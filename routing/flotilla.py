"""Modo flotilla: varias unidades con sus rutas, siguiendo su posición en tiempo real.

Pensado para una empresa con varios vehículos (o pipas): se registran las unidades con
su destino (o varias paradas), el motor calcula la ruta de cada una, y conforme llegan
posiciones GPS se actualiza el avance, los km/minutos restantes y la hora estimada de
llegada. Si una unidad se sale del corredor de su ruta (geocerca de corredor), se recalcula
la ruta desde donde está y se emite una alerta. Si se le pasa el combustible, se sugiere
la siguiente parada de recarga sobre su ruta restante.

Este módulo es lógica pura y síncrona: cada operación devuelve una lista de **eventos**
(dicts serializables a JSON). La API (`routing.api`) los reenvía por WebSocket al mapa.

Eventos:
    {"tipo": "ruta", "vehiculo": {...}}         ruta nueva o recalculada (incluye la línea)
    {"tipo": "posicion", "vehiculo": {...}}     avance (sin la línea, para que pese poco)
    {"tipo": "alerta", "id", "alerta", "mensaje", ...}  desvio | combustible_bajo | llegada | sin_ruta
    {"tipo": "eliminado", "id"}
"""
from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass, field

from geo.distancia import Punto, haversine_km, longitudes_acumuladas, proyectar_en_segmento

from .recarga import Vehiculo, estaciones_en_corredor, planear_recargas

COLORES = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6", "#bcf60c",
           "#008080", "#9a6324", "#800000", "#808000", "#000075", "#e6beff", "#ffe119", "#aaffc3"]


@dataclass
class Unidad:
    id: str
    nombre: str
    posicion: Punto
    destinos: list[Punto]
    color: str
    combustible: Vehiculo | None = None  # opcional: tanque, rendimiento y litros actuales
    linea: list[Punto] = field(default_factory=list)
    acumulado: list[float] = field(default_factory=list)
    distancia_km: float = 0.0
    duracion_min: float = 0.0
    km_recorrido: float = 0.0
    segmento: int = 0  # último segmento donde se proyectó (búsqueda local, no global)
    desvio_km: float = 0.0
    velocidad_kmh: float | None = None
    actualizado: float = field(default_factory=time.time)
    llegó: bool = False
    recalculos: int = 0
    siguiente_recarga: dict | None = None
    avisado_combustible: bool = False  # la alerta sale una vez por episodio; luego solo se actualiza la sugerencia
    datos: dict = field(default_factory=dict)

    @property
    def km_restante(self) -> float:
        return max(0.0, self.distancia_km - self.km_recorrido)

    @property
    def min_restante(self) -> float:
        if self.distancia_km <= 0:
            return 0.0
        return self.duracion_min * self.km_restante / self.distancia_km

    def resumen(self, con_linea: bool = False) -> dict:
        d = {
            "id": self.id, "nombre": self.nombre, "color": self.color,
            "lat": self.posicion[0], "lon": self.posicion[1],
            "destinos": [[lat, lon] for lat, lon in self.destinos],
            "distancia_km": round(self.distancia_km, 2), "km_recorrido": round(self.km_recorrido, 2),
            "km_restante": round(self.km_restante, 2), "min_restante": round(self.min_restante, 1),
            "eta_epoch": round(self.actualizado + self.min_restante * 60) if not self.llegó else None,
            "avance": round(self.km_recorrido / self.distancia_km, 4) if self.distancia_km else 1.0,
            "desvio_km": round(self.desvio_km, 3), "velocidad_kmh": self.velocidad_kmh,
            "llego": self.llegó, "recalculos": self.recalculos, "actualizado": self.actualizado,
            "litros": round(self.combustible.combustible_inicial_l, 1) if self.combustible else None,
            "siguiente_recarga": self.siguiente_recarga, **self.datos,
        }
        if con_linea:
            d["linea"] = [[lon, lat] for lat, lon in self.linea]
        return d


class Flotilla:
    """Registro en memoria de unidades. Seguro para usarse desde varios hilos."""

    def __init__(self, motor, indice=None, umbral_desvio_km: float = 0.5, radio_llegada_km: float = 0.15,
                 corredor_recarga_km: float = 2.0) -> None:
        self.motor = motor
        self.indice = indice
        self.umbral_desvio_km = umbral_desvio_km
        self.radio_llegada_km = radio_llegada_km
        self.corredor_recarga_km = corredor_recarga_km
        self.unidades: dict[str, Unidad] = {}
        self._lock = threading.RLock()

    # ---------- alta / baja ----------
    def registrar(self, id: str, posicion: Punto, destinos: list[Punto], nombre: str | None = None,
                  color: str | None = None, combustible: Vehiculo | None = None, datos: dict | None = None) -> list[dict]:
        if not destinos:
            raise ValueError("Se necesita al menos un destino")
        with self._lock:
            u = Unidad(id=id, nombre=nombre or id, posicion=tuple(posicion), destinos=[tuple(d) for d in destinos],
                       color=color or COLORES[len(self.unidades) % len(COLORES)], combustible=combustible,
                       datos=datos or {})
            self.unidades[id] = u
            return self._calcular_ruta(u)

    def eliminar(self, id: str) -> list[dict]:
        with self._lock:
            return [{"tipo": "eliminado", "id": id}] if self.unidades.pop(id, None) else []

    def cambiar_destinos(self, id: str, destinos: list[Punto]) -> list[dict]:
        with self._lock:
            u = self.unidades[id]
            u.destinos = [tuple(d) for d in destinos]
            u.llegó = False
            return self._calcular_ruta(u)

    # ---------- posición ----------
    def actualizar_posicion(self, id: str, lat: float, lon: float, ts: float | None = None,
                            litros: float | None = None) -> list[dict]:
        with self._lock:
            u = self.unidades[id]
            ts = ts or time.time()
            anterior, t_anterior = u.posicion, u.actualizado
            u.posicion, u.actualizado = (lat, lon), ts
            if ts > t_anterior:
                u.velocidad_kmh = round(haversine_km(anterior, u.posicion) / ((ts - t_anterior) / 3600), 1)
            if u.combustible:
                if litros is not None:
                    u.combustible.combustible_inicial_l = litros
                else:  # estimar consumo por lo recorrido
                    gastado = haversine_km(anterior, u.posicion) / u.combustible.rendimiento_km_l
                    u.combustible.combustible_inicial_l = max(0.0, u.combustible.combustible_inicial_l - gastado)
            if u.llegó or not u.linea:
                return [{"tipo": "posicion", "vehiculo": u.resumen()}]

            eventos: list[dict] = []
            self._proyectar(u)
            if u.desvio_km > self.umbral_desvio_km:
                eventos.append({"tipo": "alerta", "id": u.id, "alerta": "desvio",
                                "mensaje": f"{u.nombre} se salió {u.desvio_km:.2f} km de su ruta; se recalcula",
                                "lat": lat, "lon": lon})
                eventos += self._calcular_ruta(u)
            if haversine_km(u.posicion, u.destinos[-1]) <= self.radio_llegada_km:
                u.llegó, u.km_recorrido = True, u.distancia_km
                eventos.append({"tipo": "alerta", "id": u.id, "alerta": "llegada", "mensaje": f"{u.nombre} llegó a su destino"})
            eventos += self._revisar_combustible(u)
            eventos.append({"tipo": "posicion", "vehiculo": u.resumen()})
            return eventos

    def _proyectar(self, u: Unidad) -> None:
        """Proyecta la posición sobre la ruta buscando cerca del último segmento conocido
        (las rutas largas tienen miles de vértices; el GPS avanza poco entre lecturas)."""
        n = len(u.linea) - 1
        ventana = range(max(0, u.segmento - 50), min(n, u.segmento + 400))
        mejor = (math.inf, u.segmento, 0.0)
        for k in ventana:
            t, d = proyectar_en_segmento(u.posicion, u.linea[k], u.linea[k + 1])
            if d < mejor[0]:
                mejor = (d, k, t)
        if mejor[0] > self.umbral_desvio_km:  # quizá saltó lejos: búsqueda completa
            for k in range(n):
                t, d = proyectar_en_segmento(u.posicion, u.linea[k], u.linea[k + 1])
                if d < mejor[0]:
                    mejor = (d, k, t)
        d, k, t = mejor
        u.desvio_km, u.segmento = d, k
        u.km_recorrido = u.acumulado[k] + t * (u.acumulado[k + 1] - u.acumulado[k])

    def _calcular_ruta(self, u: Unidad) -> list[dict]:
        try:
            r = self.motor.ruta([u.posicion] + u.destinos)
        except Exception as exc:
            return [{"tipo": "alerta", "id": u.id, "alerta": "sin_ruta", "mensaje": f"No se pudo calcular la ruta: {exc}"}]
        u.linea = r["linea"] if len(r["linea"]) >= 2 else [u.posicion, u.destinos[-1]]
        u.acumulado = longitudes_acumuladas(u.linea)
        u.distancia_km, u.duracion_min = r["distancia_km"], r["duracion_min"]
        u.km_recorrido, u.segmento, u.desvio_km = 0.0, 0, 0.0
        u.recalculos += 1
        u.siguiente_recarga, u.avisado_combustible = None, False
        eventos = [{"tipo": "ruta", "vehiculo": u.resumen(con_linea=True)}]
        return eventos + self._revisar_combustible(u)

    def _revisar_combustible(self, u: Unidad) -> list[dict]:
        """Si no le alcanza para llegar, sugiere la recarga óptima sobre la ruta restante."""
        c = u.combustible
        if not c or self.indice is None or u.llegó:
            return []
        alcance = (c.combustible_inicial_l - c.reserva_l) * c.rendimiento_km_l
        if alcance >= u.km_restante:
            u.siguiente_recarga, u.avisado_combustible = None, False
            return []
        if u.siguiente_recarga and u.siguiente_recarga.get("km_ruta", -1) > u.km_recorrido:
            return []  # ya hay sugerencia vigente
        restante = [u.posicion] + u.linea[u.segmento + 1:]
        lats = [p[0] for p in restante]
        lons = [p[1] for p in restante]
        m = self.corredor_recarga_km / 111 + 0.01
        candidatas = self.indice.en_caja(min(lats) - m, min(lons) - m, max(lats) + m, max(lons) + m)
        # "paradas": en camino importa la siguiente parada necesaria, no la más barata aunque esté a la vuelta
        plan = planear_recargas(restante, candidatas, c, corredor_km=self.corredor_recarga_km, objetivo="paradas")
        if plan and plan.paradas:
            p = plan.paradas[0]
            u.siguiente_recarga = {"permiso": p.permiso, "nombre": p.nombre, "marca": p.marca, "lat": p.lat,
                                   "lon": p.lon, "km_ruta": round(u.km_recorrido + p.km_ruta, 1), "litros": p.litros,
                                   "precio": p.precio}
            msg = f"{u.nombre}: no le alcanza ({alcance:.0f} km de autonomía, faltan {u.km_restante:.0f} km). Cargar en {p.nombre}"
        else:
            # sin plan completo: al menos la estación alcanzable más lejana sobre la ruta
            cerca = [e for e in estaciones_en_corredor(restante, candidatas, self.corredor_recarga_km, c.producto)
                     if e["km_ruta"] + e["desvio_km"] <= alcance]
            u.siguiente_recarga = None
            if cerca:
                e = cerca[-1]
                u.siguiente_recarga = {k: e.get(k) for k in ("permiso", "nombre", "marca", "lat", "lon", "precio")}
                u.siguiente_recarga["km_ruta"] = round(u.km_recorrido + e["km_ruta"], 1)
            msg = f"{u.nombre}: combustible insuficiente y sin plan completo de recarga sobre la ruta"
        if u.avisado_combustible:
            return []
        u.avisado_combustible = True
        return [{"tipo": "alerta", "id": u.id, "alerta": "combustible_bajo", "mensaje": msg,
                 "siguiente_recarga": u.siguiente_recarga}]

    # ---------- lectura ----------
    def estado(self, con_lineas: bool = True) -> dict:
        """Foto de toda la flotilla como GeoJSON (posiciones + rutas restantes)."""
        with self._lock:
            features = []
            for u in self.unidades.values():
                r = u.resumen()
                features.append({"type": "Feature", "properties": {"tipo": "vehiculo", **r},
                                 "geometry": {"type": "Point", "coordinates": [u.posicion[1], u.posicion[0]]}})
                if con_lineas and u.linea:
                    features.append({"type": "Feature",
                                     "properties": {"tipo": "ruta_vehiculo", "id": u.id, "color": u.color},
                                     "geometry": {"type": "LineString",
                                                  "coordinates": [[lon, lat] for lat, lon in u.linea]}})
            return {"type": "FeatureCollection", "features": features}

    # ---------- simulación (demo sin GPS) ----------
    def simular_paso(self, segundos: float, acelerar: float = 1.0) -> list[dict]:
        """Avanza cada unidad sobre su ruta a su velocidad promedio. Para demos y pruebas."""
        eventos: list[dict] = []
        with self._lock:
            ahora = time.time()
            for u in list(self.unidades.values()):
                if u.llegó or not u.linea or u.duracion_min <= 0:
                    continue
                vel = u.distancia_km / (u.duracion_min / 60)
                km = min(u.distancia_km, u.km_recorrido + vel * segundos * acelerar / 3600)
                eventos += self.actualizar_posicion(u.id, *punto_en_km(u.linea, u.acumulado, km),
                                                    ts=max(ahora, u.actualizado + segundos * acelerar))
        return eventos


def punto_en_km(linea: list[Punto], acumulado: list[float], km: float) -> Punto:
    import bisect
    k = min(max(bisect.bisect_right(acumulado, km) - 1, 0), len(linea) - 2)
    largo = acumulado[k + 1] - acumulado[k]
    t = 0.0 if largo == 0 else (km - acumulado[k]) / largo
    a, b = linea[k], linea[k + 1]
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t

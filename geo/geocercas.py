"""Geocercas: zonas circulares, poligonales o de corredor sobre una ruta.

Casos de uso en la app:
- Mostrar solo las gasolineras dentro de una zona (mi colonia, mi municipio, un radio).
- Alertar cuando la pipa o el vehículo entra/sale de una zona (estación destino, base,
  zona con alto reporte de tomas clandestinas).
- Detectar desvíos: el vehículo sale del corredor de su ruta planeada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from .distancia import (
    Caja,
    Punto,
    caja_de,
    circulo_a_poligono,
    distancia_a_anillo_km,
    haversine_km,
    longitudes_acumuladas,
    proyectar_en_linea,
    punto_en_poligono,
    punto_en_poligono_con_huecos,
)

TIPOS = {"circulo", "poligono", "multipoligono", "corredor"}


@dataclass
class Geocerca:
    id: str
    nombre: str
    tipo: str  # "circulo" | "poligono" | "multipoligono" | "corredor"
    centro: Punto | None = None
    radio_km: float | None = None
    vertices: list[Punto] = field(default_factory=list)
    ancho_km: float | None = None  # corredor: distancia máxima a la línea
    etiquetas: dict = field(default_factory=dict)
    # multipoligono: lista de polígonos; cada uno es [exterior, hueco1, hueco2, ...]
    poligonos: list[list[list[Punto]]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.tipo == "circulo" and (self.centro is None or self.radio_km is None):
            raise ValueError("Un círculo necesita centro y radio_km")
        if self.tipo == "poligono" and len(self.vertices) < 3:
            raise ValueError("Un polígono necesita al menos 3 vértices")
        if self.tipo == "corredor" and (len(self.vertices) < 2 or self.ancho_km is None):
            raise ValueError("Un corredor necesita una línea de 2+ puntos y ancho_km")
        if self.tipo == "multipoligono" and (not self.poligonos or any(len(p[0]) < 3 for p in self.poligonos)):
            raise ValueError("Un multipolígono necesita al menos un polígono de 3+ vértices")
        if self.tipo not in TIPOS:
            raise ValueError(f"Tipo de geocerca desconocido: {self.tipo}")
        self._acumulado = longitudes_acumuladas(self.vertices) if self.tipo == "corredor" else None
        self.caja = self._calcular_caja()

    def _calcular_caja(self) -> Caja:
        if self.tipo == "circulo":
            return caja_de([self.centro], self.radio_km)
        if self.tipo == "multipoligono":
            return caja_de([v for poly in self.poligonos for v in poly[0]])
        return caja_de(self.vertices, self.ancho_km or 0.0)

    def distancia_borde_km(self, p: Punto) -> float:
        """Distancia con signo al borde: negativa dentro, positiva fuera.

        Es lo que usa el monitor para la histéresis (no salir por un brinco del GPS
        de unos metros) y sirve para avisos tipo "estás a 300 m de la zona".
        """
        if self.tipo == "circulo":
            return haversine_km(self.centro, p) - self.radio_km
        if self.tipo == "corredor":
            _, desvio = proyectar_en_linea(p, self.vertices, self._acumulado)
            return desvio - self.ancho_km
        if self.tipo == "poligono":
            d = distancia_a_anillo_km(p, self.vertices)
            return -d if punto_en_poligono(p, self.vertices) else d
        d = min(distancia_a_anillo_km(p, anillo) for poly in self.poligonos for anillo in poly)
        return -d if self.contiene(p) else d

    def contiene(self, p: Punto) -> bool:
        if self.tipo == "circulo":
            return haversine_km(self.centro, p) <= self.radio_km
        if self.tipo == "poligono":
            return punto_en_poligono(p, self.vertices)
        if self.tipo == "multipoligono":
            return any(punto_en_poligono_con_huecos(p, poly) for poly in self.poligonos)
        _, desvio = proyectar_en_linea(p, self.vertices, self._acumulado)
        return desvio <= self.ancho_km

    def a_geojson(self, circulo_como_poligono: bool = False) -> dict:
        """Feature GeoJSON. Con circulo_como_poligono=True el círculo sale como Polygon
        (útil en MapLibre, que no tiene círculos en metros); si no, como Point + radio_km."""
        props = {"id": self.id, "nombre": self.nombre, "tipo": self.tipo, **self.etiquetas}
        if self.tipo == "circulo":
            props["radio_km"] = self.radio_km
            props["centro"] = [self.centro[1], self.centro[0]]
            if circulo_como_poligono:
                anillo = [[lon, lat] for lat, lon in circulo_a_poligono(self.centro, self.radio_km)]
                geom = {"type": "Polygon", "coordinates": [anillo + [anillo[0]]]}
            else:
                geom = {"type": "Point", "coordinates": [self.centro[1], self.centro[0]]}
        elif self.tipo == "poligono":
            anillo = [[lon, lat] for lat, lon in self.vertices]
            anillo.append(anillo[0])
            geom = {"type": "Polygon", "coordinates": [anillo]}
        elif self.tipo == "multipoligono":
            geom = {"type": "MultiPolygon", "coordinates": [[_anillo_geojson(a) for a in poly] for poly in self.poligonos]}
        else:
            props["ancho_km"] = self.ancho_km
            geom = {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in self.vertices]}
        return {"type": "Feature", "geometry": geom, "properties": props}


def _anillo_geojson(anillo: list[Punto]) -> list[list[float]]:
    coords = [[lon, lat] for lat, lon in anillo]
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords


def _anillo_de_geojson(coords: list[list[float]]) -> list[Punto]:
    anillo = [(float(lat), float(lon)) for lon, lat, *_ in coords]
    if len(anillo) > 1 and anillo[0] == anillo[-1]:
        anillo.pop()
    return anillo


@dataclass
class EventoGeocerca:
    geocerca_id: str
    tipo: str  # "entrada" | "salida" | "permanencia"
    momento: datetime | None
    posicion: Punto
    permanencia_s: float | None = None  # en "permanencia" y "salida": tiempo dentro


def filtrar_dentro(geocerca: Geocerca, elementos: Iterable[dict], lat: str = "lat", lon: str = "lon") -> list[dict]:
    """Devuelve los elementos (p. ej. estaciones) cuyo punto cae dentro de la geocerca."""
    return [e for e in elementos if geocerca.contiene((e[lat], e[lon]))]


def eventos_de_recorrido(
    geocercas: list[Geocerca],
    recorrido: Iterable[tuple[Punto, datetime | None]],
) -> list[EventoGeocerca]:
    """Recorre posiciones GPS en orden y emite eventos de entrada/salida por geocerca."""
    estado: dict[str, bool] = {}
    eventos: list[EventoGeocerca] = []
    for posicion, momento in recorrido:
        for g in geocercas:
            dentro = g.contiene(posicion)
            antes = estado.get(g.id)
            if antes is not None and dentro != antes:
                eventos.append(EventoGeocerca(g.id, "entrada" if dentro else "salida", momento, posicion))
            estado[g.id] = dentro
    return eventos


# --- Construcción de geocercas a partir de datos -----------------------------------------

def desde_geojson(feature: dict, id_campo: str = "id", nombre_campo: str = "nombre") -> Geocerca:
    """Feature GeoJSON -> Geocerca. Acepta lo que produce a_geojson y polígonos del INEGI.

    - Point con propiedad radio_km (o radio_m) -> círculo
    - Polygon -> polígono (sin huecos) o multipolígono (si trae huecos)
    - MultiPolygon -> multipolígono
    - LineString con ancho_km (o ancho_m) -> corredor
    """
    geom = feature["geometry"]
    props = dict(feature.get("properties") or {})
    gid = str(props.pop(id_campo, None) or feature.get("id") or props.get("CVEGEO") or "")
    nombre = str(props.pop(nombre_campo, None) or props.get("NOMGEO") or gid)
    props.pop("tipo", None)
    tipo_geom = geom["type"]
    if tipo_geom == "Point":
        radio = props.pop("radio_km", None)
        if radio is None and "radio_m" in props:
            radio = props.pop("radio_m") / 1000
        if radio is None:
            raise ValueError(f"El punto {gid!r} necesita radio_km o radio_m para ser geocerca")
        props.pop("centro", None)
        lon, lat = geom["coordinates"][:2]
        return Geocerca(gid, nombre, "circulo", centro=(lat, lon), radio_km=float(radio), etiquetas=props)
    if tipo_geom == "LineString":
        ancho = props.pop("ancho_km", None)
        if ancho is None and "ancho_m" in props:
            ancho = props.pop("ancho_m") / 1000
        if ancho is None:
            raise ValueError(f"La línea {gid!r} necesita ancho_km o ancho_m para ser corredor")
        vertices = [(lat, lon) for lon, lat, *_ in geom["coordinates"]]
        return Geocerca(gid, nombre, "corredor", vertices=vertices, ancho_km=float(ancho), etiquetas=props)
    if tipo_geom == "Polygon":
        anillos = [_anillo_de_geojson(a) for a in geom["coordinates"]]
        if len(anillos) == 1:
            props.pop("radio_km", None)
            return Geocerca(gid, nombre, "poligono", vertices=anillos[0], etiquetas=props)
        return Geocerca(gid, nombre, "multipoligono", poligonos=[anillos], etiquetas=props)
    if tipo_geom == "MultiPolygon":
        polys = [[_anillo_de_geojson(a) for a in poly] for poly in geom["coordinates"]]
        return Geocerca(gid, nombre, "multipoligono", poligonos=polys, etiquetas=props)
    raise ValueError(f"Geometría no soportada para geocerca: {tipo_geom}")


def geocercas_desde_geojson(fc: dict, **kwargs) -> list[Geocerca]:
    return [desde_geojson(f, **kwargs) for f in fc["features"]]


def a_feature_collection(geocercas: Iterable[Geocerca], circulo_como_poligono: bool = False) -> dict:
    return {"type": "FeatureCollection",
            "features": [g.a_geojson(circulo_como_poligono) for g in geocercas]}


def geocercas_de_estaciones(
    estaciones: Iterable[dict],
    radio_km: float = 0.15,
    id_campo: str = "permiso",
    lat: str = "lat",
    lon: str = "lon",
) -> list[Geocerca]:
    """Una geocerca circular por estación (llegada a la gasolinera, entrega de la pipa)."""
    salida = []
    for e in estaciones:
        etiquetas = {k: e[k] for k in ("marca", "permiso") if k in e}
        etiquetas["capa"] = "estacion"
        salida.append(Geocerca(str(e[id_campo]), str(e.get("nombre") or e[id_campo]), "circulo",
                               centro=(float(e[lat]), float(e[lon])), radio_km=radio_km, etiquetas=etiquetas))
    return salida


def corredor_de_ruta(id: str, linea: list[Punto], ancho_km: float = 2.0, nombre: str | None = None) -> Geocerca:
    """Corredor alrededor de una ruta de OSRM. Sirve para detectar desvíos y para
    elegir gasolineras candidatas a parada (las que caen dentro del corredor)."""
    return Geocerca(id, nombre or id, "corredor", vertices=linea, ancho_km=ancho_km, etiquetas={"capa": "ruta"})


def zonas_de_referencia(coropleta_fc: dict, minimo_tomas: int = 1, campo: str = "tomas_reportadas",
                        campo_clave: str = "CVEGEO") -> list[Geocerca]:
    """Geocercas informativas a partir de la coropleta agregada de pipeline.huachicol.

    Solo municipios con al menos minimo_tomas reportadas. La geocerca es el polígono
    municipal completo: la capa sigue siendo agregada (aviso tipo "zona con reportes"),
    sin puntos ni detalle operativo. Para la coropleta por estado usa campo_clave="CVE_ENT".
    """
    zonas = []
    for f in coropleta_fc["features"]:
        props = f.get("properties") or {}
        if int(props.get(campo, 0) or 0) < minimo_tomas:
            continue
        g = desde_geojson(f, id_campo=campo_clave, nombre_campo="NOMGEO")
        g.etiquetas = {"capa": "referencia_huachicol", campo: props.get(campo),
                       "fuentes": props.get("fuentes", [])}
        zonas.append(g)
    return zonas

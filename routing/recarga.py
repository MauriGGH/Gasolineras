"""Plan de paradas de recarga óptimas a lo largo de una ruta (p. ej. de un estado a otro).

Modelo (el "problema de la gasolinera"):
- La ruta viene de OSRM como polilínea. Cada estación a <= `corredor_km` de la ruta
  se proyecta sobre ella: km de avance + desvío.
- Estado = (índice del punto, litros en el tanque discretizados en pasos de `paso_l`).
- En una estación se puede cargar hasta llenar; después se avanza a cualquier punto
  posterior alcanzable con lo que hay en el tanque, dejando siempre `reserva_l`.
- Costo de una arista = litros comprados × precio de esa estación + `costo_parada`
  si hubo carga. Dijkstra sobre este grafo da el plan óptimo.

Con `costo_parada` grande y precios iguales minimiza paradas; con `costo_parada`
pequeño minimiza dinero; con el costo en pesos de los minutos de parada minimiza
una mezcla de tiempo y dinero.

`objetivo` fija esos pesos con valores razonables:
- "costo":   pesos gastados + `costo_parada` por parada (por defecto).
- "paradas": mínimo número de paradas; a igualdad, el menor gasto.
- "tiempo":  minutos de parada (carga + desvío de ida y vuelta); a igualdad, el menor gasto.

`planear_viaje` junta todo: pide la ruta al motor (OSRM o red propia), toma del índice
las estaciones del corredor y devuelve el plan listo para el mapa (GeoJSON).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from geo.distancia import Punto, longitudes_acumuladas, proyectar_en_segmento

from .busqueda import dijkstra


@dataclass
class Vehiculo:
    tanque_l: float
    rendimiento_km_l: float  # km por litro
    combustible_inicial_l: float
    reserva_l: float = 5.0
    producto: str = "regular"  # regular | premium | diesel


@dataclass
class Parada:
    permiso: str
    nombre: str
    marca: str
    lat: float
    lon: float
    km_ruta: float
    desvio_km: float
    litros: float
    precio: float
    minutos: float = 0.0  # carga + desvío ida y vuelta

    @property
    def costo(self) -> float:
        return round(self.litros * self.precio, 2)


@dataclass
class PlanRecarga:
    paradas: list[Parada]
    costo_combustible: float
    distancia_km: float
    litros_al_llegar: float
    objetivo: str = "costo"
    minutos_paradas: float = 0.0


def _rejilla_segmentos(ruta: list[Punto], celda: float) -> dict[tuple[int, int], list[int]]:
    """Índice de los segmentos de la ruta por celda, para no comparar cada estación con
    todos los segmentos (una ruta de OSRM entre estados trae decenas de miles de vértices)."""
    rejilla: dict[tuple[int, int], list[int]] = {}
    for k, (a, b) in enumerate(zip(ruta, ruta[1:])):
        i0, i1 = sorted((math.floor(a[0] / celda), math.floor(b[0] / celda)))
        j0, j1 = sorted((math.floor(a[1] / celda), math.floor(b[1] / celda)))
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                rejilla.setdefault((i, j), []).append(k)
    return rejilla


def estaciones_en_corredor(ruta: list[Punto], estaciones: list[dict], corredor_km: float, producto: str) -> list[dict]:
    """Estaciones cerca de la ruta que venden el producto, ordenadas por km de avance."""
    acumulado = longitudes_acumuladas(ruta)
    celda = max(0.02, corredor_km / 111.0 * 1.5)  # grados; >= corredor para revisar solo las 9 celdas vecinas
    rejilla = _rejilla_segmentos(ruta, celda)
    resultado = []
    for e in estaciones:
        precio = (e.get("precios") or {}).get(producto)
        if precio is None:
            continue
        ci, cj = math.floor(e["lat"] / celda), math.floor(e["lon"] / celda)
        segmentos = {k for di in (-1, 0, 1) for dj in (-1, 0, 1) for k in rejilla.get((ci + di, cj + dj), ())}
        mejor = (math.inf, 0.0)
        for k in segmentos:
            t, d = proyectar_en_segmento((e["lat"], e["lon"]), ruta[k], ruta[k + 1])
            if d < mejor[0]:
                mejor = (d, acumulado[k] + t * (acumulado[k + 1] - acumulado[k]))
        if mejor[0] <= corredor_km:
            resultado.append({**e, "km_ruta": mejor[1], "desvio_km": mejor[0], "precio": float(precio)})
    resultado.sort(key=lambda e: e["km_ruta"])
    return resultado


PESOS_OBJETIVO = {
    # objetivo: (peso de los pesos gastados, peso de cada parada, peso de cada minuto)
    "costo": (1.0, None, 0.0),  # None -> usa `costo_parada`
    "paradas": (1e-3, 1e4, 0.0),
    "tiempo": (1e-3, 0.0, 1.0),
}


def planear_recargas(
    ruta: list[Punto],
    estaciones: list[dict],
    vehiculo: Vehiculo,
    corredor_km: float = 2.0,
    costo_parada: float = 30.0,
    paso_l: float = 1.0,
    evitar: set[str] | None = None,
    objetivo: str = "costo",
    minutos_carga: float = 8.0,
    vel_desvio_kmh: float = 35.0,
) -> PlanRecarga | None:
    """Calcula las paradas óptimas. Devuelve None si la ruta no es posible con esa autonomía.

    `estaciones`: dicts con permiso, nombre, marca, lat, lon y precios {producto: precio}.
    `evitar`: permisos a excluir (p. ej. estaciones mal calificadas por Profeco).
    """
    if objetivo not in PESOS_OBJETIVO:
        raise ValueError(f"objetivo debe ser uno de {sorted(PESOS_OBJETIVO)}")
    peso_dinero, peso_parada, peso_minuto = PESOS_OBJETIVO[objetivo]
    peso_parada = costo_parada if peso_parada is None else peso_parada
    evitar = evitar or set()
    candidatas = [e for e in estaciones_en_corredor(ruta, estaciones, corredor_km, vehiculo.producto)
                  if e.get("permiso") not in evitar]
    total_km = longitudes_acumuladas(ruta)[-1]

    # Puntos: 0 = origen, 1..n = estaciones, n+1 = destino
    km = [0.0] + [e["km_ruta"] for e in candidatas] + [total_km]
    desvio = [0.0] + [e["desvio_km"] for e in candidatas] + [0.0]
    precio = [None] + [e["precio"] for e in candidatas] + [None]
    destino = len(km) - 1
    capacidad = int(math.floor(vehiculo.tanque_l / paso_l))
    reserva = int(math.ceil(vehiculo.reserva_l / paso_l))
    inicial = min(capacidad, int(math.floor(vehiculo.combustible_inicial_l / paso_l)))

    def minutos_parada(i: int) -> float:
        return minutos_carga + 2 * desvio[i] / vel_desvio_kmh * 60

    def litros_tramo(i: int, j: int) -> float:
        distancia = desvio[i] + (km[j] - km[i]) + desvio[j]
        return distancia / vehiculo.rendimiento_km_l

    # Nodo: (punto, nivel, cargado) donde cargado=False significa "llegué, aún no cargo".
    # Cargar se modela como aristas (i, g, False) -> (i, h, True) para no mezclarlo
    # con el avance y poder reconstruir cuánto se compró en cada parada.
    def vecinos(nodo):
        i, g, cargado = nodo
        if i == destino:
            return
        if not cargado:
            yield (i, g, True), 0.0  # no cargar aquí
            if precio[i] is not None:
                for h in range(g + 1, capacidad + 1):
                    yield (i, h, True), ((h - g) * paso_l * precio[i] * peso_dinero + peso_parada
                                         + minutos_parada(i) * peso_minuto)
            return
        litros = g * paso_l
        for j in range(i + 1, destino + 1):
            restante = litros - litros_tramo(i, j)
            nivel = int(math.floor(restante / paso_l + 1e-9))
            if nivel < reserva:
                if (desvio[i] + km[j] - km[i]) / vehiculo.rendimiento_km_l > litros:
                    break  # ni sin desvío se llega; los puntos siguientes están más lejos
                continue
            yield (j, nivel, False), 0.0

    resultado = dijkstra((0, inicial, False), lambda n: n[0] == destino, vecinos)
    if resultado is None:
        return None
    _costo, camino = resultado

    paradas: list[Parada] = []
    gasto = 0.0
    for (i, g, c), (i2, h, c2) in zip(camino, camino[1:]):
        if i == i2 and not c and c2 and h > g:
            e = candidatas[i - 1]
            litros = (h - g) * paso_l
            p = Parada(e.get("permiso", ""), e.get("nombre", ""), e.get("marca", ""), e["lat"], e["lon"],
                       round(e["km_ruta"], 1), round(e["desvio_km"], 2), litros, e["precio"],
                       round(minutos_parada(i), 1))
            paradas.append(p)
            gasto += litros * e["precio"]
    return PlanRecarga(paradas, round(gasto, 2), round(total_km, 1), camino[-1][1] * paso_l, objetivo,
                       round(sum(p.minutos for p in paradas), 1))


def _caja(linea: list[Punto], margen_km: float) -> tuple[float, float, float, float]:
    lats = [p[0] for p in linea]
    lons = [p[1] for p in linea]
    dlat = margen_km / 111.0
    dlon = margen_km / (111.0 * max(0.1, math.cos(math.radians(sum(lats) / len(lats)))))
    return min(lats) - dlat, min(lons) - dlon, max(lats) + dlat, max(lons) + dlon


def planear_viaje(
    puntos: list[Punto],
    vehiculo: Vehiculo,
    motor,
    indice,
    objetivo: str = "costo",
    corredor_km: float = 2.0,
    **opciones,
) -> dict:
    """Ruta origen -> (paradas intermedias) -> destino con recargas óptimas.

    `motor`: objeto con `ruta(puntos)` (OSRM o red propia, ver `routing.motor`).
    `indice`: `routing.estaciones.IndiceEstaciones`.
    Devuelve un dict con `ruta`, `plan` y `geojson` (línea + paradas) para el mapa.
    Si no hay plan posible, `plan` es None y `motivo` lo explica.
    """
    r = motor.ruta(puntos)
    linea = r["linea"]
    estaciones = indice.en_caja(*_caja(linea, corredor_km + 1))
    plan = planear_recargas(linea, estaciones, vehiculo, corredor_km=corredor_km, objetivo=objetivo, **opciones)
    salida = {
        "motor": getattr(motor, "nombre", "?"),
        "distancia_km": round(r["distancia_km"], 1),
        "duracion_min": round(r["duracion_min"] + (plan.minutos_paradas if plan else 0), 1),
        "duracion_manejo_min": round(r["duracion_min"], 1),
        "plan": None,
        "geojson": {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"tipo": "ruta"},
             "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in linea]}}]},
    }
    if plan is None:
        autonomia = (vehiculo.tanque_l - vehiculo.reserva_l) * vehiculo.rendimiento_km_l
        salida["motivo"] = (f"No hay suficientes estaciones a <= {corredor_km} km de la ruta para una autonomía "
                            f"de {autonomia:.0f} km. Prueba con un corredor más ancho.")
        return salida
    salida["plan"] = {
        "objetivo": plan.objetivo,
        "paradas": [{**p.__dict__, "costo": p.costo} for p in plan.paradas],
        "num_paradas": len(plan.paradas),
        "costo_combustible": plan.costo_combustible,
        "litros_comprados": round(sum(p.litros for p in plan.paradas), 1),
        "minutos_paradas": plan.minutos_paradas,
        "litros_al_llegar": plan.litros_al_llegar,
    }
    for k, p in enumerate(plan.paradas, 1):
        salida["geojson"]["features"].append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
            "properties": {"tipo": "parada_recarga", "orden": k, **p.__dict__, "costo": p.costo}})
    return salida

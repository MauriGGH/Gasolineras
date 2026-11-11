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
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from geo.distancia import Punto, longitudes_acumuladas, proyectar_en_linea

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

    @property
    def costo(self) -> float:
        return round(self.litros * self.precio, 2)


@dataclass
class PlanRecarga:
    paradas: list[Parada]
    costo_combustible: float
    distancia_km: float
    litros_al_llegar: float


def estaciones_en_corredor(ruta: list[Punto], estaciones: list[dict], corredor_km: float, producto: str) -> list[dict]:
    """Estaciones cerca de la ruta que venden el producto, ordenadas por km de avance."""
    acumulado = longitudes_acumuladas(ruta)
    resultado = []
    for e in estaciones:
        precio = (e.get("precios") or {}).get(producto)
        if precio is None:
            continue
        km, desvio = proyectar_en_linea((e["lat"], e["lon"]), ruta, acumulado)
        if desvio <= corredor_km:
            resultado.append({**e, "km_ruta": km, "desvio_km": desvio, "precio": float(precio)})
    resultado.sort(key=lambda e: e["km_ruta"])
    return resultado


def planear_recargas(
    ruta: list[Punto],
    estaciones: list[dict],
    vehiculo: Vehiculo,
    corredor_km: float = 2.0,
    costo_parada: float = 30.0,
    paso_l: float = 1.0,
    evitar: set[str] | None = None,
) -> PlanRecarga | None:
    """Calcula las paradas óptimas. Devuelve None si la ruta no es posible con esa autonomía.

    `estaciones`: dicts con permiso, nombre, marca, lat, lon y precios {producto: precio}.
    `evitar`: permisos a excluir (p. ej. estaciones mal calificadas por Profeco).
    """
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
                    yield (i, h, True), (h - g) * paso_l * precio[i] + costo_parada
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
                       round(e["km_ruta"], 1), round(e["desvio_km"], 2), litros, e["precio"])
            paradas.append(p)
            gasto += litros * e["precio"]
    return PlanRecarga(paradas, round(gasto, 2), round(total_km, 1), camino[-1][1] * paso_l)

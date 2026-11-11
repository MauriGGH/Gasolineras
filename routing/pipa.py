"""Ruta de surtido para una pipa que abastece varias estaciones.

Esto es un problema de ruteo de vehículos con capacidad (CVRP), no de camino más
corto: hay que decidir el orden de visitas. Aquí va una heurística sin dependencias
(barrido por vecino más cercano respetando la capacidad + mejora 2-opt por viaje).
Para flotas o ventanas horarias, cambiar por Google OR-Tools usando la misma matriz.

La matriz de distancias puede venir de OSRM `/table` (distancia real por carretera)
o de `matriz_haversine` como aproximación.
"""
from __future__ import annotations

from dataclasses import dataclass

from geo.distancia import Punto, haversine_km


@dataclass
class Entrega:
    id: str
    punto: Punto
    litros: float


def matriz_haversine(puntos: list[Punto]) -> list[list[float]]:
    return [[haversine_km(a, b) for b in puntos] for a in puntos]


def _largo(viaje: list[int], m: list[list[float]]) -> float:
    return sum(m[a][b] for a, b in zip(viaje, viaje[1:]))


def _dos_opt(viaje: list[int], m: list[list[float]]) -> list[int]:
    """Invierte tramos mientras acorte el viaje. Extremos fijos (base)."""
    mejoro = True
    while mejoro:
        mejoro = False
        for i in range(1, len(viaje) - 2):
            for j in range(i + 1, len(viaje) - 1):
                a, b, c, d = viaje[i - 1], viaje[i], viaje[j], viaje[j + 1]
                if m[a][c] + m[b][d] < m[a][b] + m[c][d] - 1e-9:
                    viaje[i:j + 1] = reversed(viaje[i:j + 1])
                    mejoro = True
    return viaje


def planear_surtido(
    base: Punto,
    entregas: list[Entrega],
    capacidad_l: float,
    matriz: list[list[float]] | None = None,
) -> list[dict]:
    """Devuelve una lista de viajes, cada uno base -> estaciones -> base.

    `matriz` (opcional) es de tamaño (n+1)x(n+1) con la base en el índice 0.
    """
    if any(e.litros > capacidad_l for e in entregas):
        raise ValueError("Hay una entrega mayor que la capacidad de la pipa")
    puntos = [base] + [e.punto for e in entregas]
    m = matriz or matriz_haversine(puntos)
    pendientes = set(range(1, len(puntos)))
    viajes = []
    while pendientes:
        viaje, carga, actual = [0], 0.0, 0
        while True:
            opciones = [k for k in pendientes if carga + entregas[k - 1].litros <= capacidad_l]
            if not opciones:
                break
            siguiente = min(opciones, key=lambda k: m[actual][k])
            viaje.append(siguiente)
            carga += entregas[siguiente - 1].litros
            pendientes.remove(siguiente)
            actual = siguiente
        viaje.append(0)
        viaje = _dos_opt(viaje, m)
        viajes.append({
            "orden": [entregas[k - 1].id for k in viaje[1:-1]],
            "litros": carga,
            "distancia_km": round(_largo(viaje, m), 2),
        })
    return viajes

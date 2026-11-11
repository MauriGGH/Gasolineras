"""Dijkstra y A* genéricos sobre grafos implícitos.

`vecinos(nodo)` devuelve pares (vecino, costo). Esto permite usar el mismo código
sobre la red vial (nodos = intersecciones) y sobre el grafo de recarga
(nodos = (estación, nivel de tanque)).
"""
from __future__ import annotations

import heapq
import itertools
from typing import Callable, Hashable, Iterable

Nodo = Hashable
Vecinos = Callable[[Nodo], Iterable[tuple[Nodo, float]]]


def a_estrella(
    origen: Nodo,
    es_meta: Callable[[Nodo], bool],
    vecinos: Vecinos,
    heuristica: Callable[[Nodo], float] = lambda _n: 0.0,
) -> tuple[float, list[Nodo]] | None:
    """A*. Con heurística 0 es Dijkstra. La heurística debe ser admisible
    (nunca sobreestimar) para que el resultado sea óptimo.

    Devuelve (costo_total, camino) o None si la meta es inalcanzable.
    """
    contador = itertools.count()  # desempate estable sin comparar nodos
    abiertos = [(heuristica(origen), next(contador), 0.0, origen)]
    mejor_g = {origen: 0.0}
    padre: dict[Nodo, Nodo] = {}
    while abiertos:
        _f, _c, g, nodo = heapq.heappop(abiertos)
        if g > mejor_g.get(nodo, float("inf")):
            continue
        if es_meta(nodo):
            camino = [nodo]
            while camino[-1] in padre:
                camino.append(padre[camino[-1]])
            return g, camino[::-1]
        for vecino, costo in vecinos(nodo):
            if costo < 0:
                raise ValueError("Dijkstra/A* no admiten costos negativos")
            ng = g + costo
            if ng < mejor_g.get(vecino, float("inf")):
                mejor_g[vecino] = ng
                padre[vecino] = nodo
                heapq.heappush(abiertos, (ng + heuristica(vecino), next(contador), ng, vecino))
    return None


def dijkstra(origen: Nodo, es_meta: Callable[[Nodo], bool], vecinos: Vecinos) -> tuple[float, list[Nodo]] | None:
    return a_estrella(origen, es_meta, vecinos)

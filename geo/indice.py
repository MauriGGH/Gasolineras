"""Índice espacial de rejilla para muchas estaciones (~13 mil en México).

Sin dependencias: divide el mapa en celdas de `celda_km` y solo revisa las celdas
vecinas. Una consulta de radio de 5 km toca unas decenas de estaciones en vez de 13 mil.
Para "la más cercana por tiempo de manejo" se usan estas candidatas y luego OSRM `table`.
"""
from __future__ import annotations

import heapq
import math
from typing import Generic, Iterable, TypeVar

from .distancia import RADIO_TIERRA_KM, Punto, haversine_km

T = TypeVar("T")


class IndiceEspacial(Generic[T]):
    def __init__(self, celda_km: float = 5.0) -> None:
        self.celda_grados = math.degrees(celda_km / RADIO_TIERRA_KM)
        self._celdas: dict[tuple[int, int], list[tuple[Punto, T]]] = {}
        self._n = 0

    @classmethod
    def de_elementos(cls, elementos: Iterable[dict], lat: str = "lat", lon: str = "lon",
                     celda_km: float = 5.0) -> "IndiceEspacial[dict]":
        indice: IndiceEspacial[dict] = cls(celda_km)
        for e in elementos:
            indice.agregar((float(e[lat]), float(e[lon])), e)
        return indice

    def __len__(self) -> int:
        return self._n

    def _celda(self, p: Punto) -> tuple[int, int]:
        # La celda en longitud se ensancha con 1/cos(lat) para que sea ~cuadrada en km.
        return (math.floor(p[0] / self.celda_grados),
                math.floor(p[1] * math.cos(math.radians(p[0])) / self.celda_grados))

    def agregar(self, p: Punto, elemento: T) -> None:
        self._celdas.setdefault(self._celda(p), []).append((p, elemento))
        self._n += 1

    def _anillo(self, centro: tuple[int, int], r: int) -> Iterable[tuple[int, int]]:
        ci, cj = centro
        if r == 0:
            yield centro
            return
        for di in range(-r, r + 1):
            for dj in (-r, r) if abs(di) != r else range(-r, r + 1):
                yield ci + di, cj + dj

    def cercanas(self, p: Punto, radio_km: float) -> list[tuple[float, T]]:
        """Elementos a ≤ radio_km de p, ordenados por distancia: [(km, elemento), ...]."""
        celda_km = math.radians(self.celda_grados) * RADIO_TIERRA_KM
        # +1 celda de margen porque la columna depende de la latitud de cada punto.
        r_max = math.ceil(radio_km / celda_km) + 1
        centro = self._celda(p)
        salida = []
        for r in range(r_max + 1):
            for c in self._anillo(centro, r):
                for q, e in self._celdas.get(c, ()):
                    d = haversine_km(p, q)
                    if d <= radio_km:
                        salida.append((d, e))
        salida.sort(key=lambda x: x[0])
        return salida

    def k_mas_cercanas(self, p: Punto, k: int = 5, radio_max_km: float = 200.0) -> list[tuple[float, T]]:
        """Las k más cercanas en línea recta (hasta radio_max_km). Crece por anillos de celdas."""
        celda_km = math.radians(self.celda_grados) * RADIO_TIERRA_KM
        centro = self._celda(p)
        heap: list[tuple[float, int, T]] = []  # max-heap por -distancia
        contador = 0
        r_max = math.ceil(radio_max_km / celda_km) + 1
        for r in range(r_max + 1):
            for c in self._anillo(centro, r):
                for q, e in self._celdas.get(c, ()):
                    d = haversine_km(p, q)
                    if d > radio_max_km:
                        continue
                    contador += 1
                    if len(heap) < k:
                        heapq.heappush(heap, (-d, contador, e))
                    elif d < -heap[0][0]:
                        heapq.heapreplace(heap, (-d, contador, e))
            # Todo lo que falta por revisar está a más de (r - 1) celdas de distancia.
            if len(heap) == k and -heap[0][0] <= (r - 1) * celda_km:
                break
        return sorted(((-d, e) for d, _, e in heap), key=lambda x: x[0])

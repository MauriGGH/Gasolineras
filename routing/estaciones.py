"""Carga del GeoJSON de estaciones (el que produce `pipeline.transformar`) e índice espacial.

Esquema esperado por feature (propiedades): permiso, nombre, marca, precios{regular,premium,diesel}
y opcionales (horario, cve_mun, ...). La geometría es un Point [lon, lat].
"""
from __future__ import annotations

import json
import math
import os
import pathlib
from functools import lru_cache

from geo.distancia import Punto, haversine_km

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CANDIDATOS = [RAIZ / "data" / "curated" / "estaciones.geojson", RAIZ / "data" / "ejemplo" / "estaciones.geojson"]


def cargar_estaciones(ruta: str | pathlib.Path) -> list[dict]:
    datos = json.loads(pathlib.Path(ruta).read_text(encoding="utf-8"))
    salida = []
    for f in datos.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        salida.append({**(f.get("properties") or {}), "lat": float(lat), "lon": float(lon)})
    return salida


def ruta_por_defecto() -> pathlib.Path:
    if os.environ.get("GASRUTA_ESTACIONES"):
        return pathlib.Path(os.environ["GASRUTA_ESTACIONES"])
    return next(p for p in CANDIDATOS if p.exists())


class IndiceEstaciones:
    """Rejilla regular en grados: suficiente para ~13 mil estaciones del país y sin dependencias."""

    def __init__(self, estaciones: list[dict], celda_grados: float = 0.05) -> None:
        self.estaciones = estaciones
        self.celda = celda_grados
        self._rejilla: dict[tuple[int, int], list[int]] = {}
        for i, e in enumerate(estaciones):
            self._rejilla.setdefault(self._clave(e["lat"], e["lon"]), []).append(i)

    def _clave(self, lat: float, lon: float) -> tuple[int, int]:
        return int(math.floor(lat / self.celda)), int(math.floor(lon / self.celda))

    def en_radio(self, p: Punto, radio_km: float) -> list[tuple[dict, float]]:
        """Estaciones a <= radio_km en línea recta, ordenadas por distancia."""
        ci, cj = self._clave(*p)
        dlat = radio_km / 111.0
        dlon = radio_km / (111.0 * max(0.1, math.cos(math.radians(p[0]))))
        ri, rj = int(math.ceil(dlat / self.celda)), int(math.ceil(dlon / self.celda))
        salida = []
        for di in range(-ri, ri + 1):
            for dj in range(-rj, rj + 1):
                for i in self._rejilla.get((ci + di, cj + dj), []):
                    e = self.estaciones[i]
                    d = haversine_km(p, (e["lat"], e["lon"]))
                    if d <= radio_km:
                        salida.append((e, d))
        return sorted(salida, key=lambda x: x[1])

    def en_caja(self, lat_min: float, lon_min: float, lat_max: float, lon_max: float) -> list[dict]:
        i0, j0 = self._clave(lat_min, lon_min)
        i1, j1 = self._clave(lat_max, lon_max)
        return [self.estaciones[k] for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)
                for k in self._rejilla.get((i, j), [])
                if lat_min <= self.estaciones[k]["lat"] <= lat_max and lon_min <= self.estaciones[k]["lon"] <= lon_max]


@lru_cache(maxsize=4)
def indice_por_defecto(ruta: str | None = None) -> IndiceEstaciones:
    return IndiceEstaciones(cargar_estaciones(ruta or ruta_por_defecto()))

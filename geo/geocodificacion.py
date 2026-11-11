"""Georreferenciación: dirección <-> coordenadas.

Orden de preferencia:
1. Coordenadas oficiales del catálogo de la CNE (ya vienen georreferenciadas).
2. Coordenadas de OSM / DENUE cuando la CNE no trae punto.
3. Geocodificación por dirección con Nominatim (autoalojado o el público respetando
   su política de uso: 1 petición por segundo y un User-Agent propio).

La geocodificación inversa (punto -> municipio/estado) se hace contra los polígonos
del Marco Geoestadístico del INEGI, sin servicios externos.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .distancia import Punto, punto_en_poligono

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "app-gasolineras/0.1"


@dataclass
class Area:
    clave: str  # CVEGEO del INEGI, p. ej. "09015" (Cuauhtémoc, CDMX)
    nombre: str
    poligonos: list[list[Punto]]

    def contiene(self, p: Punto) -> bool:
        return any(punto_en_poligono(p, poly) for poly in self.poligonos)


def geocodificar(direccion: str, base_url: str = NOMINATIM_URL, pausa_s: float = 1.0) -> Punto | None:
    """Dirección en texto -> (lat, lon) con Nominatim. Devuelve None si no hay resultado."""
    params = urllib.parse.urlencode({"q": direccion, "format": "json", "limit": 1, "countrycodes": "mx"})
    req = urllib.request.Request(f"{base_url}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        datos = json.load(resp)
    time.sleep(pausa_s)
    if not datos:
        return None
    return float(datos[0]["lat"]), float(datos[0]["lon"])


def area_de_punto(p: Punto, areas: list[Area]) -> Area | None:
    """Geocodificación inversa contra polígonos (municipios o estados)."""
    for area in areas:
        if area.contiene(p):
            return area
    return None


def cargar_areas_geojson(ruta: str, campo_clave: str = "CVEGEO", campo_nombre: str = "NOMGEO") -> list[Area]:
    """Carga municipios/estados desde un GeoJSON (Marco Geoestadístico convertido a WGS84)."""
    with open(ruta, encoding="utf-8") as f:
        fc = json.load(f)
    areas = []
    for feat in fc["features"]:
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        anillos = [[(lat, lon) for lon, lat in poly[0]] for poly in polys]
        props = feat["properties"]
        areas.append(Area(str(props[campo_clave]), str(props[campo_nombre]), anillos))
    return areas

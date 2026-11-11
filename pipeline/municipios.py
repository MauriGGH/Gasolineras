"""Asigna municipio y estado (claves INEGI) a cada estación por punto en polígono.

Las estaciones que se cruzaron con DENUE ya traen `cve_mun`; las demás se completan con
los polígonos del Marco Geoestadístico del INEGI (GeoJSON en WGS84, con CVEGEO de 5
dígitos y NOMGEO). Se usa un prefiltro por caja envolvente para que 13 mil puntos contra
~2,500 municipios corra en segundos sin dependencias.

Cómo conseguir el GeoJSON (una sola vez, en la PC):
    1. Descargar el Marco Geoestadístico (https://www.inegi.org.mx/temas/mg/), capa 00mun.
    2. ogr2ogr -f GeoJSON -t_srs EPSG:4326 -simplify 0.001 data/geo/municipios.geojson 00mun.shp
"""
from __future__ import annotations

import json
import pathlib

from geo.distancia import punto_en_poligono


class IndiceMunicipios:
    def __init__(self, municipios_geojson: dict, campo_clave: str = "CVEGEO", campo_nombre: str = "NOMGEO"):
        self._areas = []
        for feat in municipios_geojson["features"]:
            geom = feat.get("geometry") or {}
            if geom.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            # (anillo exterior, huecos) en (lat, lon), que es lo que espera geo.distancia
            partes = [([(la, lo) for lo, la, *_ in poly[0]], [[(la, lo) for lo, la, *_ in h] for h in poly[1:]])
                      for poly in polys]
            lats = [la for ext, _ in partes for la, _ in ext]
            lons = [lo for ext, _ in partes for _, lo in ext]
            props = feat.get("properties", {})
            self._areas.append(((min(lats), min(lons), max(lats), max(lons)), partes,
                                str(props.get(campo_clave, "")).zfill(5), props.get(campo_nombre)))

    def __len__(self) -> int:
        return len(self._areas)

    def buscar(self, lat: float, lon: float) -> tuple[str, str | None] | None:
        """Devuelve (CVEGEO, nombre) del municipio que contiene el punto, o None."""
        for (la0, lo0, la1, lo1), partes, clave, nombre in self._areas:
            if not (la0 <= lat <= la1 and lo0 <= lon <= lo1):
                continue
            for exterior, huecos in partes:
                if punto_en_poligono((lat, lon), exterior) and not any(
                        punto_en_poligono((lat, lon), h) for h in huecos):
                    return clave, nombre
        return None


def asignar(estaciones: list[dict], indice: IndiceMunicipios) -> dict:
    """Completa cve_mun / municipio / cve_ent en sitio. Devuelve conteos para el reporte."""
    rep = {"municipio_por_denue": 0, "municipio_por_poligono": 0, "sin_municipio": 0}
    for e in estaciones:
        if e.get("cve_mun"):
            rep["municipio_por_denue"] += 1
        else:
            hallado = indice.buscar(e["lat"], e["lon"]) if len(indice) else None
            if hallado:
                e["cve_mun"], e["municipio"] = hallado
                rep["municipio_por_poligono"] += 1
            else:
                rep["sin_municipio"] += 1
        if e.get("cve_mun"):
            e["cve_ent"] = e["cve_mun"][:2]
    return rep


def cargar(ruta: pathlib.Path) -> IndiceMunicipios | None:
    if not ruta.exists():
        return None
    return IndiceMunicipios(json.loads(ruta.read_text(encoding="utf-8")))

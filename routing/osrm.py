"""Cliente mínimo para un servidor OSRM (autoalojado con el PBF de México).

Levantar OSRM:
    docker run -t -v $PWD/data/osm:/data osrm/osrm-backend osrm-extract -p /opt/car.lua /data/mexico-latest.osm.pbf
    docker run -t -v $PWD/data/osm:/data osrm/osrm-backend osrm-partition /data/mexico-latest.osrm
    docker run -t -v $PWD/data/osm:/data osrm/osrm-backend osrm-customize /data/mexico-latest.osrm
    docker run -t -p 5000:5000 -v $PWD/data/osm:/data osrm/osrm-backend osrm-routed --algorithm mld /data/mexico-latest.osrm
"""
from __future__ import annotations

import json
import os
import urllib.request

from geo.distancia import Punto

OSRM_URL = os.environ.get("OSRM_URL", "http://localhost:5000")


def _coords(puntos: list[Punto]) -> str:
    return ";".join(f"{lon},{lat}" for lat, lon in puntos)


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        datos = json.load(resp)
    if datos.get("code") != "Ok":
        raise RuntimeError(f"OSRM respondió {datos.get('code')}: {datos.get('message')}")
    return datos


def ruta(puntos: list[Punto], base_url: str = OSRM_URL) -> dict:
    """Ruta por carretera. Devuelve {'linea': [(lat, lon)...], 'distancia_km', 'duracion_min'}."""
    d = _get(f"{base_url}/route/v1/driving/{_coords(puntos)}?overview=full&geometries=geojson")
    r = d["routes"][0]
    return {
        "linea": [(lat, lon) for lon, lat in r["geometry"]["coordinates"]],
        "distancia_km": r["distance"] / 1000,
        "duracion_min": r["duration"] / 60,
    }


def tabla(puntos: list[Punto], base_url: str = OSRM_URL) -> dict:
    """Matriz de distancias (km) y tiempos (min) entre todos los puntos."""
    d = _get(f"{base_url}/table/v1/driving/{_coords(puntos)}?annotations=distance,duration")
    return {
        "distancia_km": [[v / 1000 if v is not None else float("inf") for v in fila] for fila in d["distances"]],
        "duracion_min": [[v / 60 if v is not None else float("inf") for v in fila] for fila in d["durations"]],
    }


def cercanas_por_tiempo(origen: Punto, estaciones: list[dict], base_url: str = OSRM_URL) -> list[dict]:
    """Ordena estaciones candidatas por tiempo real de manejo desde `origen`."""
    if not estaciones:
        return []
    puntos = [origen] + [(e["lat"], e["lon"]) for e in estaciones]
    d = _get(f"{base_url}/table/v1/driving/{_coords(puntos)}?sources=0&annotations=distance,duration")
    salida = []
    for e, dist, dur in zip(estaciones, d["distances"][0][1:], d["durations"][0][1:]):
        if dur is not None:
            salida.append({**e, "distancia_km": dist / 1000, "duracion_min": dur / 60})
    return sorted(salida, key=lambda e: e["duracion_min"])

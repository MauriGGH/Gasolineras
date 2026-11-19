"""Sesión 46: fusión de datos espaciales (GeoPandas) y temporales (Open-Meteo).

Uso:
    python pipeline_clima.py                       # sucursales.geojson -> clima_sucursales.csv
    python pipeline_clima.py otra_capa.geojson salida.csv --id permiso

La capa de entrada debe ser de puntos. Cada punto se enriquece con la temperatura y la
precipitación actuales de Open-Meteo, conservando su identificador.
"""
import argparse
import sys
import time
from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
import requests

URL = "https://api.open-meteo.com/v1/forecast"
VARIABLES = "temperature_2m,precipitation"


def obtener_clima(lat, lon, sesion=None, reintentos=3):
    """Pide el clima actual de un punto. Reintenta ante fallos de red o errores 5xx."""
    http = sesion or requests
    for intento in range(1, reintentos + 1):
        try:
            res = http.get(
                URL,
                params={"latitude": lat, "longitude": lon, "current": VARIABLES},
                timeout=15,
            )
            res.raise_for_status()
            return res.json()["current"]
        except (requests.RequestException, KeyError, ValueError):
            if intento == reintentos:
                raise
            time.sleep(2 ** intento)


def enriquecer(puntos, col_id="id", col_nombre="nombre"):
    if puntos.empty or not (puntos.geometry.geom_type == "Point").all():
        raise ValueError("La capa debe tener solo geometrías de tipo Point")
    puntos = puntos.to_crs(4326)  # Open-Meteo espera grados WGS84
    consulta = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    filas = []
    with requests.Session() as sesion:
        for _, fila in puntos.iterrows():
            lat, lon = fila.geometry.y, fila.geometry.x
            try:
                clima = obtener_clima(lat, lon, sesion)
                error = None
            except Exception as exc:  # un punto fallido no debe tirar todo el lote
                clima, error = {}, str(exc)
            filas.append({
                col_id: fila[col_id],
                "nombre": fila[col_nombre],
                "lat": lat,
                "lon": lon,
                "hora_clima": clima.get("time"),
                "temperature_2m": clima.get("temperature_2m"),
                "precipitation": clima.get("precipitation"),
                "consultado_utc": consulta,
                "error": error,
            })
    return pd.DataFrame(filas)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada", nargs="?", default="sucursales.geojson")
    ap.add_argument("salida", nargs="?", default="clima_sucursales.csv")
    ap.add_argument("--id", default="id", help="columna identificadora de la capa")
    ap.add_argument("--nombre", default="nombre", help="columna con el nombre del lugar")
    a = ap.parse_args()

    puntos = gpd.read_file(a.entrada)
    df_final = enriquecer(puntos, a.id, a.nombre)
    df_final.to_csv(a.salida, index=False)
    print(df_final.head())
    fallos = df_final["error"].notna().sum()
    print(f"\n{len(df_final) - fallos}/{len(df_final)} consultas correctas -> {a.salida}")
    sys.exit(1 if fallos else 0)

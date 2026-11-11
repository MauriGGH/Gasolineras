"""Gasolinera más cercana a ti, por tiempo real de manejo.

1. Índice espacial: candidatas en un radio en línea recta (barato).
2. Filtros: marca, producto disponible, precio máximo, estaciones a evitar.
3. Motor de ruteo (`tabla` 1×N de OSRM o de la red propia): ordena por minutos de manejo,
   que es lo que le importa al conductor (la más cercana en línea recta puede estar del
   otro lado de una autopista).
"""
from __future__ import annotations

from geo.distancia import Punto

from .estaciones import IndiceEstaciones


def gasolineras_cercanas(
    origen: Punto,
    indice: IndiceEstaciones,
    motor,
    n: int = 5,
    radio_km: float = 10.0,
    max_candidatas: int = 40,
    producto: str | None = None,
    marcas: set[str] | None = None,
    precio_max: float | None = None,
    evitar: set[str] | None = None,
    ordenar_por: str = "minutos",  # minutos | km | precio
) -> list[dict]:
    """Devuelve hasta `n` estaciones con distancia_km, duracion_min y (si aplica) precio."""
    candidatas = []
    for e, recta in indice.en_radio(origen, radio_km):
        if evitar and e.get("permiso") in evitar:
            continue
        if marcas and e.get("marca") not in marcas:
            continue
        precio = (e.get("precios") or {}).get(producto) if producto else None
        if producto and precio is None:
            continue
        if precio_max is not None and (precio is None or precio > precio_max):
            continue
        candidatas.append({**e, "linea_recta_km": round(recta, 3), **({"precio": precio} if producto else {})})
        if len(candidatas) >= max_candidatas:
            break
    if not candidatas:
        return []
    t = motor.tabla([origen] + [(e["lat"], e["lon"]) for e in candidatas], fuentes=[0])
    for e, km, mins in zip(candidatas, t["distancia_km"][0][1:], t["duracion_min"][0][1:]):
        e["distancia_km"] = round(km, 2)
        e["duracion_min"] = round(mins, 1)
    alcanzables = [e for e in candidatas if e["duracion_min"] != float("inf")]
    clave = {"minutos": lambda e: e["duracion_min"], "km": lambda e: e["distancia_km"],
             "precio": lambda e: (e.get("precio") or float("inf"), e["duracion_min"])}[ordenar_por]
    return sorted(alcanzables, key=clave)[:n]

"""Utilidades geométricas sin dependencias externas (WGS84, lat/lon en grados)."""
from __future__ import annotations

import math

RADIO_TIERRA_KM = 6371.0088

Punto = tuple[float, float]  # (lat, lon)


def haversine_km(a: Punto, b: Punto) -> float:
    """Distancia de gran círculo entre dos puntos en km."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(math.sqrt(h))


def _a_plano(p: Punto, lat0: float) -> tuple[float, float]:
    """Proyección equirectangular local a km. Precisa para distancias cortas (< 50 km)."""
    x = math.radians(p[1]) * RADIO_TIERRA_KM * math.cos(math.radians(lat0))
    y = math.radians(p[0]) * RADIO_TIERRA_KM
    return x, y


def proyectar_en_segmento(p: Punto, a: Punto, b: Punto) -> tuple[float, float]:
    """Proyecta p sobre el segmento a-b.

    Devuelve (t, distancia_km): t en [0, 1] es la posición a lo largo del segmento
    y distancia_km es la distancia perpendicular de p al segmento.
    """
    lat0 = (a[0] + b[0] + p[0]) / 3
    px, py = _a_plano(p, lat0)
    ax, ay = _a_plano(a, lat0)
    bx, by = _a_plano(b, lat0)
    dx, dy = bx - ax, by - ay
    largo2 = dx * dx + dy * dy
    t = 0.0 if largo2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / largo2))
    cx, cy = ax + t * dx, ay + t * dy
    return t, math.hypot(px - cx, py - cy)


def longitudes_acumuladas(linea: list[Punto]) -> list[float]:
    """Km acumulados en cada vértice de una polilínea."""
    acumulado = [0.0]
    for a, b in zip(linea, linea[1:]):
        acumulado.append(acumulado[-1] + haversine_km(a, b))
    return acumulado


def proyectar_en_linea(p: Punto, linea: list[Punto], acumulado: list[float] | None = None) -> tuple[float, float]:
    """Proyecta p sobre una polilínea. Devuelve (km_de_avance, desvio_km)."""
    if len(linea) < 2:
        raise ValueError("La línea necesita al menos dos puntos")
    acumulado = acumulado or longitudes_acumuladas(linea)
    mejor = (math.inf, 0.0)  # (desvio, km)
    for i, (a, b) in enumerate(zip(linea, linea[1:])):
        t, d = proyectar_en_segmento(p, a, b)
        if d < mejor[0]:
            mejor = (d, acumulado[i] + t * (acumulado[i + 1] - acumulado[i]))
    return mejor[1], mejor[0]


def punto_en_poligono(p: Punto, poligono: list[Punto]) -> bool:
    """Ray casting. El polígono es una lista de (lat, lon); no hace falta cerrarlo."""
    lat, lon = p
    dentro = False
    n = len(poligono)
    for i in range(n):
        lat1, lon1 = poligono[i]
        lat2, lon2 = poligono[(i + 1) % n]
        if (lat1 > lat) != (lat2 > lat):
            lon_cruce = lon1 + (lat - lat1) * (lon2 - lon1) / (lat2 - lat1)
            if lon < lon_cruce:
                dentro = not dentro
    return dentro

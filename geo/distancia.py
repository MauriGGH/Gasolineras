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


# --- Extensiones para geocercas y georreferenciación -----------------------------------

Caja = tuple[float, float, float, float]  # (lat_min, lon_min, lat_max, lon_max)

# Caja aproximada de la República Mexicana (incluye islas del Pacífico cercanas).
CAJA_MEXICO: Caja = (14.3, -118.7, 32.8, -86.5)


def en_mexico(p: Punto) -> bool:
    """¿La coordenada es numérica, finita y cae en la caja de México? Sirve para limpiar feeds."""
    lat, lon = p
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return False
    return CAJA_MEXICO[0] <= lat <= CAJA_MEXICO[2] and CAJA_MEXICO[1] <= lon <= CAJA_MEXICO[3]


def caja_de(puntos: list[Punto], margen_km: float = 0.0) -> Caja:
    """Caja envolvente de un conjunto de puntos, agrandada margen_km hacia cada lado."""
    lats = [p[0] for p in puntos]
    lons = [p[1] for p in puntos]
    dlat = math.degrees(margen_km / RADIO_TIERRA_KM)
    lat_ref = max(abs(min(lats)), abs(max(lats)))
    dlon = dlat / max(math.cos(math.radians(lat_ref + dlat)), 1e-6)
    return min(lats) - dlat, min(lons) - dlon, max(lats) + dlat, max(lons) + dlon


def en_caja(p: Punto, caja: Caja) -> bool:
    return caja[0] <= p[0] <= caja[2] and caja[1] <= p[1] <= caja[3]


def punto_destino(origen: Punto, rumbo_grados: float, distancia_km: float) -> Punto:
    """Punto al que se llega saliendo de origen con un rumbo (0 = norte) y una distancia."""
    d = distancia_km / RADIO_TIERRA_KM
    th = math.radians(rumbo_grados)
    lat1, lon1 = map(math.radians, origen)
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(th))
    lon2 = lon1 + math.atan2(math.sin(th) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


def circulo_a_poligono(centro: Punto, radio_km: float, lados: int = 64) -> list[Punto]:
    """Aproxima un círculo con un polígono (para pintarlo en MapLibre o guardarlo como GeoJSON)."""
    return [punto_destino(centro, 360 * i / lados, radio_km) for i in range(lados)]


def distancia_a_anillo_km(p: Punto, anillo: list[Punto]) -> float:
    """Distancia mínima de p al borde de un anillo (cerrado o no)."""
    n = len(anillo)
    return min(proyectar_en_segmento(p, anillo[i], anillo[(i + 1) % n])[1] for i in range(n))


def punto_en_poligono_con_huecos(p: Punto, anillos: list[list[Punto]]) -> bool:
    """El primer anillo es el exterior y los demás son huecos (como en GeoJSON)."""
    if not anillos or not punto_en_poligono(p, anillos[0]):
        return False
    return not any(punto_en_poligono(p, hueco) for hueco in anillos[1:])

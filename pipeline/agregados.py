"""Agregados de precios para el mapa: promedio, mínimo y máximo por estado, municipio y marca.

Sirven para la coropleta de precios y para los paneles del front ("¿qué marca es más
barata en mi estado?"). Se calculan sobre las estaciones ya integradas del día.
"""
from __future__ import annotations

import statistics
from collections import defaultdict

PRODUCTOS = ("regular", "premium", "diesel")


def _resumen(valores: list[float]) -> dict:
    return {
        "n": len(valores),
        "promedio": round(statistics.fmean(valores), 2),
        "mediana": round(statistics.median(valores), 2),
        "min": min(valores),
        "max": max(valores),
    }


def por_grupo(estaciones: list[dict], clave) -> dict[str, dict[str, dict]]:
    """{grupo: {producto: resumen}}. `clave` es una función estación -> grupo (o None para omitirla)."""
    valores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for e in estaciones:
        g = clave(e)
        if not g:
            continue
        for producto, precio in (e.get("precios") or {}).items():
            valores[g][producto].append(precio)
    return {g: {p: _resumen(v) for p, v in sorted(prods.items())} for g, prods in sorted(valores.items())}


def calcular(estaciones: list[dict], fecha: str) -> dict:
    return {
        "fecha": fecha,
        "nacional": por_grupo(estaciones, lambda e: "MX").get("MX", {}),
        "por_estado": por_grupo(estaciones, lambda e: e.get("cve_ent")),
        "por_municipio": por_grupo(estaciones, lambda e: e.get("cve_mun")),
        "por_marca": por_grupo(estaciones, lambda e: e.get("marca")),
        "por_estado_marca": por_grupo(
            estaciones, lambda e: f"{e['cve_ent']}|{e['marca']}" if e.get("cve_ent") else None),
        "estaciones_por_marca": _conteo(estaciones, "marca"),
    }


def _conteo(estaciones: list[dict], campo: str) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for e in estaciones:
        c[e.get(campo) or "?"] += 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def coropleta_precios(municipios_geojson: dict, agregados: dict, producto: str = "regular",
                      campo_clave: str = "CVEGEO") -> dict:
    """Polígonos municipales con el precio promedio del producto (solo los que tienen datos)."""
    feats = []
    for f in municipios_geojson["features"]:
        clave = str(f["properties"][campo_clave]).zfill(5)
        res = agregados["por_municipio"].get(clave, {}).get(producto)
        if res:
            feats.append({"type": "Feature", "geometry": f["geometry"],
                          "properties": {**f["properties"], "producto": producto, **res, "capa": "precio_promedio"}})
    return {"type": "FeatureCollection", "features": feats}

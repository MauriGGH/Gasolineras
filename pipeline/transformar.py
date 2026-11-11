"""Raw -> modelo limpio -> GeoJSON para el mapa.

Modelo:
    estaciones: permiso, place_id, nombre, marca, lat, lon, precios{regular,premium,diesel}
    precios (histórico): fecha, permiso, producto, precio  -> CSV que crece cada día

Uso:
    python -m pipeline.transformar data/raw/2026-11-11
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

from geo.distancia import haversine_km

from .marcas import normalizar_marca

# México continental + islas, para descartar coordenadas basura (0,0, lat/lon invertidas...)
LIMITES_MX = {"lat": (14.3, 32.8), "lon": (-118.7, -86.5)}
RANGO_PRECIO = (12.0, 40.0)  # MXN por litro; fuera de esto se marca como dudoso
PRODUCTOS = {"regular", "premium", "diesel"}
RADIO_MATCH_KM = 0.075


def leer_cne_estaciones(ruta: pathlib.Path) -> dict[str, dict]:
    """<places><place place_id=".."><name/><cre_id/><location><x/><y/></location></place>"""
    estaciones = {}
    for place in ET.parse(ruta).getroot().iter("place"):
        try:
            lon = float(place.findtext("location/x"))
            lat = float(place.findtext("location/y"))
        except (TypeError, ValueError):
            continue
        pid = place.get("place_id")
        estaciones[pid] = {
            "place_id": pid,
            "permiso": (place.findtext("cre_id") or "").strip(),
            "nombre": (place.findtext("name") or "").strip(),
            "lat": lat,
            "lon": lon,
        }
    return estaciones


def leer_cne_precios(ruta: pathlib.Path) -> dict[str, dict[str, float]]:
    """<places><place place_id=".."><gas_price type="regular">23.5</gas_price>...</place>"""
    precios: dict[str, dict[str, float]] = {}
    for place in ET.parse(ruta).getroot().iter("place"):
        pid = place.get("place_id")
        for gp in place.iter("gas_price"):
            tipo = (gp.get("type") or "").lower()
            try:
                valor = float(gp.text)
            except (TypeError, ValueError):
                continue
            if tipo in PRODUCTOS:
                precios.setdefault(pid, {})[tipo] = valor
    return precios


def leer_osm(ruta: pathlib.Path) -> list[dict]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    salida = []
    for el in datos.get("elements", []):
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        tags = el.get("tags", {})
        salida.append({"osm_id": f"{el['type']}/{el['id']}", "lat": lat, "lon": lon,
                       "brand": tags.get("brand"), "operator": tags.get("operator"),
                       "name": tags.get("name"), "opening_hours": tags.get("opening_hours")})
    return salida


def leer_denue(ruta: pathlib.Path) -> list[dict]:
    """CSV nacional del DENUE filtrado a SCIAN 468411."""
    salida = []
    with ruta.open(encoding="latin-1", newline="") as f:
        for fila in csv.DictReader(f):
            if fila.get("codigo_act") != "468411":
                continue
            try:
                salida.append({"lat": float(fila["latitud"]), "lon": float(fila["longitud"]),
                               "nombre": fila.get("nom_estab"), "razon_social": fila.get("raz_social"),
                               "cve_mun": f"{fila.get('cve_ent', ''):0>2}{fila.get('cve_mun', ''):0>3}"})
            except (KeyError, ValueError):
                continue
    return salida


def _valida(lat: float, lon: float) -> bool:
    return LIMITES_MX["lat"][0] <= lat <= LIMITES_MX["lat"][1] and LIMITES_MX["lon"][0] <= lon <= LIMITES_MX["lon"][1]


def _indice_rejilla(puntos: list[dict], celda: float = 0.01) -> dict:
    idx: dict[tuple[int, int], list[dict]] = {}
    for p in puntos:
        idx.setdefault((int(p["lat"] / celda), int(p["lon"] / celda)), []).append(p)
    return idx


def _mas_cercano(p: dict, idx: dict, celda: float = 0.01) -> dict | None:
    ci, cj = int(p["lat"] / celda), int(p["lon"] / celda)
    mejor, mejor_d = None, RADIO_MATCH_KM
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for q in idx.get((ci + di, cj + dj), []):
                d = haversine_km((p["lat"], p["lon"]), (q["lat"], q["lon"]))
                if d <= mejor_d:
                    mejor, mejor_d = q, d
    return mejor


def integrar(cne_est: dict[str, dict], cne_precios: dict[str, dict], osm: list[dict], denue: list[dict]) -> tuple[list[dict], dict]:
    """Une fuentes. Devuelve (estaciones, reporte_de_calidad)."""
    idx_osm, idx_denue = _indice_rejilla(osm), _indice_rejilla(denue)
    reporte = {"cne_total": len(cne_est), "coordenadas_invalidas": 0, "sin_precio": 0,
               "precio_dudoso": 0, "match_osm": 0, "match_denue": 0, "permiso_duplicado": 0}
    vistos: set[str] = set()
    estaciones = []
    for pid, e in cne_est.items():
        if not _valida(e["lat"], e["lon"]):
            reporte["coordenadas_invalidas"] += 1
            continue
        if e["permiso"] in vistos:
            reporte["permiso_duplicado"] += 1
            continue
        vistos.add(e["permiso"])
        precios = cne_precios.get(pid, {})
        if not precios:
            reporte["sin_precio"] += 1
        dudosos = [k for k, v in precios.items() if not RANGO_PRECIO[0] <= v <= RANGO_PRECIO[1]]
        reporte["precio_dudoso"] += bool(dudosos)
        o, d = _mas_cercano(e, idx_osm), _mas_cercano(e, idx_denue)
        reporte["match_osm"] += o is not None
        reporte["match_denue"] += d is not None
        marca = normalizar_marca((o or {}).get("brand"), e["nombre"], (o or {}).get("name"),
                                 (d or {}).get("nombre"), (d or {}).get("razon_social"))
        estaciones.append({
            **e,
            "marca": marca,
            "precios": {k: v for k, v in precios.items() if k not in dudosos},
            "horario": (o or {}).get("opening_hours"),
            "osm_id": (o or {}).get("osm_id"),
            "cve_mun": (d or {}).get("cve_mun"),
        })
    return estaciones, reporte


def a_geojson(estaciones: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
         "properties": {k: v for k, v in e.items() if k not in ("lat", "lon")}}
        for e in estaciones]}


def main(carpeta_raw: str) -> None:
    raw = pathlib.Path(carpeta_raw)
    fecha = raw.name
    salida = raw.parents[1] / "curated"
    salida.mkdir(parents=True, exist_ok=True)
    cne_est = leer_cne_estaciones(raw / "cne_estaciones.xml")
    cne_precios = leer_cne_precios(raw / "cne_precios.xml")
    osm = leer_osm(raw / "osm_fuel.json") if (raw / "osm_fuel.json").exists() else []
    denue = leer_denue(raw / "denue.csv") if (raw / "denue.csv").exists() else []
    estaciones, reporte = integrar(cne_est, cne_precios, osm, denue)

    (salida / "estaciones.geojson").write_text(json.dumps(a_geojson(estaciones), ensure_ascii=False), encoding="utf-8")
    historico = salida / "precios_historico.csv"
    nuevo = not historico.exists()
    with historico.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["fecha", "permiso", "producto", "precio"])
        for e in estaciones:
            for producto, precio in e["precios"].items():
                w.writerow([fecha, e["permiso"], producto, precio])
    (salida / f"calidad_{fecha}.json").write_text(json.dumps(reporte, indent=2), encoding="utf-8")
    print(json.dumps(reporte, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])

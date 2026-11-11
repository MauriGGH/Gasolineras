"""Corrida completa del pipeline: raw del día -> todas las capas que consumen el mapa y el ruteo.

    python -m pipeline.correr                      # usa la carpeta más reciente de data/raw/
    python -m pipeline.correr data/raw/2026-11-11
    python -m pipeline.correr --descargar          # baja CNE + OSM primero (pipeline.ingesta)

Insumos opcionales (si no están, el paso se omite y queda anotado en el manifiesto):
    data/raw/<fecha>/osm_fuel.json, denue.csv
    data/geo/municipios.geojson, data/geo/estados.geojson   (Marco Geoestadístico INEGI, WGS84)
    data/manual/profeco_quien_es_quien.csv, huachicol_*.csv

Salidas en data/curated/ (contrato en docs/contrato-datos.md).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

from . import agregados, huachicol, municipios, profeco
from .transformar import (a_geojson, escribir_historico, integrar, leer_cne_estaciones, leer_cne_precios,
                          leer_denue, leer_osm)

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
VERSION_CONTRATO = "1"


def _escribir(ruta: pathlib.Path, obj, compacto: bool = True) -> str:
    ruta.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":") if compacto else None,
                               indent=None if compacto else 2), encoding="utf-8")
    return ruta.name


def _carpeta_reciente(raw: pathlib.Path) -> pathlib.Path:
    fechas = sorted(p for p in raw.iterdir() if p.is_dir() and (p / "cne_estaciones.xml").exists())
    if not fechas:
        raise SystemExit(f"No hay corridas con cne_estaciones.xml en {raw}; corre `python -m pipeline.ingesta`.")
    return fechas[-1]


def compacto(estaciones: list[dict]) -> dict:
    """Versión ligera para el front: columnas + filas (≈4x más chica que el GeoJSON)."""
    columnas = ["permiso", "nombre", "marca", "lat", "lon", "regular", "premium", "diesel", "cve_mun", "evitar"]
    filas = [[e["permiso"], e["nombre"], e["marca"], round(e["lat"], 6), round(e["lon"], 6),
              e["precios"].get("regular"), e["precios"].get("premium"), e["precios"].get("diesel"),
              e.get("cve_mun"), bool((e.get("profeco") or {}).get("evitar"))] for e in estaciones]
    return {"columnas": columnas, "filas": filas}


def huachicol_estados_resumen(data: pathlib.Path = DATA) -> dict:
    """Último periodo anual por producto, por estado, sin geometría (panel / tooltip)."""
    salida: dict[str, dict] = {}
    for producto in ("petroliferos", "gas_lp"):
        filas = [f for f in huachicol.tabla("estado", producto, data) if f.get("periodo") == "anual"]
        if not filas:
            continue
        anio = max(int(f["anio"]) for f in filas)
        salida[producto] = {
            "anio": anio,
            "periodo": "anual",
            "estados": {f["cve_ent"].zfill(2): {"estado": f["estado"], "tomas_reportadas": int(f["tomas_reportadas"]),
                                                "fuente": f["fuente"], "url": f["url"]}
                        for f in filas if int(f["anio"]) == anio},
        }
    return salida


def correr(carpeta_raw: pathlib.Path, data: pathlib.Path = DATA, hoy: dt.date | None = None) -> dict:
    fecha = carpeta_raw.name
    curated = data / "curated"
    curated.mkdir(parents=True, exist_ok=True)
    manifiesto = {"version_contrato": VERSION_CONTRATO, "fecha_datos": fecha,
                  "generado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                  "pasos_omitidos": [], "archivos": []}

    # 1. Integración CNE + OSM + DENUE
    osm_path, denue_path = carpeta_raw / "osm_fuel.json", carpeta_raw / "denue.csv"
    osm = leer_osm(osm_path) if osm_path.exists() else []
    denue = leer_denue(denue_path) if denue_path.exists() else []
    if not osm:
        manifiesto["pasos_omitidos"].append("osm (sin osm_fuel.json): marca solo por nombre")
    if not denue:
        manifiesto["pasos_omitidos"].append("denue (sin denue.csv)")
    estaciones, reporte = integrar(leer_cne_estaciones(carpeta_raw / "cne_estaciones.xml"),
                                   leer_cne_precios(carpeta_raw / "cne_precios.xml"), osm, denue)

    # 2. Municipio / estado
    indice = municipios.cargar(data / "geo" / "municipios.geojson")
    if indice is None:
        manifiesto["pasos_omitidos"].append("municipios por polígono (sin data/geo/municipios.geojson)")
        indice = municipios.IndiceMunicipios({"features": []})
    reporte.update(municipios.asignar(estaciones, indice))

    # 3. Profeco
    evitar, rep_profeco = profeco.aplicar(estaciones, profeco.leer(data / "manual" / "profeco_quien_es_quien.csv"), hoy)
    reporte.update(rep_profeco)

    # 4. Agregados de precio
    agg = agregados.calcular(estaciones, fecha)

    a = manifiesto["archivos"]
    a.append(_escribir(curated / "estaciones.geojson", a_geojson(estaciones)))
    a.append(_escribir(curated / "estaciones.min.json", compacto(estaciones)))
    escribir_historico(curated / "precios_historico.csv", fecha, estaciones)
    a.append("precios_historico.csv")
    a.append(_escribir(curated / "precios_agregados.json", agg))
    a.append(_escribir(curated / "evitar_permisos.json", {"fecha": fecha, "permisos": evitar}, compacto=False))
    a.append(_escribir(curated / "huachicol_estados.json", huachicol_estados_resumen(data), compacto=False))

    mun_geo = data / "geo" / "municipios.geojson"
    if mun_geo.exists():
        geo = json.loads(mun_geo.read_text(encoding="utf-8"))
        for producto in ("regular", "diesel"):
            a.append(_escribir(curated / f"precio_municipios_{producto}.geojson",
                               agregados.coropleta_precios(geo, agg, producto)))
    est_geo = data / "geo" / "estados.geojson"
    if est_geo.exists():
        geo = json.loads(est_geo.read_text(encoding="utf-8"))
        for producto, info in huachicol_estados_resumen(data).items():
            conteos = huachicol.leer_conteos(data / "manual" / "huachicol_estados.csv", info["anio"], "anual",
                                             producto, nivel="estado")
            a.append(_escribir(curated / f"huachicol_estados_{producto}.geojson",
                               huachicol.coropleta(geo, conteos, "CVE_ENT", 2)))
    else:
        manifiesto["pasos_omitidos"].append("coropletas por estado (sin data/geo/estados.geojson)")

    reporte["estaciones_publicadas"] = len(estaciones)
    manifiesto["calidad"] = reporte
    a.append(_escribir(curated / f"calidad_{fecha}.json", reporte, compacto=False))
    _escribir(curated / "manifest.json", manifiesto, compacto=False)
    return manifiesto


def main(argv: list[str]) -> None:
    if "--descargar" in argv:
        from . import ingesta
        ingesta.main([])
        argv = [x for x in argv if x != "--descargar"]
    carpeta = pathlib.Path(argv[0]) if argv else _carpeta_reciente(DATA / "raw")
    print(json.dumps(correr(carpeta), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])

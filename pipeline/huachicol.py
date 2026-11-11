"""Capa de referencia de tomas clandestinas, SOLO agregada por municipio y año.

Entrada: data/manual/huachicol_municipios.csv, capturado a mano desde informes de
Pemex, respuestas de transparencia (PNT) y notas periodísticas. Cada fila lleva su
fuente y URL. No se capturan coordenadas, ductos ni ningún detalle operativo.

Salida: GeoJSON de polígonos municipales con el conteo, para una coropleta.

Uso:
    python -m pipeline.huachicol data/geo/municipios.geojson 2025
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "data"
CAMPOS = {"cve_mun", "municipio", "estado", "anio", "tomas_reportadas", "fuente", "url"}


def leer_conteos(ruta: pathlib.Path, anio: int | None = None) -> dict[str, dict]:
    with ruta.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        faltan = CAMPOS - set(lector.fieldnames or [])
        if faltan:
            raise ValueError(f"Faltan columnas en {ruta.name}: {sorted(faltan)}")
        conteos: dict[str, dict] = {}
        for fila in lector:
            if anio is not None and int(fila["anio"]) != anio:
                continue
            clave = fila["cve_mun"].zfill(5)
            actual = conteos.setdefault(clave, {"tomas_reportadas": 0, "fuentes": []})
            actual["tomas_reportadas"] += int(fila["tomas_reportadas"])
            actual["fuentes"].append({"fuente": fila["fuente"], "url": fila["url"], "anio": int(fila["anio"])})
    return conteos


def coropleta(municipios_geojson: dict, conteos: dict[str, dict], campo_clave: str = "CVEGEO") -> dict:
    features = []
    for feat in municipios_geojson["features"]:
        clave = str(feat["properties"][campo_clave]).zfill(5)
        if clave in conteos:
            props = {**feat["properties"], **conteos[clave], "capa": "huachicol_referencia"}
            features.append({"type": "Feature", "geometry": feat["geometry"], "properties": props})
    return {"type": "FeatureCollection", "features": features}


def main(ruta_municipios: str, anio: str | None = None) -> None:
    conteos = leer_conteos(RAIZ / "manual" / "huachicol_municipios.csv", int(anio) if anio else None)
    municipios = json.loads(pathlib.Path(ruta_municipios).read_text(encoding="utf-8"))
    salida = RAIZ / "curated" / "huachicol_municipios.geojson"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(coropleta(municipios, conteos), ensure_ascii=False), encoding="utf-8")
    print(f"{len(conteos)} municipios con datos -> {salida}")


if __name__ == "__main__":
    main(*sys.argv[1:])

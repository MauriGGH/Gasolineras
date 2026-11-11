"""Capa de referencia de tomas clandestinas, SOLO agregada por municipio o estado y periodo.

Entradas (capturadas a mano desde informes de Pemex, respuestas de transparencia (PNT) y
notas periodísticas; cada fila lleva fuente y URL):
    data/manual/huachicol_municipios.csv   clave cve_mun (CVEGEO de 5 dígitos)
    data/manual/huachicol_estados.csv      clave cve_ent (2 dígitos)

Columnas comunes: anio, periodo (anual | 1S | 1T ...), producto (petroliferos | gas_lp),
tomas_reportadas, fuente, url, nota. Los conteos de periodos distintos NO se suman entre
sí: cada coropleta es de un (anio, periodo, producto).

No se capturan coordenadas, ductos ni ningún detalle operativo.

Uso:
    python -m pipeline.huachicol data/geo/municipios.geojson 2024 1T
    python -m pipeline.huachicol --estados data/geo/estados.geojson 2024 anual
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "data"
CAMPOS = {"municipio", "estado", "anio", "tomas_reportadas", "fuente", "url"}
NIVELES = {
    "municipio": {"archivo": "huachicol_municipios.csv", "clave": "cve_mun", "largo": 5, "campo_geo": "CVEGEO"},
    "estado": {"archivo": "huachicol_estados.csv", "clave": "cve_ent", "largo": 2, "campo_geo": "CVE_ENT"},
}


def leer_conteos(ruta: pathlib.Path, anio: int | None = None, periodo: str | None = None,
                 producto: str | None = "petroliferos", nivel: str = "municipio") -> dict[str, dict]:
    """{clave: {tomas_reportadas, periodo, producto, fuentes[]}} para un mismo periodo.

    Las filas sin columna `periodo`/`producto` (formato viejo) cuentan como anual/petroliferos.
    """
    cfg = NIVELES[nivel]
    with ruta.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        requeridos = (CAMPOS - {"municipio"} if nivel == "estado" else CAMPOS) | {cfg["clave"]}
        faltan = requeridos - set(lector.fieldnames or [])
        if faltan:
            raise ValueError(f"Faltan columnas en {ruta.name}: {sorted(faltan)}")
        conteos: dict[str, dict] = {}
        periodos_vistos: set[tuple] = set()
        for fila in lector:
            fila_periodo = (fila.get("periodo") or "anual").strip()
            fila_producto = (fila.get("producto") or "petroliferos").strip()
            if anio is not None and int(fila["anio"]) != anio:
                continue
            if periodo is not None and fila_periodo != periodo:
                continue
            if producto is not None and fila_producto != producto:
                continue
            periodos_vistos.add((fila["anio"], fila_periodo, fila_producto))
            clave = fila[cfg["clave"]].strip().zfill(cfg["largo"])
            actual = conteos.setdefault(clave, {"tomas_reportadas": 0, "anio": int(fila["anio"]),
                                                "periodo": fila_periodo, "producto": fila_producto, "fuentes": []})
            actual["tomas_reportadas"] += int(fila["tomas_reportadas"])
            actual["fuentes"].append({"fuente": fila["fuente"], "url": fila["url"], "anio": int(fila["anio"]),
                                      "periodo": fila_periodo, "nota": (fila.get("nota") or "").strip()})
    if len(periodos_vistos) > 1:
        raise ValueError(
            f"Se mezclarían periodos distintos {sorted(periodos_vistos)}; indica anio, periodo y producto.")
    return conteos


def coropleta(geojson: dict, conteos: dict[str, dict], campo_clave: str = "CVEGEO", largo: int = 5) -> dict:
    features = []
    for feat in geojson["features"]:
        clave = str(feat["properties"][campo_clave]).zfill(largo)
        if clave in conteos:
            props = {**feat["properties"], **conteos[clave], "capa": "huachicol_referencia"}
            features.append({"type": "Feature", "geometry": feat["geometry"], "properties": props})
    return {"type": "FeatureCollection", "features": features}


def claves_sin_poligono(geojson: dict, conteos: dict[str, dict], campo_clave: str = "CVEGEO",
                        largo: int = 5) -> list[str]:
    """Claves capturadas que no existen en los polígonos (CVEGEO mal tecleado, etc.)."""
    existentes = {str(f["properties"][campo_clave]).zfill(largo) for f in geojson["features"]}
    return sorted(set(conteos) - existentes)


def tabla(nivel: str = "estado", producto: str | None = None, raiz: pathlib.Path = RAIZ) -> list[dict]:
    """Todas las filas de un nivel como lista (para el panel del front, sin geometría)."""
    ruta = raiz / "manual" / NIVELES[nivel]["archivo"]
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as f:
        filas = [dict(r) for r in csv.DictReader(f)]
    return [r for r in filas if producto is None or (r.get("producto") or "petroliferos") == producto]


def main(*args: str) -> None:
    args_l = list(args)
    nivel = "estado" if "--estados" in args_l else "municipio"
    args_l = [a for a in args_l if a != "--estados"]
    ruta_geo, anio, periodo = (args_l + [None, None, None])[:3]
    cfg = NIVELES[nivel]
    conteos = leer_conteos(RAIZ / "manual" / cfg["archivo"], int(anio) if anio else None, periodo, nivel=nivel)
    geo = json.loads(pathlib.Path(ruta_geo).read_text(encoding="utf-8"))
    huerfanas = claves_sin_poligono(geo, conteos, cfg["campo_geo"], cfg["largo"])
    if huerfanas:
        print(f"AVISO: claves sin polígono, revisar captura: {huerfanas}")
    sufijo = "_".join(x for x in (nivel, anio, periodo) if x)
    salida = RAIZ / "curated" / f"huachicol_{sufijo}.geojson"
    salida.parent.mkdir(parents=True, exist_ok=True)
    fc = coropleta(geo, conteos, cfg["campo_geo"], cfg["largo"])
    salida.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    print(f"{len(fc['features'])} {nivel}s con datos -> {salida}")


if __name__ == "__main__":
    main(*sys.argv[1:])

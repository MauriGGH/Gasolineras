"""Capa Profeco: "Quién es Quién en los combustibles" (semanal).

Profeco publica cada semana (PDF / nota) los precios más altos y más bajos por región y
la lista de estaciones verificadas, incluidas las que NO despachan litros completos o se
negaron a la verificación. No hay API, así que se captura a mano en
data/manual/profeco_quien_es_quien.csv con una fila por estación y semana:

    fecha        AAAA-MM-DD de la publicación
    permiso      PL/XXXXX/EXP/ES/AAAA (si la nota lo trae; si no, se intenta por nombre)
    nombre       razón social o nombre de la estación
    entidad      estado (texto, para desambiguar por nombre)
    producto     regular | premium | diesel | (vacío si la fila es solo de verificación)
    precio       precio reportado (opcional)
    resultado    ok | litros_incompletos | se_nego | precio_alto | precio_bajo
    fuente, url  de dónde salió la fila

Salidas:
    - propiedades `profeco` en cada estación (última calificación y fecha)
    - evitar_permisos.json: permisos que el ruteo debe excluir (`routing.recarga.planear_recargas(evitar=...)`)
"""
from __future__ import annotations

import csv
import datetime as dt
import pathlib

from .marcas import similitud_nombre

CAMPOS = {"fecha", "permiso", "nombre", "entidad", "producto", "precio", "resultado", "fuente", "url"}
RESULTADOS = {"ok", "litros_incompletos", "se_nego", "precio_alto", "precio_bajo"}
# Resultados que sacan a una estación de los planes de recarga.
NEGATIVOS = {"litros_incompletos", "se_nego"}
VIGENCIA_DIAS = 180  # una mala verificación deja de pesar después de ~6 meses


def leer(ruta: pathlib.Path) -> list[dict]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f)
        faltan = CAMPOS - set(lector.fieldnames or [])
        if faltan:
            raise ValueError(f"Faltan columnas en {ruta.name}: {sorted(faltan)}")
        filas = []
        for fila in lector:
            resultado = (fila["resultado"] or "").strip().lower()
            if resultado not in RESULTADOS:
                raise ValueError(f"Resultado desconocido {resultado!r} en {ruta.name}: {fila}")
            filas.append({**{k: (v or "").strip() for k, v in fila.items()}, "resultado": resultado})
    return filas


def _resolver_permiso(fila: dict, estaciones: list[dict]) -> str | None:
    if fila["permiso"]:
        return fila["permiso"]
    if not fila["nombre"]:
        return None
    mejor, sim = None, 0.0
    for e in estaciones:
        s = similitud_nombre(fila["nombre"], e.get("nombre"))
        if s > sim:
            mejor, sim = e, s
    # por nombre solo se acepta un parecido muy alto y único
    if mejor is None or sim < 0.92:
        return None
    empatados = [e for e in estaciones if similitud_nombre(fila["nombre"], e.get("nombre")) >= sim]
    return mejor["permiso"] if len(empatados) == 1 else None


def aplicar(estaciones: list[dict], filas: list[dict], hoy: dt.date | None = None) -> tuple[list[str], dict]:
    """Anota la última verificación en cada estación. Devuelve (permisos_a_evitar, reporte)."""
    hoy = hoy or dt.date.today()
    por_permiso = {e["permiso"]: e for e in estaciones}
    ultima: dict[str, dict] = {}
    rep = {"profeco_filas": len(filas), "profeco_sin_estacion": 0}
    for fila in sorted(filas, key=lambda f: f["fecha"]):
        permiso = _resolver_permiso(fila, estaciones)
        if permiso not in por_permiso:
            rep["profeco_sin_estacion"] += 1
            continue
        actual = ultima.setdefault(permiso, {"fecha": fila["fecha"], "resultados": set(), "fuente": "", "url": ""})
        if fila["fecha"] > actual["fecha"]:
            actual.update(fecha=fila["fecha"], resultados=set())
        actual["resultados"].add(fila["resultado"])
        actual.update(fuente=fila["fuente"], url=fila["url"])

    evitar = []
    for permiso, info in ultima.items():
        negativo = bool(info["resultados"] & NEGATIVOS)
        vigente = (hoy - dt.date.fromisoformat(info["fecha"])).days <= VIGENCIA_DIAS
        por_permiso[permiso]["profeco"] = {
            "fecha": info["fecha"],
            "resultados": sorted(info["resultados"]),
            "evitar": negativo and vigente,
            "fuente": info["fuente"],
            "url": info["url"],
        }
        if negativo and vigente:
            evitar.append(permiso)
    rep["profeco_estaciones"] = len(ultima)
    rep["profeco_evitar"] = len(evitar)
    return sorted(evitar), rep

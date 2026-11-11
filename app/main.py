# -*- coding: utf-8 -*-
"""
Servidor de la aplicación "Ojo de Dios · Gasolineras MX".

Sirve tres cosas:
  - la interfaz (app/static/index.html y sus archivos)
  - una API de solo lectura con los datos ya validados (datos/procesados/)
  - el motor de rutas, recargas, surtido y flotilla (routing.api) montado en /api/ruteo

Arranque en desarrollo:
    python scripts/construir_datos.py
    uvicorn app.main:app --reload --port 8000
y abrir http://127.0.0.1:8000
"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from routing.api import app as api_ruteo

RAIZ = Path(__file__).resolve().parent.parent
ESTATICOS = Path(__file__).resolve().parent / "static"
PROCESADOS = RAIZ / "datos" / "procesados"
ARCHIVOS = ("datos_mapa.json", "estaciones.json", "estados.geojson")

app = FastAPI(title="Ojo de Dios · Gasolineras MX", version="0.2.0")
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
app.mount("/api/ruteo", api_ruteo)
# Módulo de geocercas y ubicación del navegador (web/geo): lo importa app.js con import("/geo/index.js")
app.mount("/geo", StaticFiles(directory=RAIZ / "web" / "geo"), name="geo")


def leer_json(nombre: str):
    """Lee un JSON procesado. Si no existe, avisa cómo generarlo en vez de devolver vacío."""
    ruta = PROCESADOS / nombre
    if not ruta.exists():
        raise HTTPException(status_code=503, detail=f"Falta {nombre}. Ejecuta: python scripts/construir_datos.py")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(ESTATICOS / "index.html")


@app.get("/api/salud")
def salud():
    """Para monitoreo: dice si los datos procesados están presentes."""
    faltan = [n for n in ARCHIVOS if not (PROCESADOS / n).exists()]
    return {"estado": "ok" if not faltan else "sin_datos", "faltan": faltan}


@app.get("/api/datos")
def datos():
    """Agregados del mapa: nacional, entidades, marcas y focos de referencia."""
    return JSONResponse(leer_json("datos_mapa.json"))


@app.get("/api/estaciones")
def estaciones():
    """Todas las estaciones en formato compacto {columnas, filas}."""
    return JSONResponse(leer_json("estaciones.json"))


@app.get("/api/entidades/{nombre}")
def entidad(nombre: str):
    entidades = leer_json("datos_mapa.json")["entidades"]
    if nombre not in entidades:
        raise HTTPException(status_code=404, detail=f"Entidad no encontrada: {nombre}")
    return entidades[nombre]


@app.get("/api/geo/estados")
def geo_estados():
    """Límites estatales (provisionales; ver LEEME.md)."""
    return JSONResponse(leer_json("estados.geojson"))

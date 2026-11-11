"""Selección del motor de ruteo: OSRM si está disponible, si no la red vial propia.

    GASRUTA_MOTOR=osrm     -> siempre OSRM (OSRM_URL, por defecto http://localhost:5000)
    GASRUTA_MOTOR=offline  -> red vial propia (GASRUTA_RED_VIAL, por defecto la de ejemplo)
    (sin definir)          -> prueba OSRM y si no responde usa la red propia

Ambos exponen la misma interfaz: `ruta(puntos)` y `tabla(puntos, fuentes=None)`.
"""
from __future__ import annotations

import os
import pathlib
import urllib.request
from functools import lru_cache

from geo.distancia import Punto

from . import osrm
from .red_vial import RedVial

RAIZ = pathlib.Path(__file__).resolve().parents[1]
RED_EJEMPLO = RAIZ / "data" / "ejemplo" / "red_vial.geojson"


class MotorOSRM:
    nombre = "osrm"

    def __init__(self, base_url: str = osrm.OSRM_URL) -> None:
        self.base_url = base_url

    def ruta(self, puntos: list[Punto]) -> dict:
        return osrm.ruta(puntos, self.base_url)

    def tabla(self, puntos: list[Punto], fuentes: list[int] | None = None) -> dict:
        t = osrm.tabla(puntos, self.base_url, fuentes=fuentes)
        return t


class MotorRedVial:
    nombre = "red_vial"

    def __init__(self, red: RedVial) -> None:
        self.red = red

    def ruta(self, puntos: list[Punto]) -> dict:
        return self.red.ruta(puntos)

    def tabla(self, puntos: list[Punto], fuentes: list[int] | None = None) -> dict:
        return self.red.tabla(puntos, fuentes)


def osrm_disponible(base_url: str = osrm.OSRM_URL) -> bool:
    try:
        urllib.request.urlopen(f"{base_url}/nearest/v1/driving/-99.13,19.43", timeout=2)
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def obtener_motor():
    modo = os.environ.get("GASRUTA_MOTOR", "").lower()
    if modo == "osrm" or (modo == "" and osrm_disponible()):
        return MotorOSRM()
    return MotorRedVial(RedVial.desde_geojson(os.environ.get("GASRUTA_RED_VIAL", RED_EJEMPLO)))

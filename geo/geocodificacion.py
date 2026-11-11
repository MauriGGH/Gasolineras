"""Georreferenciación: dirección <-> coordenadas.

Orden de preferencia:
1. Coordenadas oficiales del catálogo de la CNE (ya vienen georreferenciadas).
2. Coordenadas de OSM / DENUE cuando la CNE no trae punto.
3. Geocodificación por dirección con Nominatim (autoalojado o el público respetando
   su política de uso: 1 petición por segundo y un User-Agent propio).

La geocodificación inversa (punto -> municipio/estado) se hace contra los polígonos
del Marco Geoestadístico del INEGI, sin servicios externos.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .distancia import Punto, punto_en_poligono

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "app-gasolineras/0.1"


@dataclass
class Area:
    clave: str  # CVEGEO del INEGI, p. ej. "09015" (Cuauhtémoc, CDMX)
    nombre: str
    poligonos: list[list[Punto]]

    def contiene(self, p: Punto) -> bool:
        return any(punto_en_poligono(p, poly) for poly in self.poligonos)


def geocodificar(direccion: str, base_url: str = NOMINATIM_URL, pausa_s: float = 1.0) -> Punto | None:
    """Dirección en texto -> (lat, lon) con Nominatim. Devuelve None si no hay resultado."""
    params = urllib.parse.urlencode({"q": direccion, "format": "json", "limit": 1, "countrycodes": "mx"})
    req = urllib.request.Request(f"{base_url}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        datos = json.load(resp)
    time.sleep(pausa_s)
    if not datos:
        return None
    return float(datos[0]["lat"]), float(datos[0]["lon"])


def area_de_punto(p: Punto, areas: list[Area]) -> Area | None:
    """Geocodificación inversa contra polígonos (municipios o estados)."""
    for area in areas:
        if area.contiene(p):
            return area
    return None


def cargar_areas_geojson(ruta: str, campo_clave: str = "CVEGEO", campo_nombre: str = "NOMGEO") -> list[Area]:
    """Carga municipios/estados desde un GeoJSON (Marco Geoestadístico convertido a WGS84)."""
    with open(ruta, encoding="utf-8") as f:
        fc = json.load(f)
    areas = []
    for feat in fc["features"]:
        geom = feat["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        anillos = [[(lat, lon) for lon, lat in poly[0]] for poly in polys]
        props = feat["properties"]
        areas.append(Area(str(props[campo_clave]), str(props[campo_nombre]), anillos))
    return areas


# --- Extensiones -------------------------------------------------------------------------

import re  # noqa: E402
from typing import Callable  # noqa: E402

from .distancia import en_caja, en_mexico  # noqa: E402

NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

_NUM = r"[-+]?\d+(?:[.,]\d+)?"
_DECIMAL = re.compile(rf"^\s*\(?\s*({_NUM})\s*[,;\s]\s*({_NUM})\s*\)?\s*$")
_DMS = re.compile(
    r"(\d+(?:\.\d+)?)\s*[°º]\s*(?:(\d+(?:\.\d+)?)\s*['′]\s*)?(?:(\d+(?:\.\d+)?)\s*(?:\"|″|'')\s*)?([NSEWO])",
    re.IGNORECASE,
)


def parsear_coordenadas(texto: str) -> Punto | None:
    """Reconoce coordenadas escritas por el usuario antes de ir al geocodificador.

    Acepta "19.4326, -99.1332", "19.4326 -99.1332", enlaces de Google Maps con "@lat,lon"
    y grados-minutos-segundos como 19°25'57"N 99°07'59"W (O = oeste también vale).
    Si el usuario escribe "lon, lat" con valores de México (p. ej. -99.13, 19.43), se corrige.
    """
    texto = texto.strip()
    if "@" in texto:
        m = re.search(rf"@({_NUM}),({_NUM})", texto)
        if m:
            texto = f"{m.group(1)},{m.group(2)}"
    m = _DECIMAL.match(texto)
    if m:
        a, b = (float(x.replace(",", ".")) for x in m.groups())
        if not en_mexico((a, b)) and en_mexico((b, a)):
            a, b = b, a
        return (a, b) if abs(a) <= 90 and abs(b) <= 180 else None
    partes = _DMS.findall(texto)
    if len(partes) == 2:
        valores = {}
        for g, mi, s, hemi in partes:
            v = float(g) + float(mi or 0) / 60 + float(s or 0) / 3600
            hemi = hemi.upper()
            if hemi in "SWO":
                v = -v
            valores["lat" if hemi in "NS" else "lon"] = v
        if len(valores) == 2:
            return valores["lat"], valores["lon"]
    return None


@dataclass
class ResultadoGeocodificacion:
    lat: float
    lon: float
    etiqueta: str
    fuente: str  # "coordenadas" | "nominatim" | "cache"
    estado: str | None = None
    municipio: str | None = None
    cp: str | None = None

    @property
    def punto(self) -> Punto:
        return self.lat, self.lon


def _pedir_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "es"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


class Geocodificador:
    """Geocodificación directa e inversa con Nominatim, con caché y ritmo de 1 petición/s.

    - Si el texto ya son coordenadas, no consulta nada.
    - Resultados fuera de México se descartan.
    - `pedir_json` se puede inyectar (pruebas, otro proveedor, Nominatim propio).
    """

    def __init__(self, base_url: str = "https://nominatim.openstreetmap.org",
                 pausa_s: float = 1.0, pedir_json: Callable[[str], object] = _pedir_json,
                 reloj: Callable[[], float] = time.monotonic, dormir: Callable[[float], None] = time.sleep) -> None:
        self.base_url = base_url.rstrip("/")
        self.pausa_s = pausa_s
        self._pedir = pedir_json
        self._reloj = reloj
        self._dormir = dormir
        self._ultima = -1e18
        self._cache: dict[str, object] = {}

    def _consultar(self, ruta: str, params: dict) -> object:
        url = f"{self.base_url}/{ruta}?{urllib.parse.urlencode(params)}"
        if url in self._cache:
            return self._cache[url]
        espera = self._ultima + self.pausa_s - self._reloj()
        if espera > 0:
            self._dormir(espera)
        self._ultima = self._reloj()
        datos = self._pedir(url)
        self._cache[url] = datos
        return datos

    @staticmethod
    def _resultado(d: dict, fuente: str = "nominatim") -> ResultadoGeocodificacion:
        a = d.get("address") or {}
        return ResultadoGeocodificacion(
            float(d["lat"]), float(d["lon"]), d.get("display_name", ""), fuente,
            estado=a.get("state"),
            municipio=a.get("county") or a.get("city") or a.get("town") or a.get("municipality"),
            cp=a.get("postcode"),
        )

    def buscar(self, texto: str, limite: int = 5) -> list[ResultadoGeocodificacion]:
        coords = parsear_coordenadas(texto)
        if coords:
            return [ResultadoGeocodificacion(coords[0], coords[1], f"{coords[0]:.6f}, {coords[1]:.6f}", "coordenadas")]
        datos = self._consultar("search", {"q": texto, "format": "jsonv2", "addressdetails": 1,
                                           "limit": limite, "countrycodes": "mx"})
        res = [self._resultado(d) for d in datos or []]
        return [r for r in res if en_mexico(r.punto)]

    def inversa(self, p: Punto, zoom: int = 18) -> ResultadoGeocodificacion | None:
        """(lat, lon) -> dirección legible (calle, colonia, municipio, estado)."""
        datos = self._consultar("reverse", {"lat": f"{p[0]:.6f}", "lon": f"{p[1]:.6f}",
                                            "format": "jsonv2", "addressdetails": 1, "zoom": zoom})
        if not datos or "error" in datos:
            return None
        return self._resultado(datos)


class IndiceAreas:
    """Punto -> municipio/estado contra polígonos del INEGI, respetando huecos y
    multipolígonos y con prefiltro por caja (2,469 municipios sin recorrerlos todos)."""

    def __init__(self, fc: dict, campo_clave: str = "CVEGEO", campo_nombre: str = "NOMGEO") -> None:
        from .geocercas import desde_geojson  # import local para no crear ciclos

        self.areas = [desde_geojson(f, id_campo=campo_clave, nombre_campo=campo_nombre) for f in fc["features"]]

    @classmethod
    def desde_archivo(cls, ruta: str, **kwargs) -> "IndiceAreas":
        with open(ruta, encoding="utf-8") as f:
            return cls(json.load(f), **kwargs)

    def area_de(self, p: Punto):
        """Devuelve la geocerca del área (id = CVEGEO, nombre = NOMGEO) o None."""
        for a in self.areas:
            if en_caja(p, a.caja) and a.contiene(p):
                return a
        return None

    def clave_de(self, p: Punto) -> str | None:
        a = self.area_de(p)
        return a.id if a else None

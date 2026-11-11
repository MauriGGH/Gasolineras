"""Descarga de fuentes crudas. Cada corrida guarda en data/raw/AAAA-MM-DD/.

Uso:
    python -m pipeline.ingesta            # todas las fuentes
    python -m pipeline.ingesta cne osm    # solo algunas
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FUENTES = {
    # Comisión Nacional de Energía (antes CRE). Se actualizan diario ~18:00 (GMT-6).
    "cne_precios": "https://publicacionexterna.azurewebsites.net/publicaciones/prices",
    "cne_estaciones": "https://publicacionexterna.azurewebsites.net/publicaciones/places",
}
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Espejos públicos de Overpass: si el principal responde 502/504 (frecuente), se prueba el siguiente.
OVERPASS_ESPEJOS = [
    OVERPASS_URL,
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
# Todas las gasolineras de México en OSM, con etiquetas (brand, operator, horario...).
OVERPASS_QUERY = """
[out:json][timeout:300];
area["ISO3166-1"="MX"][admin_level=2]->.mx;
(
  node["amenity"="fuel"](area.mx);
  way["amenity"="fuel"](area.mx);
);
out center tags;
"""
USER_AGENT = "app-gasolineras/0.1"
RAIZ = pathlib.Path(__file__).resolve().parents[1] / "data" / "raw"


def _descargar(url: str, destino: pathlib.Path, datos: bytes | None = None, intentos: int = 3) -> pathlib.Path:
    """Descarga con reintentos (espera 5 s, 15 s...) ante errores 5xx o de red."""
    for intento in range(1, intentos + 1):
        req = urllib.request.Request(url, data=datos, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                contenido = resp.read()
            break
        except (urllib.error.URLError, TimeoutError) as e:
            temporal = not isinstance(e, urllib.error.HTTPError) or e.code >= 500 or e.code == 429
            if not temporal or intento == intentos:
                raise
            espera = 5 * 3 ** (intento - 1)
            print(f"  {url}: {e}; reintento {intento}/{intentos - 1} en {espera} s")
            time.sleep(espera)
    destino.write_bytes(contenido)
    print(f"  {destino.name}: {len(contenido) / 1e6:.1f} MB")
    return destino


def carpeta_del_dia(fecha: dt.date | None = None) -> pathlib.Path:
    carpeta = RAIZ / (fecha or dt.date.today()).isoformat()
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ingestar_cne(carpeta: pathlib.Path) -> None:
    _descargar(FUENTES["cne_precios"], carpeta / "cne_precios.xml")
    _descargar(FUENTES["cne_estaciones"], carpeta / "cne_estaciones.xml")


def ingestar_osm(carpeta: pathlib.Path) -> None:
    """OSM es complementario (marca y horario): si ningún espejo responde, la corrida sigue sin él."""
    cuerpo = urllib.parse.urlencode({"data": OVERPASS_QUERY}).encode()
    for url in OVERPASS_ESPEJOS:
        try:
            _descargar(url, carpeta / "osm_fuel.json", cuerpo, intentos=2)
            return
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  Overpass {url} falló: {e}")
    print("  AVISO: sin datos de OSM en esta corrida; la marca se deduce solo del nombre")


def ingestar_denue(carpeta: pathlib.Path) -> None:
    """DENUE no tiene un archivo único estable para SCIAN 468411: se baja el CSV
    nacional desde https://www.inegi.org.mx/app/descarga/?ti=6 y se filtra con
    `pipeline.transformar.leer_denue`. Aquí solo se deja la nota de la corrida."""
    (carpeta / "denue_LEEME.json").write_text(json.dumps({
        "fuente": "INEGI DENUE",
        "scian": "468411 Comercio al por menor de gasolina y diésel",
        "accion": "descargar CSV nacional y guardarlo como denue.csv en esta carpeta",
    }, ensure_ascii=False, indent=2), encoding="utf-8")


PASOS = {"cne": ingestar_cne, "osm": ingestar_osm, "denue": ingestar_denue}


def main(argv: list[str]) -> None:
    carpeta = carpeta_del_dia()
    for nombre in argv or list(PASOS):
        print(f"Ingesta {nombre} -> {carpeta}")
        PASOS[nombre](carpeta)


if __name__ == "__main__":
    main(sys.argv[1:])

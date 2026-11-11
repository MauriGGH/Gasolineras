"""Normalización de marcas de gasolineras.

Prioridad: etiqueta `brand` de OSM -> reglas sobre nombre / razón social -> "Independiente".
"""
from __future__ import annotations

import re
import unicodedata

# patrón (sobre texto sin acentos y en minúsculas) -> marca canónica
REGLAS: list[tuple[str, str]] = [
    (r"\bpemex\b|franquicia pemex", "Pemex"),
    (r"\boxxo ?gas\b", "Oxxo Gas"),
    (r"\bg ?500\b", "G500"),
    (r"\bbp\b", "BP"),
    (r"\bshell\b", "Shell"),
    (r"\bmobil\b|exxon", "Mobil"),
    (r"\bchevron\b|\btexaco\b", "Chevron"),
    (r"^arco$|\barco (gas|mexico)\b", "Arco"),  # "arco" suelto da falsos positivos (Arcos, Arco Norte)
    (r"\btotal ?energies\b|^total( mexico)?$", "TotalEnergies"),  # evita "Servicio Total"
    (r"\brepsol\b", "Repsol"),
    (r"\bhidrosina\b", "Hidrosina"),
    (r"\bpetro ?7\b|\bpetro seven\b|\b7-?eleven\b", "Petro-7"),
    (r"\bgulf\b", "Gulf"),
    (r"\bredco\b", "Redco"),
    (r"\bfull ?gas\b", "FullGas"),
    (r"\bla gas\b", "La Gas"),
    (r"\bpetromax\b", "Petromax"),
    (r"\bvalero\b", "Valero"),
    (r"\bcostco\b", "Costco"),
    (r"\bsoriana\b", "Soriana"),
    (r"\bmerco\b", "Merco"),
    (r"\borsan\b", "Orsan"),
    (r"\brendichicas\b", "Rendichicas"),
    (r"\bkm ?gas\b", "KM Gas"),
    (r"\bgas ?express ?nieto\b", "Gas Express Nieto"),
]
_COMPILADAS = [(re.compile(p), m) for p, m in REGLAS]


def _limpiar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_acentos.lower()).strip()


def normalizar_marca(*textos: str | None) -> str:
    """Recibe en orden de confianza (brand OSM, nombre, razón social) y devuelve la marca."""
    for texto in textos:
        if not texto:
            continue
        t = _limpiar(texto)
        for patron, marca in _COMPILADAS:
            if patron.search(t):
                return marca
    return "Independiente"


_SUFIJOS = re.compile(
    r"\b(s ?a ?p ?i|s ?a|s ?de ?r ?l|de ?c ?v|sapi|sa|cv|rl|"
    r"gasolinera|gasolineria|estacion|de servicio|servicio|servicios|grupo|gasolineras)\b"
)


def nombre_comparable(texto: str | None) -> str:
    """Nombre sin acentos, signos ni sufijos societarios ("SA de CV", "Gasolinera"...)."""
    if not texto:
        return ""
    t = re.sub(r"[^a-z0-9 ]", " ", _limpiar(texto))
    return re.sub(r"\s+", " ", _SUFIJOS.sub(" ", t)).strip()


def similitud_nombre(a: str | None, b: str | None) -> float:
    """0..1. Usa rapidfuzz (token_set_ratio) si está instalado; si no, difflib."""
    a, b = nombre_comparable(a), nombre_comparable(b)
    if not a or not b:
        return 0.0
    try:
        from rapidfuzz import fuzz
    except ImportError:
        from difflib import SequenceMatcher

        ta, tb = set(a.split()), set(b.split())
        if ta <= tb or tb <= ta:
            return 1.0
        return SequenceMatcher(None, a, b).ratio()
    return fuzz.token_set_ratio(a, b) / 100.0

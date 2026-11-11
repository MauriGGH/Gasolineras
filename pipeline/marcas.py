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
    (r"\barco\b", "Arco"),
    (r"\btotal ?energies\b|\btotal\b", "TotalEnergies"),
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

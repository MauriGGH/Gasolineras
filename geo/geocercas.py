"""Geocercas: zonas circulares, poligonales o de corredor sobre una ruta.

Casos de uso en la app:
- Mostrar solo las gasolineras dentro de una zona (mi colonia, mi municipio, un radio).
- Alertar cuando la pipa o el vehículo entra/sale de una zona (estación destino, base,
  zona con alto reporte de tomas clandestinas).
- Detectar desvíos: el vehículo sale del corredor de su ruta planeada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from .distancia import Punto, haversine_km, longitudes_acumuladas, proyectar_en_linea, punto_en_poligono


@dataclass
class Geocerca:
    id: str
    nombre: str
    tipo: str  # "circulo" | "poligono" | "corredor"
    centro: Punto | None = None
    radio_km: float | None = None
    vertices: list[Punto] = field(default_factory=list)
    ancho_km: float | None = None  # corredor: distancia máxima a la línea
    etiquetas: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tipo == "circulo" and (self.centro is None or self.radio_km is None):
            raise ValueError("Un círculo necesita centro y radio_km")
        if self.tipo == "poligono" and len(self.vertices) < 3:
            raise ValueError("Un polígono necesita al menos 3 vértices")
        if self.tipo == "corredor" and (len(self.vertices) < 2 or self.ancho_km is None):
            raise ValueError("Un corredor necesita una línea de 2+ puntos y ancho_km")
        if self.tipo not in {"circulo", "poligono", "corredor"}:
            raise ValueError(f"Tipo de geocerca desconocido: {self.tipo}")
        self._acumulado = longitudes_acumuladas(self.vertices) if self.tipo == "corredor" else None

    def contiene(self, p: Punto) -> bool:
        if self.tipo == "circulo":
            return haversine_km(self.centro, p) <= self.radio_km
        if self.tipo == "poligono":
            return punto_en_poligono(p, self.vertices)
        _, desvio = proyectar_en_linea(p, self.vertices, self._acumulado)
        return desvio <= self.ancho_km

    def a_geojson(self) -> dict:
        props = {"id": self.id, "nombre": self.nombre, "tipo": self.tipo, **self.etiquetas}
        if self.tipo == "circulo":
            props["radio_km"] = self.radio_km
            geom = {"type": "Point", "coordinates": [self.centro[1], self.centro[0]]}
        elif self.tipo == "poligono":
            anillo = [[lon, lat] for lat, lon in self.vertices]
            anillo.append(anillo[0])
            geom = {"type": "Polygon", "coordinates": [anillo]}
        else:
            props["ancho_km"] = self.ancho_km
            geom = {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in self.vertices]}
        return {"type": "Feature", "geometry": geom, "properties": props}


@dataclass
class EventoGeocerca:
    geocerca_id: str
    tipo: str  # "entrada" | "salida"
    momento: datetime | None
    posicion: Punto


def filtrar_dentro(geocerca: Geocerca, elementos: Iterable[dict], lat: str = "lat", lon: str = "lon") -> list[dict]:
    """Devuelve los elementos (p. ej. estaciones) cuyo punto cae dentro de la geocerca."""
    return [e for e in elementos if geocerca.contiene((e[lat], e[lon]))]


def eventos_de_recorrido(
    geocercas: list[Geocerca],
    recorrido: Iterable[tuple[Punto, datetime | None]],
) -> list[EventoGeocerca]:
    """Recorre posiciones GPS en orden y emite eventos de entrada/salida por geocerca."""
    estado: dict[str, bool] = {}
    eventos: list[EventoGeocerca] = []
    for posicion, momento in recorrido:
        for g in geocercas:
            dentro = g.contiene(posicion)
            antes = estado.get(g.id)
            if antes is not None and dentro != antes:
                eventos.append(EventoGeocerca(g.id, "entrada" if dentro else "salida", momento, posicion))
            estado[g.id] = dentro
    return eventos

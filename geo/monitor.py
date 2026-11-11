"""Monitor de geocercas en vivo para el GPS del conductor o de la pipa.

A diferencia de `geocercas.eventos_de_recorrido` (que compara dentro/fuera punto a
punto), este monitor está pensado para posiciones reales con ruido:

- Histéresis: para salir hay que alejarse más de `histeresis_km` del borde, así un
  brinco del GPS de 10–20 m junto al borde no genera entrada/salida/entrada.
- Precisión: se ignoran lecturas con precisión peor que `precision_max_m`.
- Permanencia: emite "permanencia" una vez cuando se lleva `permanencia_s` dentro
  (p. ej. la pipa lleva 5 min en la estación = entrega en curso).
- Prefiltro por caja: con miles de geocercas solo evalúa las que pueden contener el punto.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from .distancia import Punto, en_caja
from .geocercas import EventoGeocerca, Geocerca


@dataclass
class _Estado:
    dentro: bool
    desde: datetime | None = None
    permanencia_avisada: bool = False


class MonitorGeocercas:
    def __init__(
        self,
        geocercas: Iterable[Geocerca] = (),
        histeresis_km: float = 0.03,
        precision_max_m: float | None = 100.0,
        permanencia_s: float | None = None,
        evento_inicial: bool = True,
    ) -> None:
        self.histeresis_km = histeresis_km
        self.precision_max_m = precision_max_m
        self.permanencia_s = permanencia_s
        self.evento_inicial = evento_inicial
        self._geocercas: dict[str, Geocerca] = {}
        self._estado: dict[str, _Estado] = {}
        self._oyentes: list[Callable[[EventoGeocerca], None]] = []
        for g in geocercas:
            self.agregar(g)

    # --- administración ---------------------------------------------------------------
    def agregar(self, g: Geocerca) -> None:
        self._geocercas[g.id] = g
        self._estado.pop(g.id, None)

    def quitar(self, geocerca_id: str) -> None:
        self._geocercas.pop(geocerca_id, None)
        self._estado.pop(geocerca_id, None)

    def al_evento(self, oyente: Callable[[EventoGeocerca], None]) -> None:
        self._oyentes.append(oyente)

    def dentro_de(self) -> list[Geocerca]:
        return [self._geocercas[i] for i, e in self._estado.items() if e.dentro and i in self._geocercas]

    # --- evaluación -------------------------------------------------------------------
    def _dentro_ahora(self, g: Geocerca, p: Punto, antes: bool | None) -> bool:
        if not en_caja(p, g.caja) and not antes:
            return False
        d = g.distancia_borde_km(p)
        return d <= self.histeresis_km if antes else d <= 0

    def actualizar(self, posicion: Punto, momento: datetime | None = None,
                   precision_m: float | None = None) -> list[EventoGeocerca]:
        if self.precision_max_m is not None and precision_m is not None and precision_m > self.precision_max_m:
            return []
        eventos: list[EventoGeocerca] = []
        for gid, g in self._geocercas.items():
            estado = self._estado.get(gid)
            antes = estado.dentro if estado else None
            ahora = self._dentro_ahora(g, posicion, antes)
            if estado is None:
                self._estado[gid] = _Estado(ahora, momento if ahora else None)
                if ahora and self.evento_inicial:
                    eventos.append(EventoGeocerca(gid, "entrada", momento, posicion))
                continue
            if ahora and not antes:
                self._estado[gid] = _Estado(True, momento)
                eventos.append(EventoGeocerca(gid, "entrada", momento, posicion))
            elif antes and not ahora:
                eventos.append(EventoGeocerca(gid, "salida", momento, posicion, _segundos(estado.desde, momento)))
                self._estado[gid] = _Estado(False)
            elif ahora and self.permanencia_s is not None and not estado.permanencia_avisada:
                t = _segundos(estado.desde, momento)
                if t is not None and t >= self.permanencia_s:
                    estado.permanencia_avisada = True
                    eventos.append(EventoGeocerca(gid, "permanencia", momento, posicion, t))
        for ev in eventos:
            for oyente in self._oyentes:
                oyente(ev)
        return eventos


def _segundos(desde: datetime | None, hasta: datetime | None) -> float | None:
    if desde is None or hasta is None:
        return None
    return (hasta - desde).total_seconds()

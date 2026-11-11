"""Red vial propia con Dijkstra / A* (sin OSRM).

Sirve para dos cosas:
1. Modo sin servidor: con la red de ejemplo (`data/ejemplo/red_vial.geojson`, carreteras
   federales principales simplificadas) se pueden probar rutas, recargas y flotillas
   sin levantar OSRM.
2. Grafos propios: cualquier GeoJSON de LineStrings (p. ej. un extracto de la Red Nacional
   de Caminos del INEGI) se carga igual. Para todo el país conviene OSRM (Contraction
   Hierarchies / MLD), que responde en milisegundos; aquí el algoritmo es A* con la
   heurística haversine / velocidad máxima, que es admisible y por lo tanto óptima.

Los puntos que no caen sobre la red se "enganchan" a los `k` nodos más cercanos con un
tramo de acceso (distancia en línea recta × factor de rodeo, a velocidad urbana).
"""
from __future__ import annotations

import heapq
import json
import math
import pathlib
from dataclasses import dataclass

from geo.distancia import Punto, haversine_km

from .busqueda import a_estrella

FACTOR_RODEO = 1.3  # una calle real mide ~30 % más que la línea recta
VEL_ACCESO_KMH = 35.0
VEL_DEFECTO_KMH = 80.0
CELDA_GRADOS = 0.1


@dataclass
class Arista:
    destino: int
    km: float
    minutos: float


class RedVial:
    def __init__(self) -> None:
        self.nodos: list[Punto] = []
        self.ady: list[list[Arista]] = []
        self._por_coord: dict[tuple[float, float], int] = {}
        self._rejilla: dict[tuple[int, int], list[int]] = {}
        self.vel_max_kmh = VEL_DEFECTO_KMH

    # ---------- construcción ----------
    def _nodo(self, p: Punto) -> int:
        clave = (round(p[0], 5), round(p[1], 5))
        if clave not in self._por_coord:
            self._por_coord[clave] = len(self.nodos)
            self.nodos.append(clave)
            self.ady.append([])
            celda = (int(math.floor(clave[0] / CELDA_GRADOS)), int(math.floor(clave[1] / CELDA_GRADOS)))
            self._rejilla.setdefault(celda, []).append(self._por_coord[clave])
        return self._por_coord[clave]

    def agregar_via(self, linea: list[Punto], vel_kmh: float = VEL_DEFECTO_KMH, doble_sentido: bool = True) -> None:
        self.vel_max_kmh = max(self.vel_max_kmh, vel_kmh)
        ids = [self._nodo(p) for p in linea]
        for a, b in zip(ids, ids[1:]):
            if a == b:
                continue
            km = haversine_km(self.nodos[a], self.nodos[b])
            self.ady[a].append(Arista(b, km, km / vel_kmh * 60))
            if doble_sentido:
                self.ady[b].append(Arista(a, km, km / vel_kmh * 60))

    @classmethod
    def desde_geojson(cls, ruta: str | pathlib.Path) -> "RedVial":
        """LineStrings con propiedades opcionales `vel_kmh` y `oneway`."""
        datos = json.loads(pathlib.Path(ruta).read_text(encoding="utf-8"))
        red = cls()
        for f in datos["features"]:
            g = f["geometry"]
            lineas = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
            props = f.get("properties") or {}
            for linea in lineas:
                red.agregar_via([(lat, lon) for lon, lat in linea], float(props.get("vel_kmh", VEL_DEFECTO_KMH)),
                                not props.get("oneway", False))
        return red

    # ---------- consultas ----------
    def cercanos(self, p: Punto, k: int = 3, radio_celdas: int = 1) -> list[tuple[int, float]]:
        """Los k nodos más cercanos (id, km). Amplía la búsqueda hasta encontrar algo."""
        ci, cj = int(math.floor(p[0] / CELDA_GRADOS)), int(math.floor(p[1] / CELDA_GRADOS))
        r = radio_celdas
        while True:
            cand = [n for di in range(-r, r + 1) for dj in range(-r, r + 1) for n in self._rejilla.get((ci + di, cj + dj), [])]
            if len(cand) >= k or r > 60:
                break
            r *= 2
        return sorted(((n, haversine_km(p, self.nodos[n])) for n in cand), key=lambda x: x[1])[:k]

    def _acceso(self, km_recta: float) -> tuple[float, float]:
        km = km_recta * FACTOR_RODEO
        return km, km / VEL_ACCESO_KMH * 60

    def ruta(self, puntos: list[Punto], criterio: str = "minutos") -> dict:
        """Ruta que pasa por todos los `puntos` en orden. Misma forma que `osrm.ruta`."""
        linea: list[Punto] = []
        km_total = min_total = 0.0
        for a, b in zip(puntos, puntos[1:]):
            tramo = self._tramo(a, b, criterio)
            if tramo is None:
                raise RuntimeError(f"Sin ruta entre {a} y {b}")
            linea.extend(tramo["linea"] if not linea else tramo["linea"][1:])
            km_total += tramo["distancia_km"]
            min_total += tramo["duracion_min"]
        return {"linea": linea, "distancia_km": km_total, "duracion_min": min_total}

    def _tramo(self, a: Punto, b: Punto, criterio: str) -> dict | None:
        recta = haversine_km(a, b)
        directo_km, directo_min = self._acceso(recta)
        ORIGEN, META = -1, -2
        salidas = {n: self._acceso(d) for n, d in self.cercanos(a)}
        llegadas = {n: self._acceso(d) for n, d in self.cercanos(b)}
        peso = (lambda km, mins: mins) if criterio == "minutos" else (lambda km, mins: km)

        def vecinos(n):
            if n == ORIGEN:
                for m, (km, mins) in salidas.items():
                    yield m, peso(km, mins)
                if recta < 15:  # trayectos urbanos cortos: ir directo
                    yield META, peso(directo_km, directo_min)
                return
            for ar in self.ady[n]:
                yield ar.destino, peso(ar.km, ar.minutos)
            if n in llegadas:
                yield META, peso(*llegadas[n])

        def h(n):
            if n in (ORIGEN, META):
                return 0.0
            d = haversine_km(self.nodos[n], b)
            return d if criterio != "minutos" else d / self.vel_max_kmh * 60

        r = a_estrella(ORIGEN, lambda n: n == META, vecinos, h)
        if r is None:
            return None
        _, camino = r
        linea = [a] + [self.nodos[n] for n in camino[1:-1]] + [b]
        km = mins = 0.0
        for u, v in zip(camino, camino[1:]):
            if u == ORIGEN and v == META:
                dk, dm = directo_km, directo_min
            elif u == ORIGEN:
                dk, dm = salidas[v]
            elif v == META:
                dk, dm = llegadas[u]
            else:
                ar = min((x for x in self.ady[u] if x.destino == v), key=lambda x: peso(x.km, x.minutos))
                dk, dm = ar.km, ar.minutos
            km += dk
            mins += dm
        return {"linea": linea, "distancia_km": km, "duracion_min": mins}

    def tabla(self, puntos: list[Punto], fuentes: list[int] | None = None) -> dict:
        """Matriz de distancias/tiempos (Dijkstra de una fuente por origen). Misma forma que `osrm.tabla`."""
        fuentes = list(range(len(puntos))) if fuentes is None else fuentes
        enganche = [{n: self._acceso(d) for n, d in self.cercanos(p)} for p in puntos]
        dist, dur = [], []
        for i in fuentes:
            mejor_min = self._dijkstra_desde(enganche[i])
            fila_km, fila_min = [], []
            for j, p in enumerate(puntos):
                if i == j:
                    fila_km.append(0.0)
                    fila_min.append(0.0)
                    continue
                cand = [(m + am, k + ak) for n, (ak, am) in enganche[j].items() if n in mejor_min
                        for m, k in [mejor_min[n]]]
                recta = haversine_km(puntos[i], p)
                if recta < 15:
                    k, m = self._acceso(recta)
                    cand.append((m, k))
                m, k = min(cand) if cand else (math.inf, math.inf)
                fila_km.append(k)
                fila_min.append(m)
            dist.append(fila_km)
            dur.append(fila_min)
        return {"distancia_km": dist, "duracion_min": dur}

    def _dijkstra_desde(self, inicio: dict[int, tuple[float, float]]) -> dict[int, tuple[float, float]]:
        """Dijkstra multi-fuente por tiempo. Devuelve {nodo: (minutos, km)}."""
        mejor: dict[int, tuple[float, float]] = {}
        cola = [(mins, km, n) for n, (km, mins) in inicio.items()]
        heapq.heapify(cola)
        while cola:
            mins, km, n = heapq.heappop(cola)
            if n in mejor:
                continue
            mejor[n] = (mins, km)
            for ar in self.ady[n]:
                if ar.destino not in mejor:
                    heapq.heappush(cola, (mins + ar.minutos, km + ar.km, ar.destino))
        return mejor

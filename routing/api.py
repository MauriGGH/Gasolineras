"""API HTTP + WebSocket del motor de ruteo (FastAPI).

    python -m pip install -e ".[api,vrp]"
    uvicorn routing.api:app --reload --port 8000
    # documentación interactiva: http://localhost:8000/docs

Endpoints
    GET  /salud                          motor activo y número de estaciones
    GET  /estaciones?bbox=lon1,lat1,lon2,lat2&marca=Pemex
    GET  /cercanas?lat=&lon=&n=5&producto=regular&marca=Pemex&radio_km=10&ordenar_por=minutos
    POST /ruta                           ruta simple por varios puntos
    POST /ruta/recargas                  ruta entre estados con paradas de recarga óptimas
    POST /ruta/surtido                   flota de pipas (OR-Tools)
    POST /flotilla/vehiculos             alta de una o varias unidades (modo flotilla)
    POST /flotilla/posiciones            posiciones GPS de una o varias unidades
    PUT  /flotilla/vehiculos/{id}/destinos
    DELETE /flotilla/vehiculos/{id}
    GET  /flotilla                       foto de la flotilla (GeoJSON)
    POST /flotilla/simulacion            mover las unidades solas sobre sus rutas (demo)
    WS   /flotilla/ws                    eventos en tiempo real (ver routing.flotilla)
    GET  /demo/flotilla                  página de prueba (Leaflet) que consume el WebSocket

El WebSocket manda primero {"tipo": "estado", "geojson": ...} y después cada evento.
También acepta mensajes del cliente con la misma forma que los POST:
    {"tipo": "posicion", "id": "u1", "lat": 19.4, "lon": -99.1}
    {"tipo": "registrar", "vehiculos": [...]}
"""
from __future__ import annotations

import asyncio
import contextlib
import pathlib
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .cercanas import gasolineras_cercanas
from .estaciones import indice_por_defecto, permisos_a_evitar
from .flotilla import Flotilla
from .motor import obtener_motor
from .recarga import Vehiculo, planear_viaje
from .vrp import Pedido, Pipa, planear_flota_surtido

app = FastAPI(title="App Gasolineras · ruteo", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

Coord = tuple[float, float]  # [lat, lon]


class Estado:
    flotilla: Flotilla | None = None
    clientes: set[WebSocket] = set()
    simulacion: asyncio.Task | None = None


def motor():
    return obtener_motor()


def indice():
    return indice_por_defecto()


def flotilla() -> Flotilla:
    if Estado.flotilla is None:
        Estado.flotilla = Flotilla(motor(), indice())
    return Estado.flotilla


async def difundir(eventos: list[dict]) -> None:
    muertos = []
    for ws in list(Estado.clientes):
        try:
            for e in eventos:
                await ws.send_json(e)
        except Exception:
            muertos.append(ws)
    for ws in muertos:
        Estado.clientes.discard(ws)


# ---------------- modelos ----------------
class VehiculoIn(BaseModel):
    tanque_l: float = Field(50, gt=0)
    rendimiento_km_l: float = Field(12, gt=0)
    combustible_inicial_l: float = Field(50, ge=0)
    reserva_l: float = Field(5, ge=0)
    producto: Literal["regular", "premium", "diesel"] = "regular"

    def a_vehiculo(self) -> Vehiculo:
        return Vehiculo(**self.model_dump())


class RutaIn(BaseModel):
    puntos: list[Coord] = Field(..., min_length=2, description="[[lat, lon], ...] origen, intermedios, destino")


class RecargasIn(RutaIn):
    vehiculo: VehiculoIn = VehiculoIn()
    objetivo: Literal["costo", "paradas", "tiempo"] = "costo"
    corredor_km: float = Field(2.0, gt=0, le=20)
    costo_parada: float = 30.0
    minutos_carga: float = 8.0
    evitar: list[str] = []
    evitar_profeco: bool = Field(True, description="excluir estaciones de evitar_permisos.json del pipeline")


class PedidoIn(BaseModel):
    id: str
    lat: float
    lon: float
    litros: float = Field(..., gt=0)
    descarga_min: float = 30
    ventana: tuple[float, float] | None = None
    datos: dict = {}


class PipaIn(BaseModel):
    id: str
    capacidad_l: float = Field(..., gt=0)
    costo_fijo: float = 0


class SurtidoIn(BaseModel):
    base: Coord
    pedidos: list[PedidoIn] = Field(..., min_length=1)
    pipas: list[PipaIn] = Field(..., min_length=1)
    minimizar: Literal["km", "minutos"] = "km"
    jornada_min: float = 720
    segundos_busqueda: int = Field(5, ge=1, le=60)


class UnidadIn(BaseModel):
    id: str
    posicion: Coord
    destinos: list[Coord] = Field(..., min_length=1)
    nombre: str | None = None
    color: str | None = None
    combustible: VehiculoIn | None = None
    datos: dict = {}


class AltaFlotillaIn(BaseModel):
    vehiculos: list[UnidadIn] = Field(..., min_length=1)


class PosicionIn(BaseModel):
    id: str
    lat: float
    lon: float
    ts: float | None = None
    litros: float | None = None


class PosicionesIn(BaseModel):
    posiciones: list[PosicionIn] = Field(..., min_length=1)


class SimulacionIn(BaseModel):
    activa: bool = True
    cada_seg: float = Field(1.0, gt=0.05)
    acelerar: float = Field(30.0, gt=0, description="x veces la velocidad real")


# ---------------- endpoints ----------------
@app.get("/demo/flotilla", include_in_schema=False)
def demo_flotilla():
    return FileResponse(pathlib.Path(__file__).parent / "static" / "demo_flotilla.html")


@app.get("/salud")
def salud():
    return {"motor": motor().nombre, "estaciones": len(indice().estaciones)}


@app.get("/estaciones")
def estaciones(bbox: str | None = Query(None, description="lon1,lat1,lon2,lat2"), marca: str | None = None,
               limite: int = 5000):
    if bbox:
        lon1, lat1, lon2, lat2 = map(float, bbox.split(","))
        lista = indice().en_caja(min(lat1, lat2), min(lon1, lon2), max(lat1, lat2), max(lon1, lon2))
    else:
        lista = indice().estaciones
    if marca:
        lista = [e for e in lista if e.get("marca") == marca]
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
         "properties": {k: v for k, v in e.items() if k not in ("lat", "lon")}} for e in lista[:limite]]}


@app.get("/cercanas")
def cercanas(lat: float, lon: float, n: int = Query(5, ge=1, le=50), radio_km: float = Query(10, gt=0, le=100),
             producto: Literal["regular", "premium", "diesel"] | None = None, marca: list[str] | None = Query(None),
             precio_max: float | None = None, ordenar_por: Literal["minutos", "km", "precio"] = "minutos"):
    return {"resultados": gasolineras_cercanas((lat, lon), indice(), motor(), n=n, radio_km=radio_km, producto=producto,
                                               marcas=set(marca) if marca else None, precio_max=precio_max,
                                               ordenar_por=ordenar_por)}


@app.post("/ruta")
def ruta(body: RutaIn):
    r = motor().ruta([tuple(p) for p in body.puntos])
    return {"distancia_km": round(r["distancia_km"], 2), "duracion_min": round(r["duracion_min"], 1),
            "geojson": {"type": "Feature", "properties": {},
                        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lat, lon in r["linea"]]}}}


@app.post("/ruta/recargas")
def ruta_recargas(body: RecargasIn):
    return planear_viaje([tuple(p) for p in body.puntos], body.vehiculo.a_vehiculo(), motor(), indice(),
                         objetivo=body.objetivo, corredor_km=body.corredor_km, costo_parada=body.costo_parada,
                         minutos_carga=body.minutos_carga,
                         evitar=set(body.evitar) | (set(permisos_a_evitar()) if body.evitar_profeco else set()))


@app.post("/ruta/surtido")
def ruta_surtido(body: SurtidoIn):
    pedidos = [Pedido(p.id, (p.lat, p.lon), p.litros, p.descarga_min, p.ventana, p.datos) for p in body.pedidos]
    pipas = [Pipa(p.id, p.capacidad_l, p.costo_fijo) for p in body.pipas]
    return planear_flota_surtido(tuple(body.base), pedidos, pipas, motor(), body.minimizar, body.jornada_min,
                                 body.segundos_busqueda)


# ---------------- flotilla ----------------
def _alta(vehiculos: list[UnidadIn]) -> list[dict]:
    f = flotilla()
    eventos = []
    for v in vehiculos:
        eventos += f.registrar(v.id, tuple(v.posicion), [tuple(d) for d in v.destinos], v.nombre, v.color,
                               v.combustible.a_vehiculo() if v.combustible else None, v.datos)
    return eventos


def _posiciones(posiciones: list[PosicionIn]) -> list[dict]:
    f = flotilla()
    eventos = []
    for p in posiciones:
        if p.id not in f.unidades:
            eventos.append({"tipo": "error", "id": p.id, "mensaje": "unidad no registrada"})
            continue
        eventos += f.actualizar_posicion(p.id, p.lat, p.lon, p.ts, p.litros)
    return eventos


@app.post("/flotilla/vehiculos")
async def flotilla_alta(body: AltaFlotillaIn):
    eventos = await asyncio.to_thread(_alta, body.vehiculos)  # rutas en paralelo al loop
    await difundir(eventos)
    return {"eventos": eventos}


@app.post("/flotilla/posiciones")
async def flotilla_posiciones(body: PosicionesIn):
    eventos = await asyncio.to_thread(_posiciones, body.posiciones)
    await difundir(eventos)
    return {"eventos": eventos}


@app.put("/flotilla/vehiculos/{id}/destinos")
async def flotilla_destinos(id: str, body: RutaIn):
    if id not in flotilla().unidades:
        raise HTTPException(404, "unidad no registrada")
    eventos = await asyncio.to_thread(flotilla().cambiar_destinos, id, [tuple(p) for p in body.puntos])
    await difundir(eventos)
    return {"eventos": eventos}


@app.delete("/flotilla/vehiculos/{id}")
async def flotilla_baja(id: str):
    eventos = flotilla().eliminar(id)
    if not eventos:
        raise HTTPException(404, "unidad no registrada")
    await difundir(eventos)
    return {"eventos": eventos}


@app.get("/flotilla")
def flotilla_estado(con_lineas: bool = True):
    return flotilla().estado(con_lineas)


async def _bucle_simulacion(cada_seg: float, acelerar: float) -> None:
    while True:
        eventos = await asyncio.to_thread(flotilla().simular_paso, cada_seg, acelerar)
        if eventos:
            await difundir(eventos)
        await asyncio.sleep(cada_seg)


@app.post("/flotilla/simulacion")
async def flotilla_simulacion(body: SimulacionIn):
    if Estado.simulacion:
        Estado.simulacion.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await Estado.simulacion
        Estado.simulacion = None
    if body.activa:
        Estado.simulacion = asyncio.create_task(_bucle_simulacion(body.cada_seg, body.acelerar))
    return {"activa": body.activa}


@app.websocket("/flotilla/ws")
async def flotilla_ws(ws: WebSocket):
    await ws.accept()
    Estado.clientes.add(ws)
    try:
        await ws.send_json({"tipo": "estado", "ts": time.time(), "geojson": flotilla().estado()})
        while True:
            msg = await ws.receive_json()
            try:
                if msg.get("tipo") == "posicion":
                    eventos = await asyncio.to_thread(_posiciones, [PosicionIn(**msg)])
                elif msg.get("tipo") == "posiciones":
                    eventos = await asyncio.to_thread(_posiciones, [PosicionIn(**p) for p in msg["posiciones"]])
                elif msg.get("tipo") == "registrar":
                    eventos = await asyncio.to_thread(_alta, [UnidadIn(**v) for v in msg["vehiculos"]])
                elif msg.get("tipo") == "estado":
                    await ws.send_json({"tipo": "estado", "ts": time.time(), "geojson": flotilla().estado()})
                    continue
                else:
                    await ws.send_json({"tipo": "error", "mensaje": f"tipo desconocido: {msg.get('tipo')}"})
                    continue
            except Exception as exc:  # validación, unidad inexistente...
                await ws.send_json({"tipo": "error", "mensaje": str(exc)})
                continue
            await difundir(eventos)
    except WebSocketDisconnect:
        pass
    finally:
        Estado.clientes.discard(ws)

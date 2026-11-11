# Motor de ruteo

Todo vive en `routing/`. Funciona con dos motores intercambiables:

| Motor | Cuándo | Cómo |
|---|---|---|
| **OSRM** | Producción, todo el país | `docker` con el PBF de México (ver `routing/osrm.py`). `GASRUTA_MOTOR=osrm`, `OSRM_URL=...` |
| **Red vial propia** | Sin servidor, pruebas, demos | A*/Dijkstra propios (`routing/red_vial.py`) sobre `data/ejemplo/red_vial.geojson` u otro GeoJSON de carreteras (`GASRUTA_RED_VIAL`) |

Sin `GASRUTA_MOTOR` se prueba OSRM y, si no responde, se usa la red propia.
Las estaciones salen de `data/curated/estaciones.geojson` (pipeline) o, si no existe,
de `data/ejemplo/estaciones.geojson` (**datos sintéticos**, permisos `EJ/...`). Se puede
forzar con `GASRUTA_ESTACIONES`.

## Funciones

| Necesidad | Módulo | Algoritmo |
|---|---|---|
| Gasolinera más cercana | `cercanas.py` | Rejilla espacial → candidatas en radio → matriz 1×N del motor; orden por minutos, km o precio. Filtros: marca, producto, precio máximo, estaciones a evitar |
| Ruta A → B (entre estados, con puntos intermedios) | `motor.py`, `red_vial.py` | OSRM (MLD/CH) o A* con heurística haversine / vel. máx. (admisible) |
| Paradas de recarga óptimas | `recarga.py` | Dijkstra sobre estados (estación, litros en tanque). Objetivos: `costo`, `paradas`, `tiempo` |
| Ruta del que surte (flota de pipas) | `vrp.py` | CVRP con ventanas de horario en OR-Tools (guided local search). Respaldo sin OR-Tools: `pipa.py` |
| Flotilla en tiempo real | `flotilla.py`, `api.py` | Rutas por unidad, avance por proyección GPS, recálculo al salir del corredor, ETA, sugerencia de recarga. Eventos por WebSocket |

### Recargas: qué optimiza cada objetivo

- `costo`: pesos gastados + `costo_parada` (30 MXN por defecto, para no partir la carga en muchas paradas). Carga solo lo necesario donde conviene.
- `paradas`: el menor número de paradas; entre empates, el menor gasto.
- `tiempo`: minutos de parada (carga `minutos_carga` + desvío ida y vuelta); entre empates, el menor gasto.

Las estaciones del corredor se buscan con una rejilla sobre los segmentos de la ruta, así una
ruta de OSRM con ~30 mil vértices contra 13 mil estaciones se resuelve en ~0.5 s.

## API

```bash
python -m pip install -e ".[dev,api,vrp]"
uvicorn routing.api:app --reload --port 8000
# http://localhost:8000/docs           documentación interactiva
# http://localhost:8000/demo/flotilla  demo del modo flotilla (Leaflet)
```

Ejemplos:

```bash
curl "localhost:8000/cercanas?lat=19.43&lon=-99.13&producto=regular&marca=Pemex&n=5"

curl -X POST localhost:8000/ruta/recargas -H 'Content-Type: application/json' -d '{
  "puntos": [[19.4326, -99.1332], [25.6866, -100.3161]],
  "objetivo": "costo",
  "vehiculo": {"tanque_l": 45, "rendimiento_km_l": 12, "combustible_inicial_l": 20, "producto": "regular"}}'

curl -X POST localhost:8000/ruta/surtido -H 'Content-Type: application/json' -d '{
  "base": [19.53, -99.19],
  "pipas": [{"id": "P1", "capacidad_l": 31000}, {"id": "P2", "capacidad_l": 20000}],
  "pedidos": [{"id": "EST-1", "lat": 19.60, "lon": -99.20, "litros": 10000, "ventana": [0, 120]},
              {"id": "EST-2", "lat": 19.45, "lon": -99.10, "litros": 15000}]}'
```

### Modo flotilla (varias unidades a la vez)

1. Alta de unidades (una o muchas) con su posición y destino(s):
   `POST /flotilla/vehiculos {"vehiculos": [{"id": "u1", "posicion": [lat, lon], "destinos": [[lat, lon]], "combustible": {...}}]}`
2. Posiciones GPS: `POST /flotilla/posiciones {"posiciones": [{"id": "u1", "lat": .., "lon": .., "litros": ..}]}`
   o por el mismo WebSocket: `{"tipo": "posicion", "id": "u1", "lat": .., "lon": ..}`.
3. El mapa se conecta a `ws://.../flotilla/ws`: recibe `estado` (GeoJSON completo) y luego
   eventos `ruta` (con la línea), `posicion` (avance, km y minutos restantes, ETA), `alerta`
   (`desvio`, `llegada`, `combustible_bajo`, `sin_ruta`) y `eliminado`.
4. Sin GPS real: `POST /flotilla/simulacion {"activa": true, "acelerar": 60}` mueve las unidades solas.

El estado vive en memoria (un proceso). Para varias réplicas, mover el registro a Redis y
difundir los eventos por pub/sub.

## Datos de ejemplo

`python scripts/generar_datos_ejemplo.py` regenera `data/ejemplo/` (carreteras federales
simplificadas entre ciudades reales y ~360 estaciones inventadas con el esquema del pipeline).

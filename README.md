# App Gasolineras

Mapa de gasolineras en México para conductores: la más cercana por tiempo real de manejo,
precios del día por marca (Pemex, Oxxo Gas, G500, BP, Shell, etc.), rutas entre estados con
paradas de recarga óptimas, ruta de surtido para pipas, geocercas y una capa de referencia
agregada de tomas clandestinas por municipio.

El frontend se adaptará del mapa de referencia (mismo diseño, cambio de tema).

## Estructura

| Carpeta | Contenido |
|---|---|
| `pipeline/` | Ingesta (CNE, OSM, DENUE), limpieza, marcas, integración, GeoJSON, capa de huachicol agregada |
| `routing/` | Dijkstra/A* genéricos, plan de recargas por autonomía, ruta de pipa (CVRP), cliente OSRM |
| `geo/` | Distancias, proyección sobre rutas, geocercas (círculo, polígono, corredor), georreferenciación |
| `docs/` | Fuentes de datos, diseño del pipeline y del ruteo |
| `data/manual/` | Datos capturados a mano con fuente (huachicol por municipio) |

## Uso rápido

```bash
python -m pip install -e ".[dev]"
python -m pytest

python -m pipeline.ingesta                       # baja CNE + OSM a data/raw/AAAA-MM-DD/
python -m pipeline.transformar data/raw/AAAA-MM-DD  # -> data/curated/estaciones.geojson
```

Para rutas reales hace falta un OSRM local con el PBF de México (ver `routing/osrm.py`).

## Datos sensibles

La capa de huachicol es solo referencia agregada (conteos por municipio y año con fuente).
No se guardan coordenadas de tomas, ductos ni detalles operativos.

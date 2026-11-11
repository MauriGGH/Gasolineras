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
| `geo/` | Distancias, proyección sobre rutas, geocercas (círculo, polígono, multipolígono, corredor), monitor en vivo, índice espacial, georreferenciación |
| `web/geo/` | Módulo JS para el navegador: ubicación del usuario y geocercas sobre el mismo GeoJSON |
| `docs/` | Fuentes de datos, diseño del pipeline y del ruteo |
| `data/manual/` | Datos capturados a mano con fuente (huachicol por estado/municipio, Profeco) |
| `data/geo/` | Polígonos INEGI de estados y municipios (no se versionan, ver docs/contrato-datos.md) |

## Uso rápido

```bash
python -m pip install -e ".[dev]"
python -m pytest

python -m pipeline.ingesta                       # baja CNE + OSM a data/raw/AAAA-MM-DD/
python -m pipeline.correr                        # todas las capas -> data/curated/ (ver docs/contrato-datos.md)
python -m pipeline.correr tests/fixtures/raw/2026-11-10   # prueba con datos de ejemplo, sin red
```

Para rutas reales hace falta un OSRM local con el PBF de México (ver `routing/osrm.py`).

Un GitHub Action (`.github/workflows/pipeline-diario.yml`) corre todo a las 19:00 (centro de México)
y publica `data/curated/` en la rama `datos`.

## Georreferencia y geocercas

- `geo.geocodificacion.Geocodificador`: dirección -> coordenadas y coordenadas -> dirección
  (Nominatim, solo México, caché y 1 petición/s). Si el texto ya son coordenadas
  ("19.43, -99.13", enlace de Google Maps, 19°25'57"N 99°07'59"W) no consulta nada.
- `geo.geocodificacion.IndiceAreas`: punto -> municipio/estado con los polígonos del INEGI
  (respeta huecos y multipolígonos).
- `geo.geocercas`: círculo, polígono, multipolígono y corredor; `distancia_borde_km` con signo;
  `geocercas_de_estaciones`, `corredor_de_ruta`, `zonas_de_referencia` (desde la coropleta de
  huachicol) y conversión a/desde GeoJSON.
- `geo.monitor.MonitorGeocercas`: eventos entrada/salida/permanencia con histéresis y filtro
  de precisión del GPS.
- `geo.indice.IndiceEspacial`: estaciones cercanas / k más cercanas sin revisar las ~13 mil.
- `web/geo/`: lo mismo del lado del navegador (`npm test` dentro de la carpeta).

## Datos sensibles

La capa de huachicol es solo referencia agregada (conteos por municipio y año con fuente).
No se guardan coordenadas de tomas, ductos ni detalles operativos.

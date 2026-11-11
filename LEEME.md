# Ojo de Dios · Gasolineras MX

Mapa interactivo nacional de gasolineras: precio por entidad y marca, estaciones,
gasolineras cercanas con geocerca, ruta entre estados con paradas de recarga óptimas,
surtido de pipas y tomas clandestinas reportadas (solo agregados por estado y
municipio, como referencia). Servidor en Python (FastAPI) + interfaz estática (D3),
con el diseño del mapa "Ojo de Dios".

## Arranque con Docker

    docker compose up --build

Abrir http://localhost:8000.

## Arranque en Windows sin Docker
Doble clic en `iniciar.bat`, o a mano:

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    .venv\Scripts\python scripts\construir_datos.py
    .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

Abrir http://127.0.0.1:8000 · API: http://127.0.0.1:8000/docs

## Datos
- Reales: corre el pipeline (`python -m pipeline.correr`, ver README.md y
  `docs/contrato-datos.md`). Deja `data/curated/estaciones.geojson` y el histórico de precios.
- Sin datos reales, `construir_datos.py` usa las estaciones SINTÉTICAS de
  `data/ejemplo/` y la interfaz muestra un aviso **DEMO** permanente.
- Tomas clandestinas: `data/manual/huachicol_estados.csv` y `huachicol_municipios.csv`,
  solo conteos con fuente y periodo. Nunca puntos de tomas ni ductos.

## Estructura
- `app/main.py`: servidor, API de datos del mapa y monta el motor en `/api/ruteo`.
- `app/static/`: interfaz (`index.html`, `estilos.css`, `app.js`, `siluetas.js`, D3 local).
- `scripts/construir_datos.py`: valida y genera `datos/procesados/*.json`.
- `pipeline/`: ingesta CNE, OSM, DENUE, Profeco; cruce y agregados.
- `routing/`: estaciones cercanas, ruta con recargas (Dijkstra sobre estación × combustible),
  surtido de pipas (VRP) y flotilla en tiempo real (WebSocket).
- `geo/`, `web/geo/`: distancias, geocercas y geocodificación.
- `capturas/`: capturas de la interfaz.

## Atajos
1–5 indicador · G gasolineras cerca · R ruta · P panorama · C capas · F fuentes · Esc cerrar.

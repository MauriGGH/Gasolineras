# Ojo de Dios · Robo vehicular MX

Aplicación web: mapa interactivo nacional de vehículos asegurados robados.
Servidor en Python (FastAPI) + interfaz estática (D3). Corre en localhost y se
despliega igual en un servidor.

## Arranque con Docker (recomendado para probar en otro equipo)

    git clone <url-del-repositorio>
    cd ojo-de-dios-robo-vehicular
    docker compose up --build

Abrir http://localhost:8000. Para detener: `Ctrl+C` y `docker compose down`.
Otro puerto: en PowerShell `$env:PUERTO=8080; docker compose up --build`.
Al construir la imagen se validan los datos; si una suma no cuadra, la construcción falla.

## Arranque en Windows sin Docker
Doble clic en `iniciar.bat`, o a mano:

    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt
    .venv\Scripts\python scripts\construir_datos.py
    .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

Abrir http://127.0.0.1:8000  ·  Documentación de la API: http://127.0.0.1:8000/docs

## Estructura
- `app/main.py`            servidor y API de solo lectura.
- `app/static/`            interfaz: `index.html`, `estilos.css`, `app.js`. `vendor/d3.min.js` es D3 7.9.0 local (sin CDN).
- `app/static/siluetas.js`  siluetas genéricas de vehículos por tipo (solo dibujos SVG, sin datos ni marcas).
- `Dockerfile`, `docker-compose.yml`  contenedor para localhost o servidor.
- `scripts/construir_datos.py`  valida los CSV contra los totales nacionales y genera los JSON.
- `datos/crudos/`          CSV transcritos del reporte AMIS de diciembre de 2025 y límites estatales.
- `datos/procesados/`      salida generada; no se edita a mano.

## API
| Ruta | Devuelve |
|---|---|
| `/api/salud` | si los datos procesados existen |
| `/api/datos` | nacional, entidades, submarcas, municipios |
| `/api/entidades/{nombre}` | ficha de una entidad |
| `/api/geo/estados` | límites estatales en GeoJSON |

## Fuentes
- AMIS, Centro Estadístico, «Robo de vehículos asegurados», reporte 2025-M12
  (https://centroestadisticoamis.mx/descarga-reporte-autos/).
- Vehículo más robado por entidad: AMIS vía prensa (marzo de 2026); sin periodo explícito. Dato secundario.
- `estados_mx.geojson`: límites generalizados de un repositorio público sin licencia declarada
  (github.com/angelnmara/geojson). Sustituir por el Marco Geoestadístico de INEGI antes de publicar.
- `lat_ref`/`lon_ref` de municipios: ubicación aproximada de la cabecera, solo para simbología.

## Pendientes conocidos
- Los conteos son absolutos; falta normalizar por parque vehicular (INEGI).
- Solo cubre vehículos asegurados. Falta la capa SESNSP (carpetas de investigación, nivel municipal).
- % de violencia y recuperación solo están cargados para 2025.
- La interfaz carga tipografías de Google Fonts; para un servidor sin salida a internet hay que alojarlas localmente.

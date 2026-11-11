# App Gasolineras · Fase 1: fuentes de datos, pipeline y ruteo

Fecha: 11 nov 2026. Alcance: investigación y diseño. El mapa todavía no se adapta (falta el repo de referencia).

## 1. Fuentes de datos

### Gasolineras y precios (núcleo)

| Fuente | Qué trae | Formato / acceso | Frecuencia | Notas |
|---|---|---|---|---|
| **CNE (antes CRE), precios por estación** | Permiso, nombre, dirección, producto (regular/premium/diésel), precio | XML: `https://publicacionexterna.azurewebsites.net/publicaciones/prices` (enlazado desde [cne.gob.mx](https://www.cne.gob.mx/ConsultaPrecios/GasolinasyDiesel/GasolinasyDiesel.html)) | Diario, 18:00 h (GMT-6) | La CRE se extinguió en 2025 y la CNE la sustituyó; el feed sigue en el mismo host. Llave natural: **número de permiso** (`PL/XXXXX/EXP/ES/AAAA`). |
| **CNE, catálogo de estaciones** | Permiso, nombre, coordenadas lat/lon | XML: `.../publicaciones/places` (endpoint histórico de la CRE) | Diario | Confirmar en la PC que sigue vivo; si no, se suple con DENUE + OSM. |
| **INEGI DENUE** | Establecimientos SCIAN 468411 (gasolineras) con lat/lon, razón social, municipio | CSV/SHP descarga masiva y API con token | Semestral | Buena fuente de respaldo para ubicación y para deducir la marca por razón social. |
| **OpenStreetMap** (`amenity=fuel`) | Ubicación, `brand`, `operator`, horarios, servicios | Overpass API o extracto PBF de Geofabrik (México) | Continuo | Mejor fuente para **marca** (Pemex, Oxxo Gas, G500, BP, Shell, Mobil, Chevron, Arco, Total, Repsol, etc.). Cobertura desigual. |
| **Profeco, "Quién es Quién en los combustibles"** | Ranking semanal de precios por marca/estación, estaciones que no dan litros completos | PDF/notas semanales | Semanal | Capa de calidad / "evitar cargar aquí"; se extrae a tabla. |

### Huachicol (solo referencia agregada)

- **Pemex**: reportes de tomas clandestinas por estado y, en algunos años, por municipio (informes anuales, respuestas por la Plataforma Nacional de Transparencia). Ojo: Pemex ha **reservado** parte de estos datos por seguridad nacional ([El Universal](https://www.eluniversal.com.mx/cartera/reservan-datos-de-huachicoleo-por-seguridad-nacional/)), así que la serie tendrá huecos.
- **Prensa**: notas con conteos por municipio, por ejemplo [El CEO, top 10 municipios 1T 2024](https://elceo.com/negocios/los-10-municipios-mas-afectados-por-el-huachicol-en-el-primer-trimestre-de-2024/), [Infobae, Hidalgo 2024](https://www.infobae.com/mexico/2025/02/06/hidalgo-numero-uno-en-huachicoleo-en-mexico-pese-a-disminucion-de-tomas-clandestinas-en-2024/), [El Imparcial, mapa 2026](https://www.elimparcial.com/mexico/2026/04/19/cada-50-minutos-perforan-un-ducto-de-pemex-en-mexico-el-mapa-actual-del-robo-de-combustible-y-gas-lp/), [Vanguardia, Coahuila 2025](https://vanguardia.com.mx/coahuila/encuentra-pemex-239-tomas-clandestinas-en-coahuila-durante-el-2025-casi-la-mitad-en-la-region-sureste-IF18955184).
- **Regla de diseño**: se publica solo como **coropleta por municipio/estado y año** (conteo de tomas reportadas, con fuente y fecha). Nada de puntos, ductos, horarios ni "puntos de venta"; la capa es informativa (zona de riesgo), igual que la capa de robos del mapa original.

### Red vial y geografía

| Fuente | Uso |
|---|---|
| **OSM México (Geofabrik PBF)** | Grafo vial para ruteo. |
| **OSRM** (o Valhalla/GraphHopper) | Motor de ruteo autoalojado en Docker sobre el PBF; da rutas, matrices de distancia/tiempo y map-matching. |
| **INEGI Red Nacional de Caminos (RNC)** | Red oficial con tipo de vía, cuotas y casetas; útil para costo por casetas en rutas entre estados. |
| **INEGI Marco Geoestadístico** | Polígonos de estados y municipios para agregar (huachicol, precios promedio). |

## 2. Pipeline de ingeniería de datos

```
 Ingesta (cron diario)        Limpieza / modelo              Servir
 ─────────────────────        ─────────────────              ──────
 CNE prices.xml  ─┐           normalizar marcas              GeoJSON / PMTiles
 CNE places.xml  ─┤──► raw ──► unir por permiso ──► curated ──► API (FastAPI)
 OSM fuel (PBF)  ─┤  (parquet)  match espacial OSM/DENUE      OSRM (ruteo)
 DENUE 468411    ─┤            (≤ 75 m + similitud de nombre)
 Profeco (sem.)  ─┤            validar precios (rangos, outliers)
 Huachicol (manual/anual) ─┘   agregar por municipio
```

1. **Ingesta**: scripts Python (`httpx` + `lxml`) guardan el archivo crudo con fecha (`data/raw/AAAA-MM-DD/`). Un GitHub Action con `cron` a las 19:00 CDMX baja el feed diario.
2. **Staging**: XML → Parquet. Tipos, coordenadas válidas dentro de México, producto estandarizado (`regular`, `premium`, `diesel`).
3. **Integración**:
   - Llave principal: permiso de la CNE.
   - Marca: OSM `brand` → si falta, reglas sobre nombre/razón social (DENUE) → si no, "Independiente".
   - Match espacial OSM ↔ CNE ↔ DENUE con un radio de 75 m y similitud de nombre (rapidfuzz).
4. **Calidad**: precio fuera de rango (p. ej. < 15 o > 35 MXN/l), estaciones sin coordenadas, duplicados por permiso. Reporte por corrida.
5. **Modelo final** (DuckDB + extensión spatial en local; PostGIS si va a servidor):
   - `dim_estacion(permiso, nombre, marca, lat, lon, municipio_cve, estado_cve)`
   - `fact_precio(permiso, fecha, producto, precio)` (histórico diario, permite tendencias)
   - `agg_huachicol(municipio_cve, anio, tomas, fuente)`
6. **Publicación**: `estaciones.geojson` (o PMTiles si pesa mucho) + precios del día; el front lo consume igual que hoy consume los datos de robos.

## 3. Ruteo y paradas óptimas

**a) Gasolinera más cercana a ti**: índice espacial (KD-tree/H3) para candidatas en un radio, luego OSRM `table` para ordenar por **tiempo real de manejo**, no por línea recta. Filtros: marca, producto, precio.

**b) Ruta A → B (p. ej. de un estado a otro)**: OSRM resuelve el camino con Contraction Hierarchies (más rápido que Dijkstra puro a escala país; si se quiere implementar propio, **A\*** con heurística de distancia haversine / velocidad máxima, que es admisible).

**c) Paradas de recarga óptimas por autonomía** (el "problema de la gasolinera"):
1. Tomar las estaciones a ≤ 2 km del corredor de la ruta (buffer) y proyectarlas sobre ella (km de avance).
2. Grafo dirigido: nodos = origen, estaciones, destino. Arista i→j si la distancia de manejo entre ellas es ≤ autonomía × margen (p. ej. 85 %, para no llegar en reserva).
3. Peso de la arista según el objetivo que elija el usuario:
   - mínimo de paradas → peso 1;
   - menor gasto → litros necesarios × precio en i (precio real de la CNE);
   - menor tiempo → tiempo de desvío + tiempo de carga.
4. **Dijkstra** sobre ese grafo da la secuencia óptima de paradas. Para el caso exacto de "cargar solo lo necesario donde es más barato" se extiende el estado a (estación, nivel de tanque discretizado), sigue siendo Dijkstra. Opcional: penalizar estaciones en municipios con mucho huachicol reportado o con mala calificación de Profeco.

**d) Ruta para quien surte (pipa / distribuidor con varias estaciones)**: esto ya no es camino más corto sino un problema de ruteo de vehículos (TSP/VRP con capacidad y ventanas de horario). Matriz de distancias con OSRM `table` + **Google OR-Tools** para el orden de visitas; Dijkstra/A* se usa en cada tramo.

## 4. Stack propuesto (provisional, se ajusta al diseño del repo de referencia)

- Datos: Python 3.12, DuckDB/GeoPandas, GitHub Actions para el cron.
- Ruteo: OSRM en Docker con el PBF de México (perfil `car`), API ligera en FastAPI que añade la lógica de paradas.
- Front: el del mapa de referencia, cambiando solo el tema (capas: estaciones por marca, precios, huachicol agregado, rutas).

## 5. Pendientes / riesgos

- Verificar en la PC que `/publicaciones/places` y `/prices` responden (desde este entorno la red está bloqueada, no pude descargarlos).
- Los datos de huachicol son parciales y heterogéneos; se documenta fuente y año de cada cifra.
- Licencias: OSM es ODbL (requiere atribución); datos de gobierno bajo Libre Uso MX.

## 6. Georreferenciación y geocercas

**Georreferenciación**
- Las coordenadas oficiales vienen del catálogo de la CNE; si faltan, de OSM/DENUE; como último recurso, geocodificación de la dirección con Nominatim (`geo/geocodificacion.py`).
- Geocodificación inversa (punto → municipio/estado) contra los polígonos del Marco Geoestadístico del INEGI, sin servicios externos. Con eso cada estación lleva `cve_mun` para filtros y agregados.
- Ubicación del usuario: geolocalización del navegador para "gasolineras cerca de mí".

**Geocercas** (`geo/geocercas.py`)
- Tipos: círculo (radio alrededor de mí o de un punto), polígono (municipio, colonia, zona dibujada) y corredor (franja de N km alrededor de una ruta).
- Usos: filtrar estaciones dentro de una zona; alertas de entrada/salida para la pipa (llegó a la estación, salió de la base); detección de desvío cuando el vehículo sale del corredor de su ruta; aviso al entrar a municipios con muchas tomas reportadas.
- Se exportan como GeoJSON para dibujarlas en el mapa.

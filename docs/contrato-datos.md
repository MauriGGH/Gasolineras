# Contrato de datos (versión 1)

Lo que deja `python -m pipeline.correr` en `data/curated/` y lo que pueden asumir el front y el ruteo.
En producción el cron diario lo publica en la rama `datos` del repo.

## Archivos

| Archivo | Para qué | Forma |
|---|---|---|
| `manifest.json` | Primer archivo que lee el front: fecha de los datos, archivos generados, pasos omitidos y reporte de calidad | objeto |
| `estaciones.geojson` | Capa de gasolineras (puntos) | FeatureCollection de `Point` |
| `estaciones.min.json` | Lo mismo, ligero para móvil | `{columnas: [...], filas: [[...]]}` |
| `precios_historico.csv` | Tendencias por estación | `fecha,permiso,producto,precio` (una fila por día y producto) |
| `precios_agregados.json` | Paneles y coropleta de precios | ver abajo |
| `precio_municipios_{regular,diesel}.geojson` | Coropleta de precio promedio (si hay polígonos municipales) | Polygon/MultiPolygon |
| `evitar_permisos.json` | Estaciones a excluir en planes de recarga (Profeco) | `{fecha, permisos: [...]}` |
| `huachicol_estados.json` | Tabla de referencia por estado, último año anual | ver abajo |
| `huachicol_estados_{petroliferos,gas_lp}.geojson` | Coropleta de referencia (si hay polígonos estatales) | Polygon/MultiPolygon |
| `calidad_AAAA-MM-DD.json` | Reporte de la corrida | objeto de conteos |

## `estaciones.geojson`, propiedades

| Campo | Tipo | Nota |
|---|---|---|
| `permiso` | string | Llave natural, `PL/XXXXX/EXP/ES/AAAA` (CNE) |
| `place_id` | string | Id del feed de la CNE |
| `nombre` | string | Como viene en la CNE |
| `marca` | string | Canónica: `Pemex`, `Oxxo Gas`, `G500`, `BP`, `Shell`, `Mobil`, `Chevron`, `Arco`, `TotalEnergies`, `Repsol`, `Hidrosina`, `Petro-7`, `Gulf`, ... o `Independiente` |
| `precios` | objeto | `{regular?, premium?, diesel?}` en MXN/l. Los precios fuera de 12–40 se quitan (quedan contados en calidad) |
| `horario` | string \| null | `opening_hours` de OSM |
| `osm_id` | string \| null | `node/123` o `way/456` |
| `cve_mun` | string \| null | CVEGEO INEGI de 5 dígitos |
| `municipio` | string \| null | Solo cuando se asignó por polígono |
| `cve_ent` | string \| null | 2 dígitos |
| `profeco` | objeto \| ausente | `{fecha, resultados[], evitar, fuente, url}` |

Coordenadas en `geometry.coordinates` como `[lon, lat]` (WGS84). `routing.recarga.planear_recargas`
recibe las propiedades más `lat`/`lon`; para convertir: `{**f["properties"], "lon": x, "lat": y}`.

## `precios_agregados.json`

```json
{
  "fecha": "2026-11-10",
  "nacional": {"regular": {"n": 12000, "promedio": 23.6, "mediana": 23.5, "min": 21.9, "max": 26.4}},
  "por_estado": {"09": {"regular": {...}, "diesel": {...}}},
  "por_municipio": {"09015": {...}},
  "por_marca": {"Pemex": {...}},
  "por_estado_marca": {"09|Pemex": {...}},
  "estaciones_por_marca": {"Pemex": 6000, "Independiente": 2500}
}
```

## Huachicol (solo referencia agregada)

`huachicol_estados.json`:

```json
{"petroliferos": {"anio": 2024, "periodo": "anual",
  "estados": {"13": {"estado": "Hidalgo", "tomas_reportadas": 2450, "fuente": "...", "url": "..."}}},
 "gas_lp": {...}}
```

- Nunca hay puntos, ductos ni coordenadas: solo conteos por estado o municipio, con fuente y periodo.
- Periodos distintos (anual, 1S, 1T) no se suman; `pipeline.huachicol` se niega a mezclarlos.
- Los insumos están en `data/manual/huachicol_estados.csv` y `huachicol_municipios.csv`. Las claves
  municipales se capturaron a mano: al generar la coropleta municipal se avisa si alguna no existe
  en los polígonos del INEGI.

## Insumos manuales

- `data/manual/profeco_quien_es_quien.csv`: una fila por estación y semana del "Quién es Quién en los
  combustibles". `resultado` ∈ `ok | litros_incompletos | se_nego | precio_alto | precio_bajo`. Las dos
  primeras negativas sacan a la estación de los planes de recarga durante 180 días.
- `data/geo/municipios.geojson` y `data/geo/estados.geojson` (no se versionan): Marco Geoestadístico
  del INEGI en WGS84. Con GDAL:
  `ogr2ogr -f GeoJSON -t_srs EPSG:4326 -simplify 0.001 data/geo/municipios.geojson 00mun.shp`
  (y `00ent.shp` para estados). Campos esperados: `CVEGEO`, `NOMGEO`, `CVE_ENT`.

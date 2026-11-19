# Sesión 46: clima en vivo por sucursal (GeoPandas + Open-Meteo)

Carpeta independiente del proyecto Gasolineras.

```bash
pip install geopandas requests pandas matplotlib reportlab
python crear_sucursales.py      # sucursales.geojson
python pipeline_clima.py        # clima_sucursales.csv
python generar_reporte.py       # Sesion_46_Apellido_Nombre.pdf
```

Con la capa del proyecto base: `python pipeline_clima.py ../data/ejemplo/estaciones.geojson salida.csv --id permiso`.
La portada se edita en el diccionario `PORTADA` de `generar_reporte.py`.

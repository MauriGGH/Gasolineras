"""Genera sucursales.geojson: red ilustrativa de 12 sucursales en ciudades de México.

Son puntos de práctica (ids S01..S12), no estaciones reales del proyecto base.
"""
import geopandas as gpd
from shapely.geometry import Point

SUCURSALES = [
    ("S01", "Sucursal Ciudad de México", 19.4326, -99.1332),
    ("S02", "Sucursal Guadalajara", 20.6597, -103.3496),
    ("S03", "Sucursal Monterrey", 25.6866, -100.3161),
    ("S04", "Sucursal Mérida", 20.9674, -89.5926),
    ("S05", "Sucursal Tijuana", 32.5149, -117.0382),
    ("S06", "Sucursal Cancún", 21.1619, -86.8515),
    ("S07", "Sucursal Puebla", 19.0414, -98.2063),
    ("S08", "Sucursal Querétaro", 20.5888, -100.3899),
    ("S09", "Sucursal Chihuahua", 28.6353, -106.0889),
    ("S10", "Sucursal Oaxaca", 17.0732, -96.7266),
    ("S11", "Sucursal Veracruz", 19.1738, -96.1342),
    ("S12", "Sucursal La Paz", 24.1426, -110.3128),
]

if __name__ == "__main__":
    gdf = gpd.GeoDataFrame(
        {"id": [s[0] for s in SUCURSALES], "nombre": [s[1] for s in SUCURSALES]},
        geometry=[Point(s[3], s[2]) for s in SUCURSALES],
        crs="EPSG:4326",
    )
    gdf.to_file("sucursales.geojson", driver="GeoJSON")
    print(f"{len(gdf)} sucursales escritas")

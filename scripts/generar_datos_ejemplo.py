"""Genera datos SINTÉTICOS para probar el ruteo sin OSRM ni el pipeline.

- data/ejemplo/red_vial.geojson: carreteras federales principales, simplificadas a
  tramos rectos entre ciudades (coordenadas reales aproximadas de las ciudades).
- data/ejemplo/estaciones.geojson: estaciones inventadas a lo largo de esas carreteras,
  con el mismo esquema que produce `pipeline.transformar` (permiso, nombre, marca,
  precios{regular,premium,diesel}, ...). Los permisos llevan el prefijo EJ/ para que
  nunca se confundan con permisos reales de la CNE.

    python scripts/generar_datos_ejemplo.py
"""
from __future__ import annotations

import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from geo.distancia import haversine_km  # noqa: E402

SALIDA = pathlib.Path(__file__).resolve().parents[1] / "data" / "ejemplo"

CIUDADES = {
    "CDMX": (19.4326, -99.1332), "Tepotzotlan": (19.7137, -99.2236), "San Juan del Rio": (20.3888, -99.9962),
    "Queretaro": (20.5888, -100.3899), "San Luis Potosi": (22.1565, -100.9855), "Matehuala": (23.6480, -100.6440),
    "Saltillo": (25.4232, -100.9925), "Monterrey": (25.6866, -100.3161), "Nuevo Laredo": (27.4779, -99.5496),
    "Torreon": (25.5428, -103.4068), "Celaya": (20.5235, -100.8157), "Irapuato": (20.6767, -101.3563),
    "Leon": (21.1250, -101.6860), "Lagos de Moreno": (21.3564, -101.9297), "Aguascalientes": (21.8853, -102.2916),
    "Zacatecas": (22.7709, -102.5833), "Toluca": (19.2826, -99.6557), "Atlacomulco": (19.7976, -99.8740),
    "Maravatio": (19.8936, -100.4428), "Morelia": (19.7060, -101.1950), "La Piedad": (20.3424, -102.0313),
    "Guadalajara": (20.6597, -103.3496), "Puebla": (19.0414, -98.2063), "Orizaba": (18.8506, -97.1036),
    "Cordoba": (18.8842, -96.9256), "Veracruz": (19.1738, -96.1342), "Pachuca": (20.1011, -98.7591),
    "Cuernavaca": (18.9242, -99.2216),
}

# (nombre, ciudades, velocidad km/h)
CARRETERAS = [
    ("Mex 57D", ["CDMX", "Tepotzotlan", "San Juan del Rio", "Queretaro", "San Luis Potosi", "Matehuala", "Saltillo", "Monterrey"], 95),
    ("Mex 85D", ["Monterrey", "Nuevo Laredo"], 95),
    ("Mex 40D", ["Saltillo", "Torreon"], 95),
    ("Mex 45D", ["Queretaro", "Celaya", "Irapuato", "Leon", "Lagos de Moreno", "Aguascalientes", "Zacatecas"], 90),
    ("Mex 49", ["San Luis Potosi", "Zacatecas"], 85),
    ("Mex 15D", ["CDMX", "Toluca", "Atlacomulco", "Maravatio", "Morelia", "La Piedad", "Guadalajara"], 95),
    ("Mex 90", ["Irapuato", "La Piedad"], 80),
    ("Mex 150D", ["CDMX", "Puebla", "Orizaba", "Cordoba", "Veracruz"], 95),
    ("Mex 85", ["CDMX", "Pachuca"], 85),
    ("Mex 95D", ["CDMX", "Cuernavaca"], 90),
]

MARCAS = [("Pemex", 0.42), ("Oxxo Gas", 0.12), ("G500", 0.08), ("BP", 0.07), ("Shell", 0.07), ("Mobil", 0.06),
          ("Hidrosina", 0.05), ("Chevron", 0.04), ("Arco", 0.03), ("TotalEnergies", 0.03), ("Independiente", 0.03)]
SOBREPRECIO = {"Pemex": 0.0, "Oxxo Gas": 0.3, "G500": -0.2, "BP": 0.5, "Shell": 0.6, "Mobil": 0.4, "Hidrosina": 0.1,
               "Chevron": 0.5, "Arco": 0.2, "TotalEnergies": 0.4, "Independiente": -0.4}
# Tramos con pocas estaciones (para que la autonomía importe)
TRAMOS_ESCASOS = {("San Luis Potosi", "Matehuala"), ("Matehuala", "Saltillo"), ("Saltillo", "Torreon")}


def interpolar(a, b, paso_km=5.0):
    d = haversine_km(a, b)
    n = max(1, int(d // paso_km))
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


def main(semilla: int = 7) -> None:
    rnd = random.Random(semilla)
    SALIDA.mkdir(parents=True, exist_ok=True)
    vias, estaciones = [], []
    marcas, pesos = zip(*MARCAS)
    for nombre, ciudades, vel in CARRETERAS:
        linea = []
        for c1, c2 in zip(ciudades, ciudades[1:]):
            tramo = interpolar(CIUDADES[c1], CIUDADES[c2])
            linea.extend(tramo if not linea else tramo[1:])
            d = haversine_km(CIUDADES[c1], CIUDADES[c2])
            escaso = (c1, c2) in TRAMOS_ESCASOS or (c2, c1) in TRAMOS_ESCASOS
            km = rnd.uniform(3, 10)
            while km < d - 3:
                t = km / d
                lat = CIUDADES[c1][0] + (CIUDADES[c2][0] - CIUDADES[c1][0]) * t + rnd.uniform(-0.004, 0.004)
                lon = CIUDADES[c1][1] + (CIUDADES[c2][1] - CIUDADES[c1][1]) * t + rnd.uniform(-0.004, 0.004)
                estaciones.append((lat, lon, rnd.choices(marcas, pesos)[0], f"{c1}-{c2}"))
                km += rnd.uniform(60, 110) if escaso else rnd.uniform(8, 25)
        vias.append({"type": "Feature", "properties": {"nombre": nombre, "vel_kmh": vel},
                     "geometry": {"type": "LineString", "coordinates": [[round(lon, 5), round(lat, 5)] for lat, lon in linea]}})
    # Estaciones urbanas alrededor de cada ciudad
    for ciudad, (lat0, lon0) in CIUDADES.items():
        for _ in range(rnd.randint(4, 12)):
            estaciones.append((lat0 + rnd.gauss(0, 0.03), lon0 + rnd.gauss(0, 0.03), rnd.choices(marcas, pesos)[0], ciudad))

    features = []
    for i, (lat, lon, marca, zona) in enumerate(estaciones, 1):
        base = 23.6 + SOBREPRECIO[marca] + rnd.gauss(0, 0.35)
        precios = {"regular": round(base, 2), "premium": round(base + 2.1 + rnd.gauss(0, 0.2), 2)}
        if rnd.random() < 0.85:
            precios["diesel"] = round(base + 1.3 + rnd.gauss(0, 0.25), 2)
        features.append({"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
                         "properties": {"permiso": f"EJ/{i:05d}/EXP/ES/2026", "place_id": f"ej{i}",
                                        "nombre": f"{marca} {zona} {i}", "marca": marca, "precios": precios,
                                        "horario": "24/7" if rnd.random() < 0.6 else None, "sintetico": True}})
    meta = {"aviso": "Datos sintéticos de ejemplo. No son estaciones reales."}
    (SALIDA / "red_vial.geojson").write_text(json.dumps({"type": "FeatureCollection", "metadata": meta, "features": vias},
                                                        ensure_ascii=False), encoding="utf-8")
    (SALIDA / "estaciones.geojson").write_text(json.dumps({"type": "FeatureCollection", "metadata": meta, "features": features},
                                                          ensure_ascii=False), encoding="utf-8")
    print(f"{len(vias)} carreteras, {len(features)} estaciones -> {SALIDA}")


if __name__ == "__main__":
    main()

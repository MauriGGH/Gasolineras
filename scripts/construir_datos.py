# -*- coding: utf-8 -*-
"""
construir_datos.py
Etapa 3 del pipeline: toma los CSV de datos/crudos, los valida contra los
totales nacionales publicados por AMIS y genera:
  - datos/procesados/datos_mapa.json   (lo que sirve la API en /api/datos)
  - datos/procesados/estados.geojson   (lo que sirve la API en /api/geo/estados)

Solo usa la biblioteca estándar; corre igual en Windows que en Linux:
    python scripts\\construir_datos.py
"""
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos" / "crudos"
PROCESADOS = RAIZ / "datos" / "procesados"

ANIOS = [2020, 2021, 2022, 2023, 2024, 2025]

# Totales nacionales del reporte AMIS de diciembre de 2025. Sirven de control:
# si la suma de las 32 entidades no coincide, el script se detiene.
NACIONAL_ROBOS = {2020: 64123, 2021: 59448, 2022: 58530, 2023: 60275, 2024: 63345, 2025: 54910}
NACIONAL_RECUPERADOS = {2020: 29876, 2021: 27295, 2022: 26094, 2023: 25908, 2024: 26450, 2025: 24321}
NACIONAL_VIOLENCIA_2025 = 30271        # unidades robadas con violencia
NACIONAL_PCT_VIOLENCIA_2025 = 55.1
NACIONAL_PCT_RECUPERACION_2025 = 44.3
TIPOS_2025 = [  # tipo, robos, % de recuperación (AMIS, misma fuente)
    {"tipo": "Automóviles", "robos": 29718, "pct_recuperacion": 45},
    {"tipo": "Pick up", "robos": 9319, "pct_recuperacion": 43},
    {"tipo": "Equipo pesado", "robos": 9060, "pct_recuperacion": 59},
    {"tipo": "Motocicletas", "robos": 6767, "pct_recuperacion": 24},
]

# El GeoJSON nombra "México" al Estado de México; se homologa al nombre de AMIS.
ALIAS_GEO = {"México": "Estado de México"}


def leer_csv(nombre):
    """Lee un CSV en UTF-8 y devuelve una lista de diccionarios."""
    with open(CRUDOS / nombre, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def area_con_signo(anillo):
    """Área plana con signo (fórmula del cordón). Positiva = antihorario."""
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def orientar_para_d3(geometria):
    """
    D3 interpreta los polígonos sobre la esfera y espera el anillo exterior en
    sentido horario (al revés que el estándar GeoJSON). Si llega al revés, el
    estado se dibuja como 'todo el planeta menos el estado'.
    """
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    for poligono in poligonos:
        for i, anillo in enumerate(poligono):
            antihorario = area_con_signo(anillo) > 0
            # exterior (i == 0) debe ir horario; los huecos, antihorario
            if (i == 0 and antihorario) or (i > 0 and not antihorario):
                anillo.reverse()
    return geometria


def main():
    # ---------- 1. Entidades ----------
    serie = leer_csv("amis_robo_entidad_2020_2025.csv")
    detalle = {r["entidad"]: r for r in leer_csv("amis_entidad_detalle_2025.csv")}
    lider = {r["entidad"]: r["vehiculo_mas_robado"] for r in leer_csv("amis_submarca_lider_por_entidad_prensa.csv")}

    entidades = {}
    for r in serie:
        n = r["entidad"]
        d = detalle[n]
        entidades[n] = {
            "robos": {a: int(r[str(a)]) for a in ANIOS},
            "recuperados": int(d["recuperados"]),
            "pct_violencia": float(d["pct_violencia"]),
            "pct_recuperacion": float(d["pct_recuperacion"]),
            "pct_motos": float(d["pct_motos"]),
            "pct_autos": float(d["pct_autos"]),
            "pct_pesado_pickup": float(d["pct_pesado_pickup"]),
            "vehiculo_lider": lider[n],
        }

    # ---------- 2. Validaciones (mide, no supongas) ----------
    errores = []
    if len(entidades) != 32:
        errores.append(f"Se esperaban 32 entidades y hay {len(entidades)}")
    for a in ANIOS:
        suma = sum(e["robos"][a] for e in entidades.values())
        if suma != NACIONAL_ROBOS[a]:
            errores.append(f"Robos {a}: suma de entidades {suma} != nacional {NACIONAL_ROBOS[a]}")
    suma_rec = sum(e["recuperados"] for e in entidades.values())
    if suma_rec != NACIONAL_RECUPERADOS[2025]:
        errores.append(f"Recuperados 2025: {suma_rec} != {NACIONAL_RECUPERADOS[2025]}")
    for n, e in entidades.items():
        calc = e["recuperados"] / e["robos"][2025] * 100
        if abs(calc - e["pct_recuperacion"]) > 0.02:
            errores.append(f"{n}: % recuperación {e['pct_recuperacion']} no cuadra con {calc:.2f}")
    if errores:
        print("VALIDACIÓN FALLIDA:")
        for e in errores:
            print("  -", e)
        sys.exit(1)
    print("Validación correcta: 32 entidades y sumas iguales a los totales nacionales 2020-2025.")

    # ---------- 3. Submarcas y municipios ----------
    submarcas = [{
        "submarca": r["submarca"], "tipo": r["tipo"], "robos": int(r["robos_2025"]),
        # vacío = la fuente no reporta el dato; se conserva como nulo, no se estima
        "pct_violencia": float(r["pct_violencia"]) if r["pct_violencia"] else None,
    } for r in leer_csv("amis_submarcas_2025.csv")]

    municipios = [{
        "municipio": r["municipio"], "entidad": r["entidad"], "robos": int(r["robos_2025"]),
        "pct_violencia": float(r["pct_violencia"]),
        "lat": float(r["lat_ref"]), "lon": float(r["lon_ref"]),   # ubicación referencial
    } for r in leer_csv("amis_municipios_2025.csv")]
    for m in municipios:
        if m["entidad"] not in entidades:
            sys.exit(f"Municipio {m['municipio']}: entidad desconocida {m['entidad']}")

    datos = {
        "anios": ANIOS,
        "nacional": {
            "robos": NACIONAL_ROBOS, "recuperados": NACIONAL_RECUPERADOS,
            "violencia_2025": NACIONAL_VIOLENCIA_2025,
            "pct_violencia_2025": NACIONAL_PCT_VIOLENCIA_2025,
            "pct_recuperacion_2025": NACIONAL_PCT_RECUPERACION_2025,
            "tipos_2025": TIPOS_2025,
        },
        "entidades": entidades, "submarcas": submarcas, "municipios": municipios,
    }

    # ---------- 4. Geometría ----------
    with open(CRUDOS / "estados_mx.geojson", encoding="utf-8") as f:
        geo = json.load(f)
    for ft in geo["features"]:
        nombre = ALIAS_GEO.get(ft["properties"]["name"], ft["properties"]["name"])
        if nombre not in entidades:
            sys.exit(f"El GeoJSON trae '{nombre}', que no existe en los datos")
        # clave corta (JAL, COL...) tomada del código ISO 3166-2 del archivo; se usa como etiqueta
        ft["properties"] = {"nombre": nombre, "clave": ft["properties"]["id"][3:]}
        orientar_para_d3(ft["geometry"])
    if len(geo["features"]) != 32:
        sys.exit("El GeoJSON no tiene 32 entidades")

    # ---------- 5. Salidas ----------
    PROCESADOS.mkdir(parents=True, exist_ok=True)
    with open(PROCESADOS / "datos_mapa.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)

    with open(PROCESADOS / "estados.geojson", "w", encoding="utf-8") as f:
        json.dump(geo, f, ensure_ascii=False, separators=(",", ":"))
    print("Generados: datos/procesados/datos_mapa.json y datos/procesados/estados.geojson")


if __name__ == "__main__":
    main()

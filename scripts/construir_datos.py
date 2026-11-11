# -*- coding: utf-8 -*-
"""
construir_datos.py
Última etapa del pipeline: toma lo que deja `python -m pipeline.correr` en data/curated/
(ver docs/contrato-datos.md), lo agrega por entidad y genera lo que sirve la API del mapa:
  - datos/procesados/datos_mapa.json   (/api/datos)
  - datos/procesados/estaciones.json   (/api/estaciones, formato compacto)
  - datos/procesados/estados.geojson   (/api/geo/estados)

De dónde salen las estaciones, en este orden:
  1. data/curated/ local (después de `python -m pipeline.correr`).
  2. La rama `datos` del repositorio, que el cron diario actualiza (se baja a data/curated/).
  3. Las estaciones SINTÉTICAS de data/ejemplo/, marcadas como demostración (aviso DEMO).

Línea de tiempo: con hasta MAX_DIARIOS días de histórico, un corte por día; con más,
un corte por semana (promedio de la semana, etiquetado con su último día).

Solo usa la biblioteca estándar:
    python scripts\\construir_datos.py              # local -> rama datos -> demo
    python scripts\\construir_datos.py --sin-red    # no intenta bajar la rama datos
    python scripts\\construir_datos.py --actualizar # vuelve a bajar la rama datos aunque haya copia local
"""
import csv
import datetime as dt
import json
import os
import statistics
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from geo.distancia import punto_en_poligono  # noqa: E402

CRUDOS = RAIZ / "datos" / "crudos"
PROCESADOS = RAIZ / "datos" / "procesados"
CURADOS = RAIZ / "data" / "curated"
EJEMPLO = RAIZ / "data" / "ejemplo"
MANUAL = RAIZ / "data" / "manual"

PRODUCTOS = ["regular", "premium", "diesel"]
MAX_DIARIOS = 45         # hasta aquí, un corte por día
MAX_SEMANAS = 104        # después, cortes semanales (dos años como máximo)
# Rama `datos` publicada por .github/workflows/pipeline-diario.yml
DATOS_URL = os.environ.get("GAS_DATOS_URL", "https://raw.githubusercontent.com/MauriGGH/Gasolineras/datos/")
ARCHIVOS_REMOTOS = ("manifest.json", "estaciones.geojson", "precios_historico.csv", "evitar_permisos.json")

# Clave INEGI de entidad -> nombre usado en el mapa y código ISO 3166-2 del GeoJSON
ENTIDADES = {
    "01": ("Aguascalientes", "AGU"), "02": ("Baja California", "BCN"), "03": ("Baja California Sur", "BCS"),
    "04": ("Campeche", "CAM"), "05": ("Coahuila", "COA"), "06": ("Colima", "COL"), "07": ("Chiapas", "CHP"),
    "08": ("Chihuahua", "CHH"), "09": ("Ciudad de México", "CMX"), "10": ("Durango", "DUR"),
    "11": ("Guanajuato", "GUA"), "12": ("Guerrero", "GRO"), "13": ("Hidalgo", "HID"), "14": ("Jalisco", "JAL"),
    "15": ("Estado de México", "MEX"), "16": ("Michoacán", "MIC"), "17": ("Morelos", "MOR"), "18": ("Nayarit", "NAY"),
    "19": ("Nuevo León", "NLE"), "20": ("Oaxaca", "OAX"), "21": ("Puebla", "PUE"), "22": ("Querétaro", "QUE"),
    "23": ("Quintana Roo", "ROO"), "24": ("San Luis Potosí", "SLP"), "25": ("Sinaloa", "SIN"), "26": ("Sonora", "SON"),
    "27": ("Tabasco", "TAB"), "28": ("Tamaulipas", "TAM"), "29": ("Tlaxcala", "TLA"), "30": ("Veracruz", "VER"),
    "31": ("Yucatán", "YUC"), "32": ("Zacatecas", "ZAC"),
}
POR_ISO = {iso: (cve, nombre) for cve, (nombre, iso) in ENTIDADES.items()}


def area_con_signo(anillo):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(anillo, anillo[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2.0


def orientar_para_d3(geometria):
    """D3 espera el anillo exterior en sentido horario (al revés que el estándar GeoJSON)."""
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    for poligono in poligonos:
        for i, anillo in enumerate(poligono):
            antihorario = area_con_signo(anillo) > 0
            if (i == 0 and antihorario) or (i > 0 and not antihorario):
                anillo.reverse()
    return geometria


# ---------------- geometría de entidades ----------------
def cargar_estados():
    with open(CRUDOS / "estados_mx.geojson", encoding="utf-8") as f:
        geo = json.load(f)
    poligonos = {}
    for ft in geo["features"]:
        iso = ft["properties"]["id"][3:]
        if iso not in POR_ISO:
            sys.exit(f"El GeoJSON trae la clave {iso}, que no está en ENTIDADES")
        cve, nombre = POR_ISO[iso]
        g = ft["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        anillos = [[(lat, lon) for lon, lat in p[0]] for p in polys]
        cajas = [(min(a[0] for a in r), min(a[1] for a in r), max(a[0] for a in r), max(a[1] for a in r)) for r in anillos]
        poligonos[nombre] = list(zip(anillos, cajas))
        ft["properties"] = {"nombre": nombre, "clave": iso, "cve": cve}
        orientar_para_d3(g)
    if len(geo["features"]) != 32:
        sys.exit("El GeoJSON no tiene 32 entidades")
    return geo, poligonos


def entidad_de(lat, lon, poligonos):
    for nombre, partes in poligonos.items():
        for anillo, (a, b, c, d) in partes:
            if a <= lat <= c and b <= lon <= d and punto_en_poligono((lat, lon), anillo):
                return nombre
    return None


# ---------------- insumos ----------------
def bajar_rama_datos(base=DATOS_URL, destino=CURADOS, timeout=60):
    """Baja la salida del cron (rama `datos`) a data/curated/. Devuelve True si quedó completa."""
    destino.mkdir(parents=True, exist_ok=True)
    bajados = {}
    for nombre in ARCHIVOS_REMOTOS:
        req = urllib.request.Request(base + nombre, headers={"User-Agent": "gasolineras-mapa/0.2"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                bajados[nombre] = r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            if nombre in ("manifest.json", "estaciones.geojson"):
                print(f"  sin datos publicados en {base} ({nombre}: {e})")
                return False
            print(f"  aviso: no se pudo bajar {nombre} ({e})")
    for nombre, contenido in bajados.items():   # se escribe todo junto para no mezclar corridas
        (destino / nombre).write_bytes(contenido)
    print(f"Datos reales bajados de la rama datos: {', '.join(bajados)}")
    return True


def leer_manifest():
    ruta = CURADOS / "manifest.json"
    if not ruta.exists():
        return {}
    m = json.loads(ruta.read_text(encoding="utf-8"))
    m.setdefault("fecha_datos", m.get("fecha"))     # versiones anteriores del manifiesto
    return m


def cargar_estaciones(red=True, actualizar=False):
    """Devuelve (estaciones, manifest, origen) con origen en {"local", "rama datos", "demo"}."""
    real = CURADOS / "estaciones.geojson"
    origen = "local"
    if red and (actualizar or not real.exists()):
        if bajar_rama_datos():
            origen = "rama datos"
    if real.exists():
        ruta, demo = real, False
    else:
        ruta, demo, origen = EJEMPLO / "estaciones.geojson", True, "demo"
    with open(ruta, encoding="utf-8") as f:
        fc = json.load(f)
    manifest = {} if demo else leer_manifest()
    salida = []
    for ft in fc["features"]:
        g = ft.get("geometry") or {}
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        salida.append({**ft["properties"], "lat": float(lat), "lon": float(lon)})
    print(f"Estaciones: {len(salida)} desde {ruta.relative_to(RAIZ)} ({origen})" + (" SINTÉTICAS" if demo else ""))
    return salida, manifest, origen


def cargar_evitar():
    ruta = CURADOS / "evitar_permisos.json"
    if not ruta.exists():
        return set()
    return set(json.loads(ruta.read_text(encoding="utf-8")).get("permisos", []))


def cargar_historico(grupos_de_permiso, ruta=None):
    """precios_historico.csv -> {fecha: {grupo: {producto: [precios]}}}.

    `grupos_de_permiso` da, para cada permiso, los grupos donde cuenta su precio
    (entidad, "m:<marca>"); todas cuentan además en "__nac".
    """
    ruta = ruta or CURADOS / "precios_historico.csv"
    if not ruta.exists():
        return {}
    por_fecha = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with open(ruta, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                precio = float(r["precio"])
            except (TypeError, ValueError):
                continue
            if r["producto"] not in PRODUCTOS:
                continue
            por_fecha[r["fecha"]]["__nac"][r["producto"]].append(precio)
            for g in grupos_de_permiso.get(r["permiso"], ()):
                por_fecha[r["fecha"]][g][r["producto"]].append(precio)
    return por_fecha


def cortes(hist, max_diarios=MAX_DIARIOS, max_semanas=MAX_SEMANAS):
    """Agrupa el histórico diario en cortes para la línea de tiempo.

    Devuelve (fechas, hist_por_corte, tipo). Con <= max_diarios días: un corte por día.
    Con más: uno por semana ISO, que junta los precios de todos sus días y se etiqueta
    con el último día con datos de esa semana.
    """
    dias = sorted(hist)
    if len(dias) <= max_diarios:
        return dias, hist, "diario"
    semanas = defaultdict(list)
    for d in dias:
        a, s, _ = dt.date.fromisoformat(d).isocalendar()
        semanas[(a, s)].append(d)
    claves = sorted(semanas)[-max_semanas:]
    fechas, agrupado = [], {}
    for k in claves:
        etiqueta = semanas[k][-1]
        fechas.append(etiqueta)
        junto = defaultdict(lambda: defaultdict(list))
        for d in semanas[k]:
            for g, prods in hist[d].items():
                for p, v in prods.items():
                    junto[g][p].extend(v)
        agrupado[etiqueta] = junto
    return fechas, agrupado, "semanal"


def leer_csv(ruta):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cargar_huachicol():
    """Solo referencia agregada: por estado (último año anual) y focos municipales con su periodo."""
    filas = leer_csv(MANUAL / "huachicol_estados.csv")
    por_estado = defaultdict(dict)
    historia = defaultdict(list)    # todas las cifras del estado, sin sumar periodos distintos
    for r in filas:
        historia[ENTIDADES[r["cve_ent"].zfill(2)][0]].append({
            "anio": int(r["anio"]), "periodo": r["periodo"], "producto": r["producto"],
            "tomas": int(r["tomas_reportadas"]), "fuente": r["fuente"], "url": r["url"], "nota": r.get("nota") or ""})
    for lst in historia.values():
        lst.sort(key=lambda h: (-h["anio"], h["producto"], h["periodo"]))
    resumen = {}
    for producto in ("petroliferos", "gas_lp"):
        anuales = [r for r in filas if r["producto"] == producto and r["periodo"] == "anual"]
        if not anuales:
            continue
        anio = max(int(r["anio"]) for r in anuales)
        sel = [r for r in anuales if int(r["anio"]) == anio]
        for r in sel:
            nombre = ENTIDADES[r["cve_ent"].zfill(2)][0]
            por_estado[nombre][producto] = {"tomas": int(r["tomas_reportadas"]), "anio": anio, "periodo": "anual",
                                            "fuente": r["fuente"], "url": r["url"]}
        resumen[producto] = {"anio": anio, "periodo": "anual", "estados_con_dato": len(sel),
                             "suma_reportada": sum(int(r["tomas_reportadas"]) for r in sel),
                             "fuentes": sorted({r["fuente"] for r in sel})}

    cabeceras = {r["cve_mun"].zfill(5): r for r in leer_csv(CRUDOS / "municipios_cabecera_ref.csv")}
    ultimos = {}
    for r in leer_csv(MANUAL / "huachicol_municipios.csv"):
        clave = r["cve_mun"].zfill(5)
        llave = (int(r["anio"]), r["periodo"])
        if clave not in ultimos or llave > ultimos[clave][0]:
            ultimos[clave] = (llave, r)
    municipios = []
    for clave, (_, r) in ultimos.items():
        cab = cabeceras.get(clave)
        if not cab:
            print(f"  aviso: {r['municipio']} ({clave}) no tiene cabecera de referencia; no se dibuja")
            continue
        municipios.append({"cve_mun": clave, "municipio": r["municipio"], "entidad": ENTIDADES[clave[:2]][0],
                           "tomas": int(r["tomas_reportadas"]), "anio": int(r["anio"]), "periodo": r["periodo"],
                           "producto": r["producto"], "fuente": r["fuente"], "url": r["url"],
                           "lat": float(cab["lat_ref"]), "lon": float(cab["lon_ref"])})
    municipios.sort(key=lambda m: -m["tomas"])
    return dict(por_estado), resumen, municipios, dict(historia)


# ---------------- agregados ----------------
def resumen_precios(valores):
    if not valores:
        return None
    return {"prom": round(statistics.fmean(valores), 2), "mediana": round(statistics.median(valores), 2),
            "min": round(min(valores), 2), "max": round(max(valores), 2), "n": len(valores)}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    geo, poligonos = cargar_estados()
    estaciones, manifest, origen = cargar_estaciones(red="--sin-red" not in argv, actualizar="--actualizar" in argv)
    demo = origen == "demo"
    fecha = manifest.get("fecha_datos")
    evitar = cargar_evitar() if not demo else set()
    for e in estaciones:
        e["evitar"] = e.get("permiso") in evitar or bool((e.get("profeco") or {}).get("evitar"))
    nombres = [ENTIDADES[c][0] for c in sorted(ENTIDADES)]

    fuera = 0
    for e in estaciones:
        cve = str(e.get("cve_ent") or (e.get("cve_mun") or "")[:2] or "")
        e["entidad"] = ENTIDADES[cve][0] if cve in ENTIDADES else entidad_de(e["lat"], e["lon"], poligonos)
        fuera += e["entidad"] is None
    if fuera:
        print(f"  aviso: {fuera} estaciones no cayeron en ninguna entidad (costa o límites generalizados)")

    por_ent = defaultdict(list)
    for e in estaciones:
        if e["entidad"]:
            por_ent[e["entidad"]].append(e)

    marca_de = lambda e: e.get("marca") or "Independiente"
    grupos = {e.get("permiso"): [g for g in (e["entidad"], "m:" + marca_de(e)) if g] for e in estaciones}
    hist = {} if demo else cargar_historico(grupos)
    fechas, hist, tipo_corte = cortes(hist)
    if not fechas:
        fechas, tipo_corte = [fecha or "ejemplo"], "unico"
        precios_de = lambda lst, p: [e["precios"][p] for e in lst if (e.get("precios") or {}).get(p)]
        por_marca_lst = defaultdict(list)
        for e in estaciones:
            por_marca_lst["m:" + marca_de(e)].append(e)
        hist = {fechas[0]: {"__nac": {p: precios_de(estaciones, p) for p in PRODUCTOS},
                            **{n: {p: precios_de(lst, p) for p in PRODUCTOS} for n, lst in por_ent.items()},
                            **{g: {p: precios_de(lst, p) for p in PRODUCTOS} for g, lst in por_marca_lst.items()}}}
    serie = lambda clave, p: [round(statistics.fmean(v), 2) if (v := hist[f].get(clave, {}).get(p)) else None for f in fechas]

    huach_estados, huach_resumen, huach_mun, huach_hist = cargar_huachicol()
    conteo_marcas = Counter(e.get("marca") or "Independiente" for e in estaciones)

    entidades = {}
    for n in nombres:
        lst = por_ent.get(n, [])
        marcas = Counter(e.get("marca") or "Independiente" for e in lst)
        baratas = {}
        for p in PRODUCTOS:
            con_precio = sorted((e for e in lst if (e.get("precios") or {}).get(p)), key=lambda e: e["precios"][p])
            baratas[p] = [{"nombre": e.get("nombre"), "marca": e.get("marca"), "permiso": e.get("permiso"),
                           "precio": e["precios"][p], "lat": e["lat"], "lon": e["lon"]} for e in con_precio[:6]]
        entidades[n] = {
            "cve": next(c for c, (x, _) in ENTIDADES.items() if x == n),
            "estaciones": len(lst),
            "precio": {p: resumen_precios([e["precios"][p] for e in lst if (e.get("precios") or {}).get(p)]) for p in PRODUCTOS},
            "serie": {p: serie(n, p) for p in PRODUCTOS},
            "marcas": [{"marca": m, "n": c} for m, c in marcas.most_common()],
            "marca_lider": marcas.most_common(1)[0][0] if marcas else None,
            "pct_pemex": round(marcas.get("Pemex", 0) / len(lst) * 100, 1) if lst else None,
            "baratas": baratas,
            "huachicol": huach_estados.get(n, {}),
            "huachicol_historia": huach_hist.get(n, []),
            "profeco_evitar": sum(1 for e in lst if e["evitar"]),
        }

    marcas = []
    for m, c in conteo_marcas.most_common():
        lst = [e for e in estaciones if (e.get("marca") or "Independiente") == m]
        marcas.append({"marca": m, "estaciones": c,
                       "precio": {p: (r["prom"] if (r := resumen_precios([e["precios"][p] for e in lst if (e.get("precios") or {}).get(p)])) else None) for p in PRODUCTOS},
                       "serie": {p: serie("m:" + m, p) for p in PRODUCTOS},
                       "profeco_evitar": sum(1 for e in lst if e["evitar"]),
                       "lider_en": [n for n in nombres if entidades[n]["marca_lider"] == m]})

    datos = {
        "demo": demo,
        "aviso": "Estaciones SINTÉTICAS de ejemplo: corre el pipeline para ver datos reales." if demo else None,
        "origen": origen,
        "corte": fechas[-1],
        "fechas": fechas,
        "tipo_corte": tipo_corte,
        "manifest": {k: manifest.get(k) for k in ("fecha_datos", "generado", "pasos_omitidos", "calidad")} if manifest else None,
        "productos": PRODUCTOS,
        "nacional": {
            "estaciones": len(estaciones),
            "precio": {p: resumen_precios([e["precios"][p] for e in estaciones if (e.get("precios") or {}).get(p)]) for p in PRODUCTOS},
            "serie": {p: serie("__nac", p) for p in PRODUCTOS},
            "marcas": [{"marca": m, "n": c} for m, c in conteo_marcas.most_common()],
            "pct_pemex": round(conteo_marcas.get("Pemex", 0) / len(estaciones) * 100, 1) if estaciones else None,
            "huachicol": huach_resumen,
            "profeco_evitar": sum(1 for e in estaciones if e["evitar"]),
        },
        "entidades": entidades,
        "marcas": marcas,
        "municipios": huach_mun,
    }

    # ---------- validaciones: mide, no supongas ----------
    errores = []
    if sum(v["estaciones"] for v in entidades.values()) != len(estaciones) - fuera:
        errores.append("La suma de estaciones por entidad no cuadra con el total")
    for p in PRODUCTOS:
        r = datos["nacional"]["precio"][p]
        if r and not (12 <= r["min"] and r["max"] <= 40):
            errores.append(f"{p}: precios fuera de 12–40 MXN/l ({r['min']}–{r['max']})")
    if errores:
        print("VALIDACIÓN FALLIDA:")
        for e in errores:
            print("  -", e)
        sys.exit(1)

    cols = ["permiso", "nombre", "marca", "lat", "lon", "regular", "premium", "diesel", "entidad", "horario", "evitar"]
    filas = [[e.get("permiso"), e.get("nombre"), e.get("marca") or "Independiente", round(e["lat"], 5), round(e["lon"], 5),
              *[(e.get("precios") or {}).get(p) for p in PRODUCTOS], e["entidad"], e.get("horario"), 1 if e["evitar"] else 0]
             for e in estaciones]

    PROCESADOS.mkdir(parents=True, exist_ok=True)
    (PROCESADOS / "datos_mapa.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    (PROCESADOS / "estaciones.json").write_text(json.dumps({"columnas": cols, "filas": filas}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (PROCESADOS / "estados.geojson").write_text(json.dumps(geo, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Validación correcta: {len(estaciones)} estaciones, {sum(1 for v in entidades.values() if v['estaciones'])} entidades con estaciones, "
          f"{len(fechas)} corte(s) ({tipo_corte}), {len(huach_mun)} focos municipales de referencia, origen: {origen}.")
    print("Generados: datos/procesados/datos_mapa.json, estaciones.json y estados.geojson")


if __name__ == "__main__":
    main()

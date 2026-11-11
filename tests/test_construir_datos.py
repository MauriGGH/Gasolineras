"""scripts/construir_datos.py: cortes de la línea de tiempo, huachicol y origen de los datos."""
import csv
import datetime as dt
import importlib.util
import json
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("construir_datos", RAIZ / "scripts" / "construir_datos.py")
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)


def _hist(dias):
    base = dt.date(2026, 1, 1)
    return {(base + dt.timedelta(d)).isoformat(): {"__nac": {"regular": [20.0 + d / 100]}} for d in range(dias)}


def test_cortes_diarios_hasta_el_limite():
    fechas, h, tipo = cd.cortes(_hist(45))
    assert tipo == "diario" and len(fechas) == 45 and fechas[0] == "2026-01-01"


def test_cortes_semanales_juntan_los_dias():
    fechas, h, tipo = cd.cortes(_hist(70))
    assert tipo == "semanal"
    # 2026-01-01 es jueves: la primera semana ISO tiene 4 días (jue-dom), etiquetada con el domingo
    assert fechas[0] == "2026-01-04" and len(h["2026-01-04"]["__nac"]["regular"]) == 4
    assert fechas[-1] == "2026-03-11"                                 # último día con datos
    assert sum(len(h[f]["__nac"]["regular"]) for f in fechas) == 70   # ningún día se pierde


def test_cortes_semanales_respetan_el_tope():
    fechas, _, _ = cd.cortes(_hist(400), max_semanas=10)
    assert len(fechas) == 10


def test_historico_agrupa_por_entidad_y_marca(tmp_path):
    ruta = tmp_path / "h.csv"
    with ruta.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "permiso", "producto", "precio"])
        w.writerows([["2026-11-10", "A", "regular", "23"], ["2026-11-10", "B", "regular", "25"],
                     ["2026-11-10", "B", "gas", "1"], ["2026-11-10", "C", "regular", "x"]])
    h = cd.cargar_historico({"A": ["Hidalgo", "m:Pemex"], "B": ["Hidalgo", "m:BP"]}, ruta)
    d = h["2026-11-10"]
    assert d["__nac"]["regular"] == [23.0, 25.0] and d["Hidalgo"]["regular"] == [23.0, 25.0]
    assert d["m:Pemex"]["regular"] == [23.0] and "gas" not in d["__nac"]


def test_huachicol_no_suma_fuentes_y_elige_anio_con_cobertura():
    por_estado, resumen, municipios, historia = cd.cargar_huachicol()
    pet = resumen["petroliferos"]
    assert pet["anio"] == 2024 and pet["estados_con_dato"] >= 9
    assert por_estado["Hidalgo"]["petroliferos"]["tomas"] == 2450          # no 2450 + otra fuente
    assert any(h["anio"] == 2020 for h in historia["Hidalgo"])
    # cada municipio con cifra tiene cabecera de referencia y se dibuja una sola vez
    with (RAIZ / "data" / "manual" / "huachicol_municipios.csv").open(encoding="utf-8") as f:
        claves = {r["cve_mun"].zfill(5) for r in csv.DictReader(f)}
    assert {m["cve_mun"] for m in municipios} == claves
    cuautepec = next(m for m in municipios if m["cve_mun"] == "13016")
    assert (cuautepec["anio"], cuautepec["periodo"]) == (2025, "anual")


def test_bajar_rama_datos_sin_red_no_rompe(tmp_path):
    assert cd.bajar_rama_datos("http://127.0.0.1:9/", tmp_path, timeout=2) is False
    assert not list(tmp_path.iterdir())          # no deja archivos a medias


def test_bajar_rama_datos_desde_carpeta(tmp_path):
    origen = tmp_path / "datos"
    origen.mkdir()
    (origen / "manifest.json").write_text(json.dumps({"fecha_datos": "2026-11-10"}))
    (origen / "estaciones.geojson").write_text('{"type":"FeatureCollection","features":[]}')
    destino = tmp_path / "curated"
    assert cd.bajar_rama_datos(origen.as_uri() + "/", destino) is True
    assert sorted(p.name for p in destino.iterdir()) == ["estaciones.geojson", "manifest.json"]

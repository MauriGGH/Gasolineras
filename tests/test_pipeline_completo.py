"""Corrida de punta a punta con datos de ejemplo (tests/fixtures) y pruebas de los módulos nuevos."""
import datetime as dt
import json
import pathlib
import shutil

import pytest

from pipeline import agregados, correr, huachicol, municipios, profeco
from pipeline.marcas import normalizar_marca, similitud_nombre
from pipeline.transformar import escribir_historico

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
HOY = dt.date(2026, 11, 11)


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    for sub in ("raw", "geo", "manual"):
        shutil.copytree(FIXTURES / sub, d / sub)
    return d


def _por_permiso(data):
    fc = json.loads((data / "curated" / "estaciones.geojson").read_text(encoding="utf-8"))
    return {f["properties"]["permiso"]: f for f in fc["features"]}


def test_corrida_completa(data):
    m = correr.correr(data / "raw" / "2026-11-10", data, HOY)
    cal = m["calidad"]
    assert cal["cne_total"] == 5
    assert cal["coordenadas_invalidas"] == 1          # lat/lon invertidas
    assert cal["estaciones_publicadas"] == 4
    assert cal["precio_dudoso"] == 1                  # diésel a 2.5
    assert cal["match_osm"] == 2 and cal["match_denue"] == 1
    assert cal["municipio_por_denue"] == 1 and cal["municipio_por_poligono"] == 3
    assert m["pasos_omitidos"] == []

    est = _por_permiso(data)
    oxxo, pinos, roble, total = (est[f"PL/{n}/EXP/ES/{a}"]["properties"]
                                 for n, a in ((100, 2015), (101, 2016), (102, 2017), (104, 2018)))
    assert oxxo["marca"] == "Oxxo Gas" and oxxo["cve_mun"] == "09015" and oxxo["cve_ent"] == "09"
    assert pinos["marca"] == "Shell" and pinos["horario"] == "24/7" and pinos["cve_mun"] == "09015"
    assert pinos["precios"] == {"regular": 23.99}
    # OSM a ~160 m, aceptado por similitud de nombre
    assert roble["marca"] == "Pemex" and roble["osm_id"] == "way/2" and roble["cve_mun"] == "13048"
    assert roble["profeco"]["evitar"] is True
    assert total["marca"] == "Independiente"          # "Servicio Total" no es TotalEnergies

    curated = data / "curated"
    assert json.loads((curated / "evitar_permisos.json").read_text())["permisos"] == ["PL/102/EXP/ES/2017"]
    mini = json.loads((curated / "estaciones.min.json").read_text(encoding="utf-8"))
    assert len(mini["filas"]) == 4 and mini["columnas"][2] == "marca"
    agg = json.loads((curated / "precios_agregados.json").read_text(encoding="utf-8"))
    assert agg["por_estado"]["09"]["regular"]["promedio"] == pytest.approx((23.49 + 23.99) / 2, abs=0.01)
    assert agg["por_marca"]["Pemex"]["premium"]["n"] == 1
    hu = json.loads((curated / "huachicol_estados.json").read_text(encoding="utf-8"))
    assert hu["petroliferos"]["anio"] == 2024 and hu["petroliferos"]["estados"]["13"]["tomas_reportadas"] == 2450
    coro = json.loads((curated / "huachicol_estados_petroliferos.geojson").read_text(encoding="utf-8"))
    assert [f["properties"]["CVE_ENT"] for f in coro["features"]] == ["13"]
    for nombre in m["archivos"]:
        assert (curated / nombre).exists()
    for prop in ("geometry",):  # la capa de huachicol nunca lleva puntos
        assert all(f[prop]["type"] in ("Polygon", "MultiPolygon") for f in coro["features"])


def test_recorrida_no_duplica_historico(data):
    raw = data / "raw" / "2026-11-10"
    correr.correr(raw, data, HOY)
    correr.correr(raw, data, HOY)
    filas = (data / "curated" / "precios_historico.csv").read_text().strip().splitlines()
    assert len(filas) == 1 + 7  # encabezado + 7 precios válidos


def test_historico_conserva_otras_fechas(tmp_path):
    ruta = tmp_path / "h.csv"
    e = [{"permiso": "PL/1", "precios": {"regular": 23.0}}]
    escribir_historico(ruta, "2026-11-09", e)
    escribir_historico(ruta, "2026-11-10", e)
    escribir_historico(ruta, "2026-11-10", [{"permiso": "PL/1", "precios": {"regular": 24.0}}])
    assert ruta.read_text().splitlines()[1:] == ["2026-11-09,PL/1,regular,23.0", "2026-11-10,PL/1,regular,24.0"]


def test_sin_insumos_opcionales(tmp_path):
    d = tmp_path / "data"
    shutil.copytree(FIXTURES / "raw", d / "raw")
    for f in ("osm_fuel.json", "denue.csv"):
        (d / "raw" / "2026-11-10" / f).unlink()
    m = correr.correr(d / "raw" / "2026-11-10", d, HOY)
    assert m["calidad"]["estaciones_publicadas"] == 4
    assert len(m["pasos_omitidos"]) == 4
    assert json.loads((d / "curated" / "huachicol_estados.json").read_text()) == {}


def test_municipio_respeta_huecos():
    cuadro = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    hueco = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    idx = municipios.IndiceMunicipios({"features": [
        {"properties": {"CVEGEO": "1001", "NOMGEO": "Dona"}, "geometry": {"type": "Polygon", "coordinates": [cuadro, hueco]}}]})
    assert idx.buscar(2, 2) == ("01001", "Dona")
    assert idx.buscar(5, 5) is None


def test_profeco_vigencia_y_nombre():
    est = [{"permiso": "A", "nombre": "Gasolinera La Luz SA de CV"}, {"permiso": "B", "nombre": "Servicio Hermanos Ruiz"}]
    filas = [
        {"fecha": "2025-01-01", "permiso": "A", "nombre": "", "resultado": "se_nego", "fuente": "", "url": ""},
        {"fecha": "2026-11-01", "permiso": "", "nombre": "HERMANOS RUIZ", "resultado": "litros_incompletos", "fuente": "", "url": ""},
        {"fecha": "2026-11-01", "permiso": "", "nombre": "Nadie", "resultado": "se_nego", "fuente": "", "url": ""},
    ]
    evitar, rep = profeco.aplicar(est, filas, HOY)
    assert evitar == ["B"]                             # la de A ya venció (> 180 días)
    assert est[0]["profeco"]["evitar"] is False
    assert rep["profeco_sin_estacion"] == 1


def test_profeco_rechaza_resultado_desconocido(tmp_path):
    ruta = tmp_path / "p.csv"
    ruta.write_text("fecha,permiso,nombre,entidad,producto,precio,resultado,fuente,url\n2026-11-01,A,,,,,quien_sabe,,\n")
    with pytest.raises(ValueError):
        profeco.leer(ruta)


def test_huachicol_no_mezcla_periodos():
    ruta = FIXTURES / "manual" / "huachicol_estados.csv"
    with pytest.raises(ValueError):
        huachicol.leer_conteos(ruta, nivel="estado")
    c = huachicol.leer_conteos(ruta, 2024, "1T", nivel="estado")
    assert list(c) == ["14"] and c["14"]["tomas_reportadas"] == 1137
    gas = huachicol.leer_conteos(ruta, 2024, "anual", "gas_lp", nivel="estado")
    assert gas["21"]["tomas_reportadas"] == 426


def test_huachicol_formato_viejo(tmp_path):
    ruta = tmp_path / "h.csv"
    ruta.write_text("cve_mun,municipio,estado,anio,tomas_reportadas,fuente,url\n13076,Tula,Hidalgo,2024,5,x,u\n"
                    "13076,Tula,Hidalgo,2024,2,y,v\n")
    assert huachicol.leer_conteos(ruta, 2024)["13076"]["tomas_reportadas"] == 7


def test_huachicol_claves_sin_poligono():
    geo = json.loads((FIXTURES / "geo" / "municipios.geojson").read_text(encoding="utf-8"))
    assert huachicol.claves_sin_poligono(geo, {"09015": {}, "99999": {}}) == ["99999"]


def test_agregados_y_coropleta():
    est = [{"marca": "Pemex", "cve_ent": "09", "cve_mun": "09015", "precios": {"regular": 23.0}},
           {"marca": "Pemex", "cve_ent": "09", "cve_mun": "09015", "precios": {"regular": 25.0}},
           {"marca": "BP", "cve_ent": None, "cve_mun": None, "precios": {"diesel": 26.0}}]
    agg = agregados.calcular(est, "2026-11-10")
    assert agg["nacional"]["regular"] == {"n": 2, "promedio": 24.0, "mediana": 24.0, "min": 23.0, "max": 25.0}
    assert "BP" in agg["por_marca"] and agg["estaciones_por_marca"] == {"Pemex": 2, "BP": 1}
    geo = json.loads((FIXTURES / "geo" / "municipios.geojson").read_text(encoding="utf-8"))
    fc = agregados.coropleta_precios(geo, agg, "regular")
    assert len(fc["features"]) == 1 and fc["features"][0]["properties"]["promedio"] == 24.0


@pytest.mark.parametrize("textos,marca", [
    (("Servicio Total del Norte",), "Independiente"),
    (("TOTAL",), "TotalEnergies"),
    (("Gasolinera Los Arcos",), "Independiente"),
    (("Arco",), "Arco"),
    (("TotalEnergies Insurgentes",), "TotalEnergies"),
])
def test_marcas_falsos_positivos(textos, marca):
    assert normalizar_marca(*textos) == marca


def test_similitud_nombre():
    assert similitud_nombre("ESTACION EL ROBLE", "El Roble") == pytest.approx(1.0)
    assert similitud_nombre("GASOLINERA LOS PINOS SA DE CV", "Servicio Hermanos Ruiz") < 0.6
    assert similitud_nombre(None, "x") == 0.0

from pipeline.marcas import normalizar_marca
from pipeline.transformar import a_geojson, integrar, leer_cne_estaciones, leer_cne_precios

ESTACIONES_XML = """<?xml version="1.0" encoding="utf-8"?>
<places>
  <place place_id="1"><name>SERVICIO OXXO GAS SUR</name><cre_id>PL/1/EXP/ES/2015</cre_id>
    <location><x>-99.13</x><y>19.43</y></location></place>
  <place place_id="2"><name>GASOLINERA SAN JUAN SA DE CV</name><cre_id>PL/2/EXP/ES/2016</cre_id>
    <location><x>-99.20</x><y>19.40</y></location></place>
  <place place_id="3"><name>MAL</name><cre_id>PL/3/EXP/ES/2016</cre_id>
    <location><x>0</x><y>0</y></location></place>
</places>"""

PRECIOS_XML = """<?xml version="1.0" encoding="utf-8"?>
<places>
  <place place_id="1"><gas_price type="regular">23.49</gas_price><gas_price type="premium">25.9</gas_price></place>
  <place place_id="2"><gas_price type="regular">999</gas_price><gas_price type="diesel">25.1</gas_price></place>
</places>"""


def test_marcas():
    assert normalizar_marca(None, "SERVICIO OXXO GAS SUR") == "Oxxo Gas"
    assert normalizar_marca("Pemex", "lo que sea") == "Pemex"
    assert normalizar_marca("", "Gasolinera Mi Pueblo") == "Independiente"
    assert normalizar_marca("G 500") == "G500"


def test_integracion(tmp_path):
    (tmp_path / "e.xml").write_text(ESTACIONES_XML, encoding="utf-8")
    (tmp_path / "p.xml").write_text(PRECIOS_XML, encoding="utf-8")
    est = leer_cne_estaciones(tmp_path / "e.xml")
    pre = leer_cne_precios(tmp_path / "p.xml")
    osm = [{"osm_id": "node/9", "lat": 19.4001, "lon": -99.2001, "brand": "Shell", "name": None,
            "operator": None, "opening_hours": "24/7"}]
    estaciones, rep = integrar(est, pre, osm, [])
    assert rep["coordenadas_invalidas"] == 1 and rep["precio_dudoso"] == 1 and rep["match_osm"] == 1
    por_permiso = {e["permiso"]: e for e in estaciones}
    assert por_permiso["PL/1/EXP/ES/2015"]["marca"] == "Oxxo Gas"
    assert por_permiso["PL/2/EXP/ES/2016"]["marca"] == "Shell"
    assert por_permiso["PL/2/EXP/ES/2016"]["precios"] == {"diesel": 25.1}  # 999 descartado
    fc = a_geojson(estaciones)
    assert fc["features"][0]["geometry"]["coordinates"] == [-99.13, 19.43]

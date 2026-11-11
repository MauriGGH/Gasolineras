from datetime import datetime, timedelta

import pytest

from geo.distancia import circulo_a_poligono, en_mexico, haversine_km, punto_destino
from geo.geocercas import (
    Geocerca,
    a_feature_collection,
    corredor_de_ruta,
    desde_geojson,
    geocercas_de_estaciones,
    geocercas_desde_geojson,
    zonas_de_referencia,
)
from geo.geocodificacion import Geocodificador, IndiceAreas, parsear_coordenadas
from geo.indice import IndiceEspacial
from geo.monitor import MonitorGeocercas

ZOCALO = (19.4326, -99.1332)
T0 = datetime(2026, 11, 11, 8, 0)


# --- distancia ---------------------------------------------------------------------------

def test_punto_destino_y_circulo():
    p = punto_destino(ZOCALO, 90, 2.0)
    assert haversine_km(ZOCALO, p) == pytest.approx(2.0, abs=1e-3)
    assert all(haversine_km(ZOCALO, v) == pytest.approx(1.0, abs=1e-3) for v in circulo_a_poligono(ZOCALO, 1.0, 16))


def test_en_mexico():
    assert en_mexico(ZOCALO)
    assert not en_mexico((40.4, -3.7))  # Madrid
    assert not en_mexico((float("nan"), -99))


# --- geocercas ---------------------------------------------------------------------------

def _dona():
    exterior = [(19, -99), (19, -98), (20, -98), (20, -99)]
    hueco = [(19.4, -98.6), (19.4, -98.4), (19.6, -98.4), (19.6, -98.6)]
    return Geocerca("m", "Municipio con hueco", "multipoligono", poligonos=[[exterior, hueco]])


def test_multipoligono_con_hueco():
    g = _dona()
    assert g.contiene((19.2, -98.8))
    assert not g.contiene((19.5, -98.5))  # dentro del hueco
    assert not g.contiene((21, -98.5))


def test_distancia_borde_con_signo():
    c = Geocerca("c", "C", "circulo", centro=ZOCALO, radio_km=1.0)
    assert c.distancia_borde_km(ZOCALO) == pytest.approx(-1.0)
    assert c.distancia_borde_km(punto_destino(ZOCALO, 0, 1.5)) == pytest.approx(0.5, abs=1e-3)
    cuadro = Geocerca("p", "P", "poligono", vertices=[(19, -99), (19, -98), (20, -98), (20, -99)])
    assert cuadro.distancia_borde_km((19.01, -98.5)) == pytest.approx(-1.11, abs=0.02)
    assert cuadro.distancia_borde_km((18.99, -98.5)) == pytest.approx(1.11, abs=0.02)
    assert _dona().distancia_borde_km((19.5, -98.5)) > 0


def test_geojson_ida_y_vuelta():
    originales = [
        Geocerca("c", "Círculo", "circulo", centro=ZOCALO, radio_km=0.5, etiquetas={"marca": "Pemex"}),
        Geocerca("p", "Polígono", "poligono", vertices=[(19, -99), (19, -98), (20, -98)]),
        _dona(),
        corredor_de_ruta("r", [(19.0, -99.0), (19.0, -98.0)], ancho_km=1.0),
    ]
    fc = a_feature_collection(originales)
    vueltas = geocercas_desde_geojson(fc)
    for a, b in zip(originales, vueltas):
        assert (a.id, a.tipo) == (b.id, b.tipo)
        for p in [ZOCALO, (19.2, -98.8), (19.5, -98.5), (19.005, -98.5)]:
            assert a.contiene(p) == b.contiene(p)
    assert vueltas[0].etiquetas["marca"] == "Pemex"


def test_circulo_como_poligono_para_maplibre():
    f = Geocerca("c", "C", "circulo", centro=ZOCALO, radio_km=1.0).a_geojson(circulo_como_poligono=True)
    anillo = f["geometry"]["coordinates"][0]
    assert f["geometry"]["type"] == "Polygon" and anillo[0] == anillo[-1]


def test_geocercas_de_estaciones():
    estaciones = [{"permiso": "PL/1/EXP/ES/2015", "nombre": "Servicio Centro", "marca": "Pemex",
                   "lat": ZOCALO[0], "lon": ZOCALO[1]}]
    (g,) = geocercas_de_estaciones(estaciones, radio_km=0.1)
    assert g.id == "PL/1/EXP/ES/2015" and g.etiquetas["marca"] == "Pemex"
    assert g.contiene(punto_destino(ZOCALO, 45, 0.05))
    assert not g.contiene(punto_destino(ZOCALO, 45, 0.2))


def test_zonas_de_referencia_filtra_por_minimo():
    def feat(clave, tomas):
        return {"type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[[-99, 19], [-98, 19], [-98, 20], [-99, 20], [-99, 19]]]},
                "properties": {"CVEGEO": clave, "NOMGEO": f"Mun {clave}", "tomas_reportadas": tomas,
                               "fuentes": [{"fuente": "Pemex", "anio": 2025}]}}
    fc = {"type": "FeatureCollection", "features": [feat("13001", 120), feat("13002", 3)]}
    zonas = zonas_de_referencia(fc, minimo_tomas=10)
    assert [z.id for z in zonas] == ["13001"]
    assert zonas[0].etiquetas["capa"] == "referencia_huachicol"
    assert zonas[0].nombre == "Mun 13001"


def test_desde_geojson_errores():
    with pytest.raises(ValueError):
        desde_geojson({"type": "Feature", "geometry": {"type": "Point", "coordinates": [-99, 19]}, "properties": {}})


# --- monitor -----------------------------------------------------------------------------

def test_monitor_histeresis_evita_rebotes():
    g = Geocerca("est", "Estación", "circulo", centro=ZOCALO, radio_km=0.1)
    m = MonitorGeocercas([g], histeresis_km=0.03)
    pasos = [0.3, 0.09, 0.11, 0.095, 0.12, 0.2]  # km al centro; 0.11 y 0.12 son ruido del GPS
    eventos = []
    for i, d in enumerate(pasos):
        eventos += m.actualizar(punto_destino(ZOCALO, 0, d), T0 + timedelta(seconds=10 * i))
    assert [e.tipo for e in eventos] == ["entrada", "salida"]
    assert eventos[1].permanencia_s == 40


def test_monitor_sin_histeresis_si_rebota():
    g = Geocerca("est", "Estación", "circulo", centro=ZOCALO, radio_km=0.1)
    m = MonitorGeocercas([g], histeresis_km=0.0)
    tipos = [e.tipo for d in [0.3, 0.09, 0.11, 0.095] for e in m.actualizar(punto_destino(ZOCALO, 0, d), T0)]
    assert tipos == ["entrada", "salida", "entrada"]


def test_monitor_precision_permanencia_y_oyente():
    g = Geocerca("base", "Base", "circulo", centro=ZOCALO, radio_km=0.2)
    m = MonitorGeocercas([g], permanencia_s=300, precision_max_m=50)
    recibidos = []
    m.al_evento(recibidos.append)
    assert m.actualizar(ZOCALO, T0, precision_m=500) == []  # lectura mala: se ignora
    assert [e.tipo for e in m.actualizar(ZOCALO, T0, precision_m=10)] == ["entrada"]
    assert m.actualizar(ZOCALO, T0 + timedelta(minutes=2)) == []
    ev = m.actualizar(ZOCALO, T0 + timedelta(minutes=6))
    assert [e.tipo for e in ev] == ["permanencia"] and ev[0].permanencia_s == 360
    assert m.actualizar(ZOCALO, T0 + timedelta(minutes=7)) == []  # se avisa una sola vez
    assert [e.tipo for e in recibidos] == ["entrada", "permanencia"]
    assert [g.id for g in m.dentro_de()] == ["base"]


def test_monitor_sin_evento_inicial():
    g = Geocerca("base", "Base", "circulo", centro=ZOCALO, radio_km=0.2)
    m = MonitorGeocercas([g], evento_inicial=False)
    assert m.actualizar(ZOCALO, T0) == []
    assert [e.tipo for e in m.actualizar(punto_destino(ZOCALO, 0, 1), T0)] == ["salida"]


def test_monitor_desvio_de_ruta():
    ruta = corredor_de_ruta("ruta", [(19.0, -99.0), (19.0, -98.0)], ancho_km=1.0)
    m = MonitorGeocercas([ruta])
    tipos = [e.tipo for p in [(19.0, -99.0), (19.005, -98.8), (19.05, -98.6), (19.0, -98.4)]
             for e in m.actualizar(p, T0)]
    assert tipos == ["entrada", "salida", "entrada"]


# --- índice espacial ---------------------------------------------------------------------

def _rejilla_estaciones():
    return [{"id": f"{i}-{j}", "lat": 19.0 + i * 0.01, "lon": -99.5 + j * 0.01} for i in range(60) for j in range(60)]


def test_indice_cercanas_igual_a_fuerza_bruta():
    estaciones = _rejilla_estaciones()
    idx = IndiceEspacial.de_elementos(estaciones, celda_km=2)
    p = (19.2345, -99.2222)
    esperado = sorted(e["id"] for e in estaciones if haversine_km(p, (e["lat"], e["lon"])) <= 3)
    obtenido = idx.cercanas(p, 3)
    assert sorted(e["id"] for _, e in obtenido) == esperado
    assert [d for d, _ in obtenido] == sorted(d for d, _ in obtenido)


def test_indice_k_mas_cercanas():
    estaciones = _rejilla_estaciones()
    idx = IndiceEspacial.de_elementos(estaciones, celda_km=2)
    for p in [(19.2345, -99.2222), (18.9, -99.6)]:  # dentro y fuera de la rejilla
        bruto = sorted(estaciones, key=lambda e: haversine_km(p, (e["lat"], e["lon"])))[:5]
        assert [e["id"] for _, e in idx.k_mas_cercanas(p, 5)] == [e["id"] for e in bruto]
    assert idx.k_mas_cercanas((25.0, -105.0), 3, radio_max_km=50) == []


# --- georreferenciación ------------------------------------------------------------------

@pytest.mark.parametrize("texto,esperado", [
    ("19.4326, -99.1332", (19.4326, -99.1332)),
    ("19.4326 -99.1332", (19.4326, -99.1332)),
    ("-99.1332, 19.4326", (19.4326, -99.1332)),  # lon,lat volteado
    ("19,4326; -99,1332", (19.4326, -99.1332)),
    ("https://www.google.com/maps/@19.4326,-99.1332,15z", (19.4326, -99.1332)),
    ("19°25'57\"N 99°07'59\"W", (19.4325, -99.13306)),
    ("19°25'57\"N 99°07'59\"O", (19.4325, -99.13306)),
])
def test_parsear_coordenadas(texto, esperado):
    lat, lon = parsear_coordenadas(texto)
    assert lat == pytest.approx(esperado[0], abs=1e-4) and lon == pytest.approx(esperado[1], abs=1e-4)


@pytest.mark.parametrize("texto", ["Av. Reforma 222, CDMX", "Gasolinera Pemex Tlalpan", "100, 300"])
def test_parsear_coordenadas_no_coords(texto):
    assert parsear_coordenadas(texto) is None


class _Falso:
    def __init__(self):
        self.urls = []
        self.t = 0.0
        self.dormido = 0.0

    def pedir(self, url):
        self.urls.append(url)
        if "/reverse" in url:
            return {"lat": "19.4326", "lon": "-99.1332", "display_name": "Zócalo, Centro, Cuauhtémoc",
                    "address": {"state": "Ciudad de México", "city": "Cuauhtémoc", "postcode": "06000"}}
        return [{"lat": "19.43", "lon": "-99.13", "display_name": "Reforma, CDMX", "address": {"state": "Ciudad de México"}},
                {"lat": "40.4", "lon": "-3.7", "display_name": "Madrid"}]

    def dormir(self, s):
        self.dormido += s
        self.t += s


def test_geocodificador_cache_ritmo_y_filtro_mexico():
    f = _Falso()
    g = Geocodificador(pedir_json=f.pedir, reloj=lambda: f.t, dormir=f.dormir)
    r = g.buscar("Reforma 222")
    assert len(r) == 1 and r[0].estado == "Ciudad de México"
    g.buscar("Reforma 222")
    assert len(f.urls) == 1  # segunda vez sale de caché
    inv = g.inversa(ZOCALO)
    assert inv.municipio == "Cuauhtémoc" and inv.cp == "06000"
    assert f.dormido == pytest.approx(1.0)  # respetó 1 petición por segundo
    assert g.buscar("19.4326, -99.1332")[0].fuente == "coordenadas"
    assert len(f.urls) == 2
    assert "countrycodes=mx" in f.urls[0]


def test_indice_areas_respeta_huecos():
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"CVEGEO": "01001", "NOMGEO": "Con hueco"},
         "geometry": {"type": "Polygon", "coordinates": [
             [[-99, 19], [-98, 19], [-98, 20], [-99, 20], [-99, 19]],
             [[-98.6, 19.4], [-98.4, 19.4], [-98.4, 19.6], [-98.6, 19.6], [-98.6, 19.4]]]}},
        {"type": "Feature", "properties": {"CVEGEO": "01002", "NOMGEO": "Enclave"},
         "geometry": {"type": "MultiPolygon", "coordinates": [
             [[[-98.6, 19.4], [-98.4, 19.4], [-98.4, 19.6], [-98.6, 19.6], [-98.6, 19.4]]]]}},
    ]}
    idx = IndiceAreas(fc)
    assert idx.clave_de((19.2, -98.8)) == "01001"
    assert idx.clave_de((19.5, -98.5)) == "01002"
    assert idx.area_de((19.5, -98.5)).nombre == "Enclave"
    assert idx.clave_de((25, -100)) is None

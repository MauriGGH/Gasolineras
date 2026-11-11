from datetime import datetime, timedelta

import pytest

from geo.distancia import haversine_km, proyectar_en_linea, punto_en_poligono
from geo.geocercas import Geocerca, eventos_de_recorrido, filtrar_dentro

ZOCALO = (19.4326, -99.1332)
ANGEL = (19.4270, -99.1677)


def test_haversine_cdmx():
    assert haversine_km(ZOCALO, ANGEL) == pytest.approx(3.67, abs=0.1)


def test_proyeccion_en_linea():
    linea = [(19.0, -99.0), (19.0, -98.0)]
    km, desvio = proyectar_en_linea((19.01, -98.5), linea)
    assert km == pytest.approx(52.6, abs=0.5)
    assert desvio == pytest.approx(1.11, abs=0.05)


def test_punto_en_poligono():
    cuadro = [(19, -99), (19, -98), (20, -98), (20, -99)]
    assert punto_en_poligono((19.5, -98.5), cuadro)
    assert not punto_en_poligono((20.5, -98.5), cuadro)


def test_geocerca_circulo_filtra_estaciones():
    g = Geocerca("cerca", "Zócalo 1 km", "circulo", centro=ZOCALO, radio_km=1.0)
    estaciones = [{"lat": ZOCALO[0] + 0.005, "lon": ZOCALO[1]}, {"lat": ANGEL[0], "lon": ANGEL[1]}]
    assert len(filtrar_dentro(g, estaciones)) == 1


def test_eventos_entrada_salida_y_corredor():
    base = Geocerca("base", "Base", "circulo", centro=(19.0, -99.0), radio_km=0.5)
    corredor = Geocerca("ruta", "Ruta", "corredor", vertices=[(19.0, -99.0), (19.0, -98.0)], ancho_km=1.0)
    t0 = datetime(2026, 11, 11, 8, 0)
    recorrido = [((19.0, -99.0), t0),
                 ((19.0, -98.9), t0 + timedelta(minutes=10)),
                 ((19.05, -98.8), t0 + timedelta(minutes=20)),  # ~5.5 km fuera del corredor
                 ((19.0, -98.7), t0 + timedelta(minutes=30))]
    ev = [(e.geocerca_id, e.tipo) for e in eventos_de_recorrido([base, corredor], recorrido)]
    assert ev == [("base", "salida"), ("ruta", "salida"), ("ruta", "entrada")]


def test_geojson_poligono_cerrado():
    g = Geocerca("p", "P", "poligono", vertices=[(19, -99), (19, -98), (20, -98)])
    anillo = g.a_geojson()["geometry"]["coordinates"][0]
    assert anillo[0] == anillo[-1] and anillo[0] == [-99, 19]

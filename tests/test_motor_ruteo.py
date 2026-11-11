"""Pruebas del motor extendido: red vial propia, cercanas, objetivos de recarga, VRP y flotilla."""
import itertools
import math

import pytest

from geo.distancia import haversine_km
from routing.cercanas import gasolineras_cercanas
from routing.estaciones import IndiceEstaciones, cargar_estaciones
from routing.flotilla import Flotilla
from routing.motor import RED_EJEMPLO, MotorRedVial
from routing.recarga import Vehiculo, planear_recargas, planear_viaje
from routing.red_vial import RedVial
from routing.vrp import Pedido, Pipa, planear_flota_surtido

CDMX, MTY, GDL, QRO = (19.4326, -99.1332), (25.6866, -100.3161), (20.6597, -103.3496), (20.5888, -100.3899)


@pytest.fixture(scope="module")
def motor():
    return MotorRedVial(RedVial.desde_geojson(RED_EJEMPLO))


@pytest.fixture(scope="module")
def indice():
    from routing.estaciones import RAIZ
    return IndiceEstaciones(cargar_estaciones(RAIZ / "data" / "ejemplo" / "estaciones.geojson"))


# ---------- red vial ----------
def red_cuadricula():
    """Cuadrícula 3x3 con una autopista rápida por la orilla."""
    red = RedVial()
    for i in range(3):
        red.agregar_via([(20 + i * 0.1, -100 + j * 0.1) for j in range(3)], vel_kmh=30)
        red.agregar_via([(20 + j * 0.1, -100 + i * 0.1) for j in range(3)], vel_kmh=30)
    red.agregar_via([(20, -100), (20, -99.9), (20, -99.8)], vel_kmh=120)
    return red


def test_a_estrella_igual_a_fuerza_bruta_en_cuadricula():
    red = red_cuadricula()
    # fuerza bruta: Floyd-Warshall por minutos
    n = len(red.nodos)
    d = [[math.inf] * n for _ in range(n)]
    for i in range(n):
        d[i][i] = 0
        for a in red.ady[i]:
            d[i][a.destino] = min(d[i][a.destino], a.minutos)
    for k, i, j in itertools.product(range(n), repeat=3):
        d[i][j] = min(d[i][j], d[i][k] + d[k][j])
    for a, b in itertools.permutations(range(n), 2):
        pa, pb = red.nodos[a], red.nodos[b]
        if haversine_km(pa, pb) < 15:
            continue  # la ruta directa urbana compite; probar solo tramos largos
        r = red.ruta([pa, pb])
        assert r["duracion_min"] == pytest.approx(d[a][b], rel=1e-6)


def test_ruta_cdmx_monterrey_es_razonable(motor):
    r = motor.ruta([CDMX, MTY])
    recta = haversine_km(CDMX, MTY)
    assert recta < r["distancia_km"] < recta * 1.4
    assert r["linea"][0] == CDMX and r["linea"][-1] == MTY


def test_tabla_simetrica_y_coherente_con_ruta(motor):
    pts = [CDMX, QRO, GDL]
    t = motor.tabla(pts)
    assert t["distancia_km"][0][0] == 0
    assert t["duracion_min"][0][2] == pytest.approx(motor.ruta([CDMX, GDL])["duracion_min"], rel=1e-6)
    assert t["distancia_km"][0][1] == pytest.approx(t["distancia_km"][1][0], rel=1e-6)


# ---------- cercanas ----------
def test_cercanas_ordena_por_minutos_y_filtra(motor, indice):
    res = gasolineras_cercanas(CDMX, indice, motor, n=5, producto="diesel", marcas={"Pemex"})
    assert res and all(e["marca"] == "Pemex" and "diesel" in e["precios"] for e in res)
    mins = [e["duracion_min"] for e in res]
    assert mins == sorted(mins)


def test_cercanas_por_precio(motor, indice):
    res = gasolineras_cercanas(CDMX, indice, motor, n=5, producto="regular", ordenar_por="precio")
    precios = [e["precio"] for e in res]
    assert precios == sorted(precios)


def test_cercanas_sin_resultados_en_el_mar(motor, indice):
    assert gasolineras_cercanas((15.0, -95.0), indice, motor, radio_km=5) == []


# ---------- recargas ----------
RUTA = [(20.0, -103.0 + i * 0.01) for i in range(401)]  # ~420 km, muchos vértices como OSRM


def est(permiso, lon, precio, lat=20.002):
    return {"permiso": permiso, "nombre": permiso, "marca": "X", "lat": lat, "lon": lon, "precios": {"regular": precio}}


def test_objetivo_paradas_usa_menos_paradas_que_costo():
    # Barato pero obliga a dos paradas cortas vs. una sola parada cara
    v = Vehiculo(tanque_l=30, rendimiento_km_l=10, combustible_inicial_l=30, reserva_l=0)
    estaciones = [est("CARA_MEDIO", -101.0, 30.0), est("BARATA1", -101.7, 18.0), est("BARATA2", -100.9, 18.0)]
    p_costo = planear_recargas(RUTA, estaciones, v, objetivo="costo", costo_parada=1)
    p_paradas = planear_recargas(RUTA, estaciones, v, objetivo="paradas")
    assert len(p_paradas.paradas) == 1
    assert len(p_costo.paradas) >= len(p_paradas.paradas)
    assert p_costo.costo_combustible <= p_paradas.costo_combustible


def test_objetivo_tiempo_prefiere_menor_desvio():
    v = Vehiculo(tanque_l=30, rendimiento_km_l=10, combustible_inicial_l=30, reserva_l=0)
    lejos = est("LEJOS_BARATA", -101.5, 18.0, lat=20.015)  # ~1.5 km de desvío
    pegada = est("PEGADA", -101.5, 25.0, lat=20.0005)
    plan = planear_recargas(RUTA, [lejos, pegada], v, objetivo="tiempo")
    assert [p.permiso for p in plan.paradas] == ["PEGADA"]
    assert planear_recargas(RUTA, [lejos, pegada], v, objetivo="costo").paradas[0].permiso == "LEJOS_BARATA"


def test_objetivo_invalido():
    with pytest.raises(ValueError):
        planear_recargas(RUTA, [], Vehiculo(40, 10, 40), objetivo="rapido")


def test_viaje_completo_nunca_excede_autonomia(motor, indice):
    v = Vehiculo(tanque_l=40, rendimiento_km_l=11, combustible_inicial_l=15, reserva_l=4)
    r = planear_viaje([CDMX, MTY], v, motor, indice, objetivo="costo")
    plan = r["plan"]
    assert plan and plan["num_paradas"] >= 2
    tanque, km_prev = v.combustible_inicial_l, 0.0
    for p in plan["paradas"]:
        tanque -= (p["km_ruta"] - km_prev + p["desvio_km"]) / v.rendimiento_km_l
        assert tanque >= v.reserva_l - 1.01  # tolerancia por discretización de 1 l
        tanque += p["litros"]
        assert tanque <= v.tanque_l + 1e-6
        km_prev = p["km_ruta"] - p["desvio_km"]  # salir de la estación cuesta el desvío
    tipos = [f["properties"]["tipo"] for f in r["geojson"]["features"]]
    assert tipos.count("parada_recarga") == plan["num_paradas"]


def test_viaje_imposible_explica_motivo(motor, indice):
    r = planear_viaje([CDMX, MTY], Vehiculo(10, 8, 10), motor, indice, corredor_km=0.1)
    assert r["plan"] is None and "autonomía" in r["motivo"]


# ---------- VRP ----------
requiere_ortools = pytest.mark.skipif(not __import__("routing.vrp").vrp._ortools_disponible(), reason="sin OR-Tools")


@requiere_ortools
def test_vrp_respeta_capacidades_y_ventanas(motor, indice):
    est_ = [e for e, _ in indice.en_radio((19.6, -99.4), 80)][:12]
    pedidos = [Pedido(e["permiso"], (e["lat"], e["lon"]), 6000) for e in est_]
    pedidos[0].ventana = (0, 90)
    pipas = [Pipa("P1", 20000), Pipa("P2", 31000), Pipa("P3", 31000)]
    r = planear_flota_surtido((19.53, -99.19), pedidos, pipas, motor, segundos_busqueda=1, incluir_geometria=False)
    assert r["metodo"] == "ortools"
    cap = {p.id: p.capacidad_l for p in pipas}
    for v in r["viajes"]:
        assert v["litros"] <= cap[v["pipa"]]
    servidos = [i for v in r["viajes"] for i in v["orden"]]
    assert len(servidos) == len(set(servidos))
    assert sorted(servidos + r["no_atendidas"]) == sorted(p.id for p in pedidos)
    assert not r["no_atendidas"]  # 72 000 l caben en 82 000 l
    llegada = next(p["llegada_min"] for v in r["viajes"] for p in v["paradas"] if p["id"] == pedidos[0].id)
    assert llegada <= 90


@requiere_ortools
def test_vrp_deja_fuera_lo_que_no_cabe(motor):
    pedidos = [Pedido("GRANDE", (19.6, -99.2), 50000), Pedido("CHICO", (19.5, -99.2), 5000)]
    r = planear_flota_surtido(CDMX, pedidos, [Pipa("P1", 20000)], motor, segundos_busqueda=1, incluir_geometria=False)
    assert r["no_atendidas"] == ["GRANDE"]


# ---------- flotilla ----------
def test_flotilla_varias_unidades_y_simulacion(motor, indice):
    f = Flotilla(motor, indice)
    ev = f.registrar("u1", CDMX, [QRO]) + f.registrar("u2", CDMX, [GDL]) + f.registrar("u3", QRO, [MTY])
    assert [e["tipo"] for e in ev].count("ruta") == 3
    colores = {u.color for u in f.unidades.values()}
    assert len(colores) == 3
    ev = f.simular_paso(60, acelerar=60)  # una hora de manejo
    pos = {e["vehiculo"]["id"]: e["vehiculo"] for e in ev if e["tipo"] == "posicion"}
    assert set(pos) == {"u1", "u2", "u3"}
    assert all(0 < v["km_recorrido"] for v in pos.values())
    assert pos["u2"]["min_restante"] < f.unidades["u2"].duracion_min
    estado = f.estado()
    assert sum(1 for x in estado["features"] if x["properties"]["tipo"] == "vehiculo") == 3


def test_flotilla_llega_y_detecta_desvio(motor, indice):
    f = Flotilla(motor, indice)
    f.registrar("u1", CDMX, [QRO])
    ev = f.actualizar_posicion("u1", 19.0, -100.5)  # muy fuera del corredor
    assert any(e.get("alerta") == "desvio" for e in ev)
    assert any(e["tipo"] == "ruta" for e in ev)
    assert f.unidades["u1"].recalculos == 2
    ev = f.actualizar_posicion("u1", *QRO)
    assert any(e.get("alerta") == "llegada" for e in ev)
    assert f.unidades["u1"].km_restante == 0


def test_flotilla_sugiere_recarga(motor, indice):
    f = Flotilla(motor, indice)
    ev = f.registrar("u1", CDMX, [MTY], combustible=Vehiculo(50, 10, 20, reserva_l=3))
    alerta = next(e for e in ev if e.get("alerta") == "combustible_bajo")
    assert alerta["siguiente_recarga"]["km_ruta"] <= 170

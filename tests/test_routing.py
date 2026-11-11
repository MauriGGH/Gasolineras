import pytest

from geo.distancia import longitudes_acumuladas
from routing.busqueda import a_estrella, dijkstra
from routing.pipa import Entrega, planear_surtido
from routing.recarga import Vehiculo, planear_recargas

# Ruta recta de ~420 km hacia el este sobre el paralelo 20
RUTA = [(20.0, -103.0 + i * 0.1) for i in range(41)]
TOTAL = longitudes_acumuladas(RUTA)[-1]


def est(permiso, lon, precio, marca="Pemex"):
    return {"permiso": permiso, "nombre": permiso, "marca": marca, "lat": 20.001, "lon": lon,
            "precios": {"regular": precio}}


def test_dijkstra_y_a_estrella_coinciden():
    grafo = {"A": [("B", 4), ("C", 1)], "C": [("B", 1), ("D", 5)], "B": [("D", 1)], "D": []}
    r1 = dijkstra("A", lambda n: n == "D", lambda n: grafo[n])
    r2 = a_estrella("A", lambda n: n == "D", lambda n: grafo[n], lambda n: 0)
    assert r1 == r2 == (3, ["A", "C", "B", "D"])


def test_sin_autonomia_suficiente_devuelve_none():
    v = Vehiculo(tanque_l=20, rendimiento_km_l=10, combustible_inicial_l=20)
    assert planear_recargas(RUTA, [], v) is None


def test_no_carga_si_alcanza():
    v = Vehiculo(tanque_l=60, rendimiento_km_l=10, combustible_inicial_l=60)
    plan = planear_recargas(RUTA, [est("A", -102.5, 23.0)], v)
    assert plan.paradas == []
    assert plan.distancia_km == pytest.approx(TOTAL, abs=0.2)


def test_prefiere_la_estacion_barata_y_carga_lo_justo():
    # 40 l de tanque, 10 km/l -> 400 km de autonomía; la ruta mide ~420 km
    v = Vehiculo(tanque_l=40, rendimiento_km_l=10, combustible_inicial_l=25, reserva_l=2)
    estaciones = [est("CARA", -102.0, 26.0), est("BARATA", -101.6, 22.0, "G500")]
    plan = planear_recargas(RUTA, estaciones, v, costo_parada=5)
    assert [p.permiso for p in plan.paradas] == ["BARATA"]
    litros = plan.paradas[0].litros
    # necesita ~42 l en total + 2 de reserva; trae 25 -> compra ~19-21 l, no llena
    assert 17 <= litros <= 22
    assert plan.litros_al_llegar >= 2


def test_respeta_estaciones_a_evitar():
    v = Vehiculo(tanque_l=40, rendimiento_km_l=10, combustible_inicial_l=25, reserva_l=2)
    estaciones = [est("CARA", -102.0, 26.0), est("BARATA", -101.6, 22.0)]
    plan = planear_recargas(RUTA, estaciones, v, evitar={"BARATA"})
    assert [p.permiso for p in plan.paradas] == ["CARA"]


def test_pipa_respeta_capacidad_y_visita_todo():
    base = (19.43, -99.13)
    entregas = [Entrega(f"E{i}", (19.43 + 0.05 * i, -99.13 + 0.03 * (i % 3)), 10_000) for i in range(1, 6)]
    viajes = planear_surtido(base, entregas, capacidad_l=20_000)
    assert sorted(x for v in viajes for x in v["orden"]) == [f"E{i}" for i in range(1, 6)]
    assert all(v["litros"] <= 20_000 for v in viajes)
    assert len(viajes) == 3

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import routing.api as api  # noqa: E402


@pytest.fixture()
def cliente(monkeypatch):
    monkeypatch.setenv("GASRUTA_MOTOR", "offline")
    api.obtener_motor.cache_clear()
    api.Estado.flotilla = None
    return TestClient(api.app)


def test_salud_y_cercanas(cliente):
    assert cliente.get("/salud").json()["motor"] == "red_vial"
    r = cliente.get("/cercanas", params={"lat": 19.43, "lon": -99.13, "producto": "regular", "n": 3}).json()
    assert len(r["resultados"]) == 3


def test_recargas(cliente):
    body = {"puntos": [[19.43, -99.13], [25.68, -100.31]], "objetivo": "paradas",
            "vehiculo": {"tanque_l": 45, "rendimiento_km_l": 12, "combustible_inicial_l": 20}}
    r = cliente.post("/ruta/recargas", json=body).json()
    assert r["plan"]["num_paradas"] >= 1
    assert r["geojson"]["features"][0]["geometry"]["type"] == "LineString"


def test_surtido(cliente):
    body = {"base": [19.53, -99.19], "pipas": [{"id": "P1", "capacidad_l": 31000}], "segundos_busqueda": 1,
            "pedidos": [{"id": "A", "lat": 19.6, "lon": -99.2, "litros": 10000},
                        {"id": "B", "lat": 19.45, "lon": -99.1, "litros": 10000}]}
    r = cliente.post("/ruta/surtido", json=body).json()
    assert sorted(r["viajes"][0]["orden"]) == ["A", "B"]


def test_flotilla_websocket(cliente):
    with cliente.websocket_connect("/flotilla/ws") as ws:
        assert ws.receive_json()["tipo"] == "estado"
        alta = {"vehiculos": [{"id": "u1", "posicion": [19.43, -99.13], "destinos": [[20.59, -100.39]]},
                              {"id": "u2", "posicion": [19.43, -99.13], "destinos": [[20.66, -103.35]]}]}
        assert cliente.post("/flotilla/vehiculos", json=alta).status_code == 200
        tipos = [ws.receive_json()["tipo"] for _ in range(2)]
        assert tipos == ["ruta", "ruta"]
        ws.send_json({"tipo": "posicion", "id": "u1", "lat": 19.5, "lon": -99.17})
        e = ws.receive_json()
        while e["tipo"] != "posicion":
            e = ws.receive_json()
        assert e["vehiculo"]["id"] == "u1"
        ws.send_json({"tipo": "posicion", "id": "nadie", "lat": 1, "lon": 1})
        assert ws.receive_json()["tipo"] == "error"
    estado = cliente.get("/flotilla").json()
    assert len([f for f in estado["features"] if f["properties"]["tipo"] == "vehiculo"]) == 2
    assert cliente.delete("/flotilla/vehiculos/u2").status_code == 200
    assert cliente.delete("/flotilla/vehiculos/u2").status_code == 404

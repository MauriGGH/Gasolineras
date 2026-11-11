import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

import {
  MonitorGeocercas, circulo, corredor, crearFiltroLecturas, desdeGeojson, geocercasDesdeGeojson,
  haversineKm, obtenerUbicacion, parsearCoordenadas, poligono, puntoDestino, seguirUbicacion,
} from "../index.js";

const ZOCALO = [19.4326, -99.1332];
const cerca = (a, b, tol) => assert.ok(Math.abs(a - b) <= tol, `${a} ≉ ${b}`);

test("haversine y punto destino", () => {
  cerca(haversineKm(ZOCALO, [19.427, -99.1677]), 3.67, 0.1);
  cerca(haversineKm(ZOCALO, puntoDestino(ZOCALO, 90, 2)), 2, 1e-3);
});

test("mismo resultado que Python con el GeoJSON de a_feature_collection", () => {
  const { geocercas, casos } = JSON.parse(readFileSync(new URL("./fixture_python.json", import.meta.url)));
  const gs = geocercasDesdeGeojson(geocercas);
  assert.equal(gs[0].propiedades.marca, "Pemex");
  for (const { punto, esperado, distancia } of casos) {
    for (const g of gs) {
      assert.equal(g.contiene(punto), esperado[g.id], `${g.id} en ${punto}`);
      cerca(g.distanciaBordeKm(punto), distancia[g.id], 1e-3);
    }
  }
});

test("aGeojson ida y vuelta (círculo sale como polígono para MapLibre)", () => {
  const gs = [circulo("c", ZOCALO, 1), poligono("p", [[19, -99], [19, -98], [20, -98]]), corredor("r", [[19, -99], [19, -98]], 1)];
  for (const g of gs) {
    const f = g.aGeojson();
    const v = desdeGeojson(f);
    for (const p of [ZOCALO, [19.2, -98.8], [19.005, -98.5]]) assert.equal(v.contiene(p), g.contiene(p));
  }
  assert.equal(gs[0].aGeojson().geometry.type, "Polygon");
});

test("monitor: histéresis, precisión, permanencia y oyentes", () => {
  const m = new MonitorGeocercas([circulo("est", ZOCALO, 0.1)], { permanenciaMs: 60_000 });
  const recibidos = [];
  const quitar = m.alEvento((e) => recibidos.push(e.tipo));
  const leer = (km, s, precisionM = 10) => {
    const [lat, lon] = puntoDestino(ZOCALO, 0, km);
    return m.actualizar({ lat, lon, timestamp: s * 1000, precisionM }).map((e) => e.tipo);
  };
  assert.deepEqual(leer(0.3, 0), []);
  assert.deepEqual(leer(0.05, 10, 500), []); // precisión mala: se ignora
  assert.deepEqual(leer(0.09, 20), ["entrada"]);
  assert.deepEqual(leer(0.11, 30), []); // ruido junto al borde
  assert.deepEqual(leer(0.05, 90), ["permanencia"]);
  assert.deepEqual(leer(0.05, 120), []);
  assert.equal(m.dentroDe()[0].id, "est");
  const salida = m.actualizar({ lat: 19.44, lon: -99.1332, timestamp: 130_000 });
  assert.equal(salida[0].tipo, "salida");
  assert.equal(salida[0].permanenciaMs, 110_000);
  quitar();
  leer(0.05, 140);
  assert.deepEqual(recibidos, ["entrada", "permanencia", "salida"]);
});

test("monitor detecta desvío de ruta", () => {
  const m = new MonitorGeocercas([corredor("ruta", [[19, -99], [19, -98]], 1)]);
  const tipos = [[19, -99], [19.005, -98.8], [19.05, -98.6], [19, -98.4]]
    .flatMap(([lat, lon], i) => m.actualizar({ lat, lon, timestamp: i }).map((e) => e.tipo));
  assert.deepEqual(tipos, ["entrada", "salida", "entrada"]);
});

test("parsearCoordenadas", () => {
  const casos = {
    "19.4326, -99.1332": [19.4326, -99.1332],
    "-99.1332 19.4326": [19.4326, -99.1332],
    "19,4326; -99,1332": [19.4326, -99.1332],
    "https://www.google.com/maps/@19.4326,-99.1332,15z": [19.4326, -99.1332],
    "19°25'57\"N 99°07'59\"O": [19.4325, -99.13306],
  };
  for (const [t, [lat, lon]] of Object.entries(casos)) {
    const r = parsearCoordenadas(t);
    cerca(r[0], lat, 1e-4);
    cerca(r[1], lon, 1e-4);
  }
  assert.equal(parsearCoordenadas("Av. Reforma 222"), null);
  assert.equal(parsearCoordenadas("100, 300"), null);
});

test("filtro de lecturas descarta saltos imposibles", () => {
  const f = crearFiltroLecturas({ velocidadMaxKmh: 200 });
  assert.ok(f({ lat: 19, lon: -99, timestamp: 0, precisionM: 5 }));
  assert.ok(!f({ lat: 19.5, lon: -99, timestamp: 60_000, precisionM: 5 })); // 55 km en 1 min
  assert.ok(f({ lat: 19.01, lon: -99, timestamp: 60_000, precisionM: 5 })); // 1.1 km en 1 min
  assert.ok(!f({ lat: 19.01, lon: -99, timestamp: 70_000, precisionM: 500 }));
});

function geoFalso(posiciones) {
  return {
    getCurrentPosition: (ok) => ok(posiciones[0]),
    watchPosition(ok) { posiciones.forEach(ok); return 7; },
    clearWatch(id) { this.limpiado = id; },
  };
}
const pos = (lat, lon, t, accuracy = 5) => ({ coords: { latitude: lat, longitude: lon, accuracy }, timestamp: t });

test("obtenerUbicacion y seguirUbicacion con geolocalización inyectada", async () => {
  const geo = geoFalso([pos(19.43, -99.13, 0), pos(25, -100, 1000), pos(19.431, -99.13, 30_000)]);
  const l = await obtenerUbicacion({}, geo);
  assert.deepEqual([l.lat, l.lon, l.precisionM], [19.43, -99.13, 5]);
  const leidas = [];
  const detener = seguirUbicacion((x) => leidas.push(x.lat), {}, geo);
  assert.deepEqual(leidas, [19.43, 19.431]); // el brinco a Monterrey en 1 s se descarta
  detener();
  assert.equal(geo.limpiado, 7);
  const sinPermiso = { getCurrentPosition: (_, err) => err({ code: 1, message: "denied" }) };
  await assert.rejects(obtenerUbicacion({}, sinPermiso), /Permiso de ubicación denegado/);
});

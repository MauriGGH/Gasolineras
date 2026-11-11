// Utilidades geométricas sin dependencias. Puntos como [lat, lon] (mismo orden que Leaflet
// y que geo/distancia.py). Las distancias van en km, igual que en Python.

export const RADIO_TIERRA_KM = 6371.0088;
/** [latMin, lonMin, latMax, lonMax] aproximada de México. */
export const CAJA_MEXICO = [14.3, -118.7, 32.8, -86.5];

const rad = (g) => (g * Math.PI) / 180;
const grad = (r) => (r * 180) / Math.PI;

/** @param {[number, number]} a @param {[number, number]} b */
export function haversineKm(a, b) {
  const dLat = rad(b[0] - a[0]);
  const dLon = rad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * RADIO_TIERRA_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function puntoDestino(origen, rumboGrados, distanciaKm) {
  const d = distanciaKm / RADIO_TIERRA_KM;
  const th = rad(rumboGrados);
  const [la1, lo1] = [rad(origen[0]), rad(origen[1])];
  const la2 = Math.asin(Math.sin(la1) * Math.cos(d) + Math.cos(la1) * Math.sin(d) * Math.cos(th));
  const lo2 = lo1 + Math.atan2(Math.sin(th) * Math.sin(d) * Math.cos(la1), Math.cos(d) - Math.sin(la1) * Math.sin(la2));
  return [grad(la2), ((grad(lo2) + 540) % 360) - 180];
}

export function enMexico(p) {
  const [lat, lon] = p;
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
  return lat >= CAJA_MEXICO[0] && lat <= CAJA_MEXICO[2] && lon >= CAJA_MEXICO[1] && lon <= CAJA_MEXICO[3];
}

export function cajaDe(puntos, margenKm = 0) {
  let a = Infinity, b = Infinity, c = -Infinity, d = -Infinity;
  for (const [lat, lon] of puntos) {
    a = Math.min(a, lat); c = Math.max(c, lat); b = Math.min(b, lon); d = Math.max(d, lon);
  }
  const dLat = grad(margenKm / RADIO_TIERRA_KM);
  const dLon = dLat / Math.max(Math.cos(rad(Math.max(Math.abs(a), Math.abs(c)) + dLat)), 1e-6);
  return [a - dLat, b - dLon, c + dLat, d + dLon];
}

export const enCaja = (p, c) => p[0] >= c[0] && p[0] <= c[2] && p[1] >= c[1] && p[1] <= c[3];

/** Proyecta p sobre el segmento a-b. Devuelve {t, distanciaKm}. */
export function proyectarEnSegmento(p, a, b) {
  const lat0 = (a[0] + b[0] + p[0]) / 3;
  const k = Math.cos(rad(lat0));
  const plano = (q) => [rad(q[1]) * RADIO_TIERRA_KM * k, rad(q[0]) * RADIO_TIERRA_KM];
  const [px, py] = plano(p), [ax, ay] = plano(a), [bx, by] = plano(b);
  const dx = bx - ax, dy = by - ay;
  const l2 = dx * dx + dy * dy;
  const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2));
  return { t, distanciaKm: Math.hypot(px - (ax + t * dx), py - (ay + t * dy)) };
}

export function longitudesAcumuladas(linea) {
  const acc = [0];
  for (let i = 1; i < linea.length; i++) acc.push(acc[i - 1] + haversineKm(linea[i - 1], linea[i]));
  return acc;
}

/** Proyecta p sobre una polilínea. Devuelve {kmAvance, desvioKm}. */
export function proyectarEnLinea(p, linea, acumulado = longitudesAcumuladas(linea)) {
  if (linea.length < 2) throw new Error("La línea necesita al menos dos puntos");
  let mejor = { desvioKm: Infinity, kmAvance: 0 };
  for (let i = 0; i < linea.length - 1; i++) {
    const { t, distanciaKm } = proyectarEnSegmento(p, linea[i], linea[i + 1]);
    if (distanciaKm < mejor.desvioKm) {
      mejor = { desvioKm: distanciaKm, kmAvance: acumulado[i] + t * (acumulado[i + 1] - acumulado[i]) };
    }
  }
  return mejor;
}

/** Ray casting; el anillo puede venir cerrado o no. */
export function puntoEnPoligono(p, anillo) {
  const [lat, lon] = p;
  let dentro = false;
  for (let i = 0, j = anillo.length - 1; i < anillo.length; j = i++) {
    const [la1, lo1] = anillo[i], [la2, lo2] = anillo[j];
    if (la1 > lat !== la2 > lat && lon < lo1 + ((lat - la1) * (lo2 - lo1)) / (la2 - la1)) dentro = !dentro;
  }
  return dentro;
}

export function distanciaAAnilloKm(p, anillo) {
  let min = Infinity;
  for (let i = 0; i < anillo.length; i++) {
    min = Math.min(min, proyectarEnSegmento(p, anillo[i], anillo[(i + 1) % anillo.length]).distanciaKm);
  }
  return min;
}

export function circuloAPoligono(centro, radioKm, lados = 64) {
  return Array.from({ length: lados }, (_, i) => puntoDestino(centro, (360 * i) / lados, radioKm));
}

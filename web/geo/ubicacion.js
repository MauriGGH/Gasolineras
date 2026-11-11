// Ubicación del usuario con la API de geolocalización del navegador.
// Normaliza a {lat, lon, precisionM, velocidadMps, rumbo, timestamp} y filtra saltos.
// `geo` se puede inyectar (pruebas, Capacitor/React Native, simulador de recorridos).

import { enMexico, haversineKm } from "./distancia.js";

const MENSAJES = {
  1: "Permiso de ubicación denegado. Actívalo en el navegador para ver las gasolineras cercanas.",
  2: "No se pudo obtener la ubicación (sin señal GPS o red).",
  3: "La ubicación tardó demasiado en responder.",
};

export class ErrorUbicacion extends Error {
  constructor(codigo, mensaje) {
    super(MENSAJES[codigo] ?? mensaje ?? "Error de ubicación");
    this.codigo = codigo;
  }
}

const geoPorDefecto = () => globalThis.navigator?.geolocation;

export function normalizarPosicion(pos) {
  const c = pos.coords;
  return {
    lat: c.latitude,
    lon: c.longitude,
    precisionM: c.accuracy,
    velocidadMps: c.speed ?? null,
    rumbo: c.heading ?? null,
    timestamp: pos.timestamp,
  };
}

const OPCIONES = { enableHighAccuracy: true, maximumAge: 10_000, timeout: 15_000 };

/** Una sola lectura (para "gasolineras cerca de mí"). */
export function obtenerUbicacion(opciones = {}, geo = geoPorDefecto()) {
  return new Promise((resolver, rechazar) => {
    if (!geo) return rechazar(new ErrorUbicacion(0, "Este navegador no soporta geolocalización."));
    geo.getCurrentPosition(
      (pos) => resolver(normalizarPosicion(pos)),
      (err) => rechazar(new ErrorUbicacion(err.code, err.message)),
      { ...OPCIONES, ...opciones },
    );
  });
}

/**
 * Filtro de lecturas: descarta precisión mala, puntos fuera de México (opcional)
 * y saltos imposibles (velocidad implícita > velocidadMaxKmh desde la última lectura buena).
 */
export function crearFiltroLecturas({ precisionMaxM = 100, velocidadMaxKmh = 250, soloMexico = false } = {}) {
  let ultima = null;
  return (l) => {
    if (precisionMaxM != null && l.precisionM != null && l.precisionM > precisionMaxM) return false;
    if (soloMexico && !enMexico([l.lat, l.lon])) return false;
    if (ultima) {
      const horas = (l.timestamp - ultima.timestamp) / 3_600_000;
      if (horas <= 0) return false;
      if (haversineKm([ultima.lat, ultima.lon], [l.lat, l.lon]) / horas > velocidadMaxKmh) return false;
    }
    ultima = l;
    return true;
  };
}

/**
 * Sigue la ubicación. Devuelve una función para detener el seguimiento.
 * Conéctalo al monitor: seguirUbicacion((l) => monitor.actualizar(l))
 */
export function seguirUbicacion(alLeer, { alError, filtro = crearFiltroLecturas(), ...opciones } = {}, geo = geoPorDefecto()) {
  if (!geo) {
    alError?.(new ErrorUbicacion(0, "Este navegador no soporta geolocalización."));
    return () => {};
  }
  const id = geo.watchPosition(
    (pos) => {
      const l = normalizarPosicion(pos);
      if (!filtro || filtro(l)) alLeer(l);
    },
    (err) => alError?.(new ErrorUbicacion(err.code, err.message)),
    { ...OPCIONES, maximumAge: 2_000, ...opciones },
  );
  return () => geo.clearWatch(id);
}

const NUM = String.raw`[-+]?\d+(?:[.,]\d+)?`;

/** Mismo comportamiento que geo.geocodificacion.parsear_coordenadas. Devuelve [lat, lon] o null. */
export function parsearCoordenadas(texto) {
  let t = texto.trim();
  const arroba = t.match(new RegExp(`@(${NUM}),(${NUM})`));
  if (arroba) t = `${arroba[1]},${arroba[2]}`;
  const m = t.match(new RegExp(String.raw`^\s*\(?\s*(${NUM})\s*[,;\s]\s*(${NUM})\s*\)?\s*$`));
  if (m) {
    let [a, b] = [m[1], m[2]].map((x) => Number(x.replace(",", ".")));
    if (!enMexico([a, b]) && enMexico([b, a])) [a, b] = [b, a];
    return Math.abs(a) <= 90 && Math.abs(b) <= 180 ? [a, b] : null;
  }
  const dms = [...t.matchAll(/(\d+(?:\.\d+)?)\s*[°º]\s*(?:(\d+(?:\.\d+)?)\s*['′]\s*)?(?:(\d+(?:\.\d+)?)\s*(?:"|″|'')\s*)?([NSEWO])/gi)];
  if (dms.length === 2) {
    const v = {};
    for (const [, g, mi, s, h] of dms) {
      const H = h.toUpperCase();
      const x = (Number(g) + Number(mi ?? 0) / 60 + Number(s ?? 0) / 3600) * ("SWO".includes(H) ? -1 : 1);
      v["NS".includes(H) ? "lat" : "lon"] = x;
    }
    if (v.lat != null && v.lon != null) return [v.lat, v.lon];
  }
  return null;
}

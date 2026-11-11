// Geocercas en el navegador a partir del GeoJSON que produce geo/geocercas.py
// (Geocerca.a_geojson / a_feature_collection), o de cualquier Feature compatible:
//   Point + radio_km|radio_m  -> círculo
//   Polygon / MultiPolygon    -> polígono (respeta huecos)
//   LineString + ancho_km|ancho_m -> corredor de ruta

import {
  cajaDe, circuloAPoligono, distanciaAAnilloKm, enCaja, haversineKm,
  longitudesAcumuladas, proyectarEnLinea, puntoEnPoligono,
} from "./distancia.js";

const anilloDeGeojson = (coords) => {
  const a = coords.map(([lon, lat]) => [lat, lon]);
  const [p, u] = [a[0], a[a.length - 1]];
  if (a.length > 1 && p[0] === u[0] && p[1] === u[1]) a.pop();
  return a;
};
const anilloAGeojson = (anillo) => {
  const c = anillo.map(([lat, lon]) => [lon, lat]);
  return [...c, c[0]];
};

class Geocerca {
  constructor({ id, nombre, tipo, centro, radioKm, poligonos, linea, anchoKm, propiedades = {} }) {
    Object.assign(this, { id, nombre: nombre ?? id, tipo, centro, radioKm, poligonos, linea, anchoKm, propiedades });
    if (tipo === "corredor") this._acumulado = longitudesAcumuladas(linea);
    this.caja =
      tipo === "circulo" ? cajaDe([centro], radioKm)
      : tipo === "corredor" ? cajaDe(linea, anchoKm)
      : cajaDe(poligonos.flatMap((p) => p[0]));
  }

  contiene(p) {
    if (!enCaja(p, this.caja)) return false;
    return this.distanciaBordeKm(p) <= 0;
  }

  /** Distancia con signo al borde (negativa dentro). */
  distanciaBordeKm(p) {
    switch (this.tipo) {
      case "circulo":
        return haversineKm(this.centro, p) - this.radioKm;
      case "corredor":
        return proyectarEnLinea(p, this.linea, this._acumulado).desvioKm - this.anchoKm;
      default: {
        const dentro = this.poligonos.some(
          ([ext, ...huecos]) => puntoEnPoligono(p, ext) && !huecos.some((h) => puntoEnPoligono(p, h)),
        );
        const d = Math.min(...this.poligonos.flat().map((a) => distanciaAAnilloKm(p, a)));
        return dentro ? -d : d;
      }
    }
  }

  /** Feature para pintar. Los círculos salen como Polygon (MapLibre/Mapbox no dibujan círculos en metros). */
  aGeojson() {
    const properties = { ...this.propiedades, id: this.id, nombre: this.nombre, tipo: this.tipo };
    let geometry;
    if (this.tipo === "circulo") {
      geometry = { type: "Polygon", coordinates: [anilloAGeojson(circuloAPoligono(this.centro, this.radioKm))] };
      properties.radio_km = this.radioKm;
    } else if (this.tipo === "corredor") {
      geometry = { type: "LineString", coordinates: this.linea.map(([lat, lon]) => [lon, lat]) };
      properties.ancho_km = this.anchoKm;
    } else {
      geometry = { type: "MultiPolygon", coordinates: this.poligonos.map((p) => p.map(anilloAGeojson)) };
    }
    return { type: "Feature", geometry, properties };
  }
}

export function circulo(id, centro, radioKm, propiedades = {}) {
  return new Geocerca({ id, nombre: propiedades.nombre, tipo: "circulo", centro, radioKm, propiedades });
}

export function poligono(id, vertices, propiedades = {}) {
  return new Geocerca({ id, nombre: propiedades.nombre, tipo: "poligono", poligonos: [[vertices]], propiedades });
}

export function corredor(id, linea, anchoKm, propiedades = {}) {
  if (linea.length < 2) throw new Error("Un corredor necesita una línea de 2+ puntos");
  return new Geocerca({ id, nombre: propiedades.nombre, tipo: "corredor", linea, anchoKm, propiedades });
}

export function desdeGeojson(feature) {
  const { geometry: g } = feature;
  const props = { ...(feature.properties ?? {}) };
  const id = String(props.id ?? feature.id ?? props.CVEGEO ?? "");
  const nombre = props.nombre ?? props.NOMGEO ?? id;
  for (const k of ["id", "nombre", "tipo", "centro"]) delete props[k];
  if (g.type === "Point") {
    const radioKm = props.radio_km ?? (props.radio_m != null ? props.radio_m / 1000 : undefined);
    if (radioKm == null) throw new Error(`El punto ${id} necesita radio_km o radio_m`);
    const [lon, lat] = g.coordinates;
    return new Geocerca({ id, nombre, tipo: "circulo", centro: [lat, lon], radioKm, propiedades: props });
  }
  if (g.type === "LineString") {
    const anchoKm = props.ancho_km ?? (props.ancho_m != null ? props.ancho_m / 1000 : undefined);
    if (anchoKm == null) throw new Error(`La línea ${id} necesita ancho_km o ancho_m`);
    const linea = g.coordinates.map(([lon, lat]) => [lat, lon]);
    return new Geocerca({ id, nombre, tipo: "corredor", linea, anchoKm, propiedades: props });
  }
  if (g.type === "Polygon" || g.type === "MultiPolygon") {
    const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    const poligonos = polys.map((p) => p.map(anilloDeGeojson));
    return new Geocerca({ id, nombre, tipo: g.type === "Polygon" ? "poligono" : "multipoligono", poligonos, propiedades: props });
  }
  throw new Error(`Geometría no soportada para geocerca: ${g.type}`);
}

export const geocercasDesdeGeojson = (fc) => fc.features.map(desdeGeojson);

/**
 * Monitor en vivo con histéresis, filtro de precisión y aviso de permanencia.
 * Misma semántica que geo/monitor.py. Tiempos en ms (timestamp del GPS).
 */
export class MonitorGeocercas {
  constructor(geocercas = [], { histeresisKm = 0.03, precisionMaxM = 100, permanenciaMs = null, eventoInicial = true } = {}) {
    Object.assign(this, { histeresisKm, precisionMaxM, permanenciaMs, eventoInicial });
    this._geocercas = new Map();
    this._estado = new Map();
    this._oyentes = new Set();
    geocercas.forEach((g) => this.agregar(g));
  }

  agregar(g) { this._geocercas.set(g.id, g); this._estado.delete(g.id); }
  quitar(id) { this._geocercas.delete(id); this._estado.delete(id); }
  dentroDe() { return [...this._estado].filter(([, e]) => e.dentro).map(([id]) => this._geocercas.get(id)).filter(Boolean); }

  /** Registra un oyente; devuelve la función para quitarlo. */
  alEvento(fn) { this._oyentes.add(fn); return () => this._oyentes.delete(fn); }

  /** @param {{lat:number, lon:number, timestamp:number, precisionM?:number}} lectura */
  actualizar({ lat, lon, timestamp, precisionM }) {
    if (this.precisionMaxM != null && precisionM != null && precisionM > this.precisionMaxM) return [];
    const p = [lat, lon];
    const eventos = [];
    for (const [id, g] of this._geocercas) {
      const e = this._estado.get(id);
      const antes = e?.dentro;
      let ahora = false;
      if (antes || enCaja(p, g.caja)) {
        const d = g.distanciaBordeKm(p);
        ahora = antes ? d <= this.histeresisKm : d <= 0;
      }
      const ev = (tipo, extra = {}) => eventos.push({ tipo, geocerca: g, lat, lon, timestamp, ...extra });
      if (!e) {
        this._estado.set(id, { dentro: ahora, desde: ahora ? timestamp : null, avisada: false });
        if (ahora && this.eventoInicial) ev("entrada");
      } else if (ahora && !antes) {
        this._estado.set(id, { dentro: true, desde: timestamp, avisada: false });
        ev("entrada");
      } else if (antes && !ahora) {
        ev("salida", { permanenciaMs: timestamp - e.desde });
        this._estado.set(id, { dentro: false, desde: null, avisada: false });
      } else if (ahora && this.permanenciaMs != null && !e.avisada && timestamp - e.desde >= this.permanenciaMs) {
        e.avisada = true;
        ev("permanencia", { permanenciaMs: timestamp - e.desde });
      }
    }
    for (const evento of eventos) for (const fn of this._oyentes) fn(evento);
    return eventos;
  }
}

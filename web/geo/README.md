# @gasolineras/geo (navegador)

Ubicación del usuario y geocercas del lado del cliente, sin dependencias ni build
(módulos ES). Lee el mismo GeoJSON que produce `geo/geocercas.py`
(`a_feature_collection`, `zonas_de_referencia`, `geocercas_de_estaciones`), así que el
backend define las zonas y el front las vigila con el GPS del teléfono.

Puntos como `[lat, lon]` (orden de Leaflet y de `geo/` en Python), distancias en km.

```js
import { geocercasDesdeGeojson, MonitorGeocercas, seguirUbicacion, obtenerUbicacion } from "./web/geo/index.js";

// 1) "Gasolineras cerca de mí"
const yo = await obtenerUbicacion();           // {lat, lon, precisionM, timestamp, ...}

// 2) Geocercas que manda el backend (estaciones, corredor de la ruta, zonas de referencia)
const fc = await fetch("/api/geocercas").then((r) => r.json());
const monitor = new MonitorGeocercas(geocercasDesdeGeojson(fc), {
  histeresisKm: 0.03,      // hay que alejarse 30 m del borde para "salir" (evita rebotes del GPS)
  precisionMaxM: 100,      // ignora lecturas con precisión peor a 100 m
  permanenciaMs: 5 * 60e3, // aviso de "permanencia" tras 5 min dentro (p. ej. pipa descargando)
});
monitor.alEvento((e) => console.log(e.tipo, e.geocerca.nombre)); // entrada | salida | permanencia

// 3) Seguimiento continuo; descarta saltos imposibles (> 250 km/h)
const detener = seguirUbicacion((lectura) => monitor.actualizar(lectura), {
  alError: (err) => mostrarAviso(err.message),  // mensajes ya en español
});

// Pintar en el mapa: g.aGeojson() (los círculos salen como Polygon para MapLibre)
```

También exporta `parsearCoordenadas` (para el buscador: "19.43, -99.13", enlaces de
Google Maps, grados-minutos-segundos), `haversineKm`, `proyectarEnLinea`, etc.

Pruebas: `npm test` (Node 20+). Incluye una prueba cruzada contra un GeoJSON generado
por la versión de Python para garantizar que ambos lados dan el mismo dentro/fuera.

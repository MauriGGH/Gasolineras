/* Ojo de Dios · Gasolineras MX — interfaz.
   Todas las cifras llegan de la API local (app/main.py); aquí no hay datos incrustados.
   Si un dato no existe se escribe "sin dato": nunca un cero ni un estimado.

   Orden del archivo:
     1. utilidades y arranque          6. piezas de los expedientes
     2. datos, estado y escalas        7. herramientas (ranking, marcas, buscador, cerca, ruta…)
     3. mapa y cámara                  8. panel único y línea de tiempo
     4. objetivo fijado (secuencia)    9. controles y atajos de teclado
     5. tooltips y cifras animadas */
"use strict";

/* ================= 1. UTILIDADES Y ARRANQUE ================= */
const $ = id => document.getElementById(id);
const fmt  = n => Number(n).toLocaleString("es-MX");
const fmt1 = n => Number(n).toLocaleString("es-MX", {minimumFractionDigits:1, maximumFractionDigits:1});
const fmt2 = n => Number(n).toLocaleString("es-MX", {minimumFractionDigits:2, maximumFractionDigits:2});
const pesos = n => "$" + fmt2(n);
const sinMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;
const angosta = matchMedia("(max-width: 720px)");      // móvil: los paneles son hojas inferiores

// Datos faltantes: `hay` dice si un valor existe; `con` lo formatea o escribe "sin dato".
const SIN = `<span class="sd">sin dato</span>`;
const hay = v => typeof v === "number" ? Number.isFinite(v) : (v !== null && v !== undefined && v !== "");
const con = (v, f) => hay(v) ? f(v) : SIN;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

async function pedir(ruta, opciones){
  const r = await fetch(ruta, opciones);
  if(!r.ok){
    let det = ""; try { det = (await r.json()).detail; } catch(_){}
    throw new Error(`${ruta} respondió ${r.status}${det ? ": " + (typeof det === "string" ? det : JSON.stringify(det)) : ""}`);
  }
  return r.json();
}
const enviar = (ruta, cuerpo) => pedir(ruta, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(cuerpo)});

/* Secuencia de arranque: cada línea reporta una comprobación real */
function arranque(lineas){
  const caja = $("arranque"), log = $("arr-log");
  const cerrar = () => caja.classList.add("fuera");
  caja.addEventListener("click", cerrar);
  if(sinMovimiento){ cerrar(); return; }
  lineas.forEach((t,i) => setTimeout(() => { log.textContent += t + "\n"; }, 170*i));
  setTimeout(cerrar, 170*lineas.length + 550);
}

// Capitales y ciudades: puntos de partida rápidos para rutas y surtido (también se puede elegir en el mapa)
const CAPITALES = [
  ["Aguascalientes, Ags.",21.8818,-102.2916],["Mexicali, B.C.",32.6245,-115.4523],["Tijuana, B.C.",32.5149,-117.0382],
  ["La Paz, B.C.S.",24.1426,-110.3128],["Campeche, Camp.",19.8301,-90.5349],["Saltillo, Coah.",25.4232,-101.0053],
  ["Colima, Col.",19.2433,-103.7250],["Tuxtla Gutiérrez, Chis.",16.7516,-93.1029],["Chihuahua, Chih.",28.6353,-106.0889],
  ["Ciudad Juárez, Chih.",31.6904,-106.4245],["CDMX · Zócalo",19.4326,-99.1332],["Durango, Dgo.",24.0277,-104.6532],
  ["Guanajuato, Gto.",21.0190,-101.2574],["León, Gto.",21.1250,-101.6860],["Chilpancingo, Gro.",17.5515,-99.5006],
  ["Acapulco, Gro.",16.8531,-99.8237],["Pachuca, Hgo.",20.1011,-98.7591],["Guadalajara, Jal.",20.6597,-103.3496],
  ["Toluca, Edomex.",19.2826,-99.6557],["Morelia, Mich.",19.7060,-101.1950],["Cuernavaca, Mor.",18.9242,-99.2216],
  ["Tepic, Nay.",21.5042,-104.8946],["Monterrey, N.L.",25.6866,-100.3161],["Oaxaca, Oax.",17.0732,-96.7266],
  ["Puebla, Pue.",19.0414,-98.2063],["Querétaro, Qro.",20.5888,-100.3899],["Chetumal, Q. Roo",18.5001,-88.2961],
  ["Cancún, Q. Roo",21.1619,-86.8515],["San Luis Potosí, S.L.P.",22.1565,-100.9855],["Culiacán, Sin.",24.8091,-107.3940],
  ["Hermosillo, Son.",29.0729,-110.9559],["Villahermosa, Tab.",17.9892,-92.9475],["Ciudad Victoria, Tamps.",23.7369,-99.1411],
  ["Nuevo Laredo, Tamps.",27.4779,-99.5496],["Tlaxcala, Tlax.",19.3182,-98.2375],["Xalapa, Ver.",19.5438,-96.9102],
  ["Veracruz, Ver.",19.1738,-96.1342],["Mérida, Yuc.",20.9674,-89.5926],["Zacatecas, Zac.",22.7709,-102.5833],
];
// Vehículos de referencia para la ruta: tanque (l), rendimiento (km/l), producto
const VEHICULOS = [
  {k:"sedan", rot:"Auto", tanque:45, rend:14, prod:"regular"},
  {k:"pickup", rot:"Pick up", tanque:80, rend:9, prod:"regular"},
  {k:"tracto", rot:"Tracto", tanque:600, rend:2.6, prod:"diesel"},
  {k:"moto", rot:"Moto", tanque:15, rend:30, prod:"regular"},
];
// Colores por marca: los de las marcas grandes son fijos; el resto toma uno de reserva
const COLOR_MARCA = { "Pemex":"#2fbf71", "Oxxo Gas":"#ff4130", "G500":"#ffb224", "BP":"#9ad94f", "Shell":"#ffe14a",
  "Mobil":"#5aa2ff", "Chevron":"#62d3e8", "TotalEnergies":"#ff7ad1", "Arco":"#4fd8c4", "Repsol":"#ff8a3d",
  "Hidrosina":"#c98bff", "Petro-7":"#f2f2f2", "Independiente":"#7488a0" };
const RESERVA = ["#b48cff","#7ee08a","#ffa3a3","#9bd7ff","#e6c07b","#a0a0ff"];
const colorMarca = (() => { const asignado = {}; let i = 0;
  return m => COLOR_MARCA[m] ?? (asignado[m] ??= RESERVA[i++ % RESERVA.length]); })();

async function iniciar(){
/* ================= 2. DATOS, ESTADO Y ESCALAS ================= */
const [DATOS, GEO, CRUDO] = await Promise.all([pedir("/api/datos"), pedir("/api/geo/estados"), pedir("/api/estaciones")]);
let MOTOR = null;
try { MOTOR = await pedir("/api/ruteo/salud"); } catch(_){ /* sin motor de rutas: las herramientas lo avisan */ }

const FECHAS = DATOS.fechas, E = DATOS.entidades, NAC = DATOS.nacional, PRODUCTOS = DATOS.productos;
const NOMBRES = Object.keys(E);
const ULT = FECHAS.length - 1;
const COL = Object.fromEntries(CRUDO.columnas.map((c,i) => [c,i]));
const EST = CRUDO.filas.map((f,i) => ({ i, permiso:f[COL.permiso], nombre:f[COL.nombre], marca:f[COL.marca], lat:f[COL.lat], lon:f[COL.lon],
  entidad:f[COL.entidad], horario:f[COL.horario], precios:{regular:f[COL.regular], premium:f[COL.premium], diesel:f[COL.diesel]} }));
const POR_PERMISO = new Map(EST.map(e => [e.permiso, e]));
const NOM_PROD = { regular:"Regular", premium:"Premium", diesel:"Diésel" };
const fechaTxt = f => /^\d{4}-\d{2}-\d{2}$/.test(f) ? new Date(f+"T12:00").toLocaleDateString("es-MX", {day:"numeric", month:"short", year:"numeric"}) : f;
const fechaCorta = f => /^\d{4}-\d{2}-\d{2}$/.test(f) ? new Date(f+"T12:00").toLocaleDateString("es-MX", {day:"numeric", month:"short"}) : f;

// Comprobación en el navegador: la suma de estaciones por entidad no puede pasar del total nacional
const sumaEst = d3.sum(NOMBRES, n => E[n].estaciones);
const huach = NAC.huachicol?.petroliferos;
arranque([
  "› enlace con API local ................. OK",
  `› gasolineras cargadas ................. ${fmt(EST.length)}${DATOS.demo ? " (DEMO)" : ""}`,
  `› entidades con estaciones ............. ${NOMBRES.filter(n => E[n].estaciones).length} de ${NOMBRES.length}`,
  `› suma por entidad ≤ total nacional .... ${sumaEst <= NAC.estaciones ? "OK" : "NO CUADRA"}`,
  `› cortes de precio ..................... ${FECHAS.length} · último ${fechaCorta(FECHAS[ULT])}`,
  `› motor de rutas ....................... ${MOTOR ? MOTOR.motor.toUpperCase() : "SIN CONEXIÓN"}`,
  `› tomas (ref. ${huach ? huach.anio : "s/d"}) ...................... ${huach ? huach.estados_con_dato + " estados" : "sin dato"}`,
  "› proyección cónica conforme fijada .... OK",
]);
$("estatus").textContent = `En línea · ${fmt(EST.length)} gasolineras${DATOS.demo ? " SINTÉTICAS" : ""} · corte ${fechaTxt(FECHAS[ULT])} · motor ${MOTOR ? MOTOR.motor : "sin conexión"}`;
if(DATOS.demo){ $("demo").hidden = false; $("demo").textContent = "◆ DEMO · " + DATOS.aviso; $("fuentes-demo").hidden = false; }

// Lo que el usuario eligió ver en el mapa
const estado = { metrica:"regular", f:ULT, sel:null, cmp:null, eligeCmp:false, vista:"coro", marca:null, est:null,
                 capas:{estaciones:true, focos:true, etiq:false, ret:true, barrido:true, cinta:false} };
// Lo que está abierto encima del mapa. `panel` es una herramienta; el expediente aparece solo cuando hay objetivo.
const ui = { panel:null, franja:false, origen:null, elige:null, modo:"viaje", secc:{ent:"precios", nac:"precios", cmp:"precios"} };
const app = $("app");

const rampaCalor = d3.interpolateRgbBasis(["#17293b","#4a3230","#a35a1c","#ffb224","#ff4130"]);
const rampaFria  = d3.interpolateRgbBasis(["#17293b","#15475a","#2a8ba3","#62d3e8","#d8f7ff"]);
const esPrecio = m => PRODUCTOS.includes(m);
const precioEnt = (e, p, f) => (e.serie[p] && hay(e.serie[p][f])) ? e.serie[p][f] : (f === ULT ? e.precio[p]?.prom : null);
function dominioPrecio(p){
  const v = NOMBRES.flatMap(n => FECHAS.map((_,f) => precioEnt(E[n], p, f))).filter(hay);
  return v.length ? [d3.min(v), d3.max(v)] : [0,1];
}
const maxEst = d3.max(NOMBRES, n => E[n].estaciones) || 1;
const tomas = e => e.huachicol?.petroliferos?.tomas;
const maxTomas = d3.max(NOMBRES, n => tomas(E[n])) || 1;
const METRICAS = {};
PRODUCTOS.forEach(p => { const [a,b] = dominioPrecio(p);
  METRICAS[p] = { titulo:`${NOM_PROD[p]} · precio promedio MXN/l`, rampa:rampaCalor, asc:true, serie:true,
    escala:d3.scaleLinear().domain([a, b === a ? a + 0.01 : b]).range([0,1]).clamp(true),
    valor:(e,f) => precioEnt(e,p,f), texto:v => pesos(v), min:pesos(a), max:pesos(b) }; });
METRICAS.estaciones = { titulo:"Gasolineras por entidad", rampa:rampaFria, asc:false,
  escala:d3.scaleSqrt().domain([0,maxEst]).range([0,1]).clamp(true), valor:e => e.estaciones, texto:v => fmt(v), min:"0", max:fmt(maxEst) };
METRICAS.tomas = { titulo:`Tomas clandestinas reportadas · ${huach ? huach.anio : ""} (referencia)`, rampa:rampaCalor, asc:false,
  escala:d3.scaleSqrt().domain([0,maxTomas]).range([0,1]).clamp(true), valor:e => tomas(e), texto:v => fmt(v), min:"0", max:fmt(maxTomas) };
const SIN_COLOR = "#161d29";                        // entidad sin dato: gris neutro, fuera de la rampa
const M = () => METRICAS[estado.metrica];
const prodActual = () => esPrecio(estado.metrica) ? estado.metrica : "regular";
const val = n => M().valor(E[n], estado.f);
const color = n => hay(val(n)) ? M().rampa(M().escala(val(n))) : SIN_COLOR;
// Orden del ranking: en precio, el más barato primero; en lo demás, el mayor primero. Lo que falta va al final.
const cmpVal = (m, a, b) => { const va = m.valor(E[a], estado.f), vb = m.valor(E[b], estado.f);
  if(!hay(va) && !hay(vb)) return 0; if(!hay(va)) return 1; if(!hay(vb)) return -1; return m.asc ? va - vb : vb - va; };
const ordenados = () => NOMBRES.slice().sort((a,b) => cmpVal(M(), a, b));
const lugarDe = (n, metrica = estado.metrica) => { const m = METRICAS[metrica];
  return hay(m.valor(E[n], estado.f)) ? NOMBRES.slice().sort((a,b) => cmpVal(m,a,b)).indexOf(n)+1 : null; };
const variacion = (ahora, antes) => (hay(ahora) && hay(antes) && antes !== 0) ? (ahora/antes-1)*100 : null;
const txtVariacion = (v, f) => v === null ? "" :
  `<span class="${v<0?"baja":"sube"} num">${v<0?"▼":"▲"} ${fmt1(Math.abs(v))} % vs ${fechaCorta(FECHAS[f-1])}</span>`;

/* ================= 3. MAPA Y CÁMARA ================= */
const svg = d3.select("#svg"), cont = $("mapa");
svg.append("defs").html(`
  <pattern id="pat-lineas" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.3" fill="#d8f7ff"/></pattern>
  <linearGradient id="grad-barre" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#62d3e8" stop-opacity="0"/><stop offset=".9" stop-color="#62d3e8" stop-opacity=".3"/>
    <stop offset="1" stop-color="#d8f7ff" stop-opacity="1"/></linearGradient>
  <clipPath id="clip-holo-a"><path/></clipPath><clipPath id="clip-holo-b"><path/></clipPath>`);
const gZoom = svg.append("g");
const gRet   = gZoom.append("path").attr("class","reticula");
const gEdos  = gZoom.append("g");
const gHolo  = gZoom.append("g").style("opacity",0);
const gBurb  = gZoom.append("g");
const gEtq   = gZoom.append("g");
const gAnillo= gZoom.append("circle").attr("class","anillo").attr("r",0);
const gCandB = gZoom.append("path").attr("class","candado b");
const gCand  = gZoom.append("path").attr("class","candado");
const gBarre = gZoom.append("rect").attr("class","barre").attr("fill","url(#grad-barre)");
const gGeo   = gZoom.append("g");                   // geocerca y ubicación
const gRuta  = gZoom.append("g");                   // rutas y viajes de pipa
const gEst   = gZoom.append("g");                   // gasolineras
const gFocos = gZoom.append("g");                   // focos municipales de referencia (tomas)
const gMarcas= gZoom.append("g");                   // paradas numeradas y extremos, encima de todo
const gEstSel= gZoom.append("circle").attr("class","est-sel").attr("r",0);
const miraV = svg.append("line").attr("class","mira"), miraH = svg.append("line").attr("class","mira");
const miraC = svg.append("circle").attr("class","mira-c").attr("r",9).attr("cx",-99);
// Cónica Conforme de Lambert con los parámetros que usa INEGI para la República
const proy = d3.geoConicConformal().parallels([17.5,29.5]).rotate([102,0]).center([0,24]);
const ruta = d3.geoPath(proy);
const FT = Object.fromEntries(GEO.features.map(f => [f.properties.nombre, f]));
let k = 1, T = d3.zoomIdentity, C = {}, primera = true;
let PAIS = [[0,0],[1,1]];
let camaraLibre = false;
const rBurb = n => hay(val(n)) ? 5 + 34*M().escala(val(n)) : 0;
// Radio de las gasolineras en pantalla: crece un poco al acercar, sin tapar el mapa
const rEst = () => Math.min(5.5, 1.8 + 0.5*Math.sqrt(k)) / k;

const zoom = d3.zoom().scaleExtent([0.35,80]).on("zoom", ev => {
  if(ev.sourceEvent) camaraLibre = true;
  T = ev.transform; k = T.k; gZoom.attr("transform", T);
  gFocos.selectAll("circle.nucleo").attr("r", 3/k);
  gFocos.selectAll("circle.onda").attr("r", d => d.r/Math.sqrt(k));
  gBurb.selectAll("circle").attr("r", d => rBurb(d)/Math.sqrt(k));
  gEtq.selectAll("text").attr("font-size", 10.5/k);
  gEtq.selectAll("tspan.v").attr("dy", 11/k);
  gEst.selectAll("circle").attr("r", rEst());
  gEstSel.attr("r", estado.est ? 9/k : 0);
  escalarMarcas();
  posarHolo();
  $("hud-zoom").innerHTML = `ZOOM <b>×${k.toFixed(1)}</b>`;
});
svg.call(zoom).on("dblclick.zoom", null);

function zonaLibre(conPaneles = true){
  const w = cont.clientWidth, h = cont.clientHeight, movil = angosta.matches;
  const hayPanel = conPaneles && !!vistaActual(), hayFranja = conPaneles && ui.franja;
  const barra = movil ? $("barra").offsetHeight : $("barra").offsetWidth;
  const franja = hayFranja ? $("franja").offsetHeight : 0;
  if(movil) return { x0:0, y0:0, x1:w, y1:h - barra - franja - (hayPanel ? Math.round(h*(hayFranja ? .46 : .58)) : 0) };
  return { x0:0, y0:0, x1:w - barra - (hayPanel ? $("panel").offsetWidth : 0), y1:h - franja };
}
function zonaPais(conPaneles){
  const z = zonaLibre(conPaneles), movil = angosta.matches;
  const m = movil ? {i:10, s:92, d:10, b:conPaneles && vistaActual() ? 10 : 92} : {i:20, s:112, d:16, b:40};
  return { x0:z.x0+m.i, y0:z.y0+m.s, x1:Math.max(z.x0+m.i+80, z.x1-m.d), y1:Math.max(z.y0+m.s+80, z.y1-m.b) };
}
function encuadre(caja, zona, factor = 1, tope = 14){
  const [[x0,y0],[x1,y1]] = caja, zw = zona.x1-zona.x0, zh = zona.y1-zona.y0;
  const s = Math.min(tope, factor * Math.min(zw/Math.max(1e-6,x1-x0), zh/Math.max(1e-6,y1-y0)));
  return d3.zoomIdentity.translate((zona.x0+zona.x1)/2, (zona.y0+zona.y1)/2).scale(s).translate(-(x0+x1)/2, -(y0+y1)/2);
}
function volar(t, dur = TIEMPOS.vuelo){
  camaraLibre = false;
  svg.interrupt("camara");
  svg.transition("camara").duration(sinMovimiento ? 0 : dur).call(zoom.transform, t);
}
const zonaObjetivo = () => { const z = zonaLibre(), movil = angosta.matches;
  return movil ? {x0:z.x0+26, y0:z.y0+96, x1:z.x1-26, y1:z.y1-22} : {x0:z.x0+60, y0:z.y0+110, x1:z.x1-60, y1:z.y1-70}; };
// Vuela al objetivo (o a los dos que se comparan); sin objetivo, al país completo
function enfocar(){
  const obj = [estado.sel, estado.cmp].filter(Boolean);
  if(!obj.length){ volar(encuadre(PAIS, zonaPais(true))); return; }
  const cajas = obj.map(n => ruta.bounds(FT[n]));
  const caja = [[d3.min(cajas, c => c[0][0]), d3.min(cajas, c => c[0][1])], [d3.max(cajas, c => c[1][0]), d3.max(cajas, c => c[1][1])]];
  volar(encuadre(caja, zonaObjetivo(), .82, 9));
}
// Vuela a un conjunto de coordenadas [lon, lat] (ruta, geocerca, estación). `minimo` evita acercar de más a un solo punto.
function volarA(puntosLonLat, tope = 40, minimo = 0.02){
  const p = puntosLonLat.map(c => proy(c)).filter(Boolean);
  if(!p.length) return;
  let [x0,x1] = d3.extent(p, q => q[0]), [y0,y1] = d3.extent(p, q => q[1]);
  const lado = Math.max(x1-x0, y1-y0, minimo * (PAIS[1][0]-PAIS[0][0]));
  const cx = (x0+x1)/2, cy = (y0+y1)/2;
  volar(encuadre([[cx-lado/2, cy-lado/2],[cx+lado/2, cy+lado/2]], zonaObjetivo(), .9, tope));
}
function acomodarCamara(){ if(estado.sel || !camaraLibre) enfocar(); }

function dibujar(){
  const w = cont.clientWidth, h = cont.clientHeight, z = zonaPais(false);
  svg.attr("viewBox", `0 0 ${w} ${h}`);
  proy.fitExtent([[z.x0,z.y0],[z.x1,z.y1]], GEO);
  PAIS = ruta.bounds(GEO);
  NOMBRES.forEach(n => C[n] = ruta.centroid(FT[n]));
  gRet.attr("d", ruta(d3.geoGraticule().step([4,4]).extent([[-120,12],[-84,34]])()));

  const p = gEdos.selectAll("path").data(GEO.features, d => d.properties.nombre).join("path")
    .attr("class","estado").attr("d", ruta)
    .on("click", (ev,d) => { ev.stopPropagation(); if(eligiendo(ev)) return; seleccionar(d.properties.nombre, ev.shiftKey); })
    .on("pointermove", (ev,d) => tip(ev, d.properties.nombre))
    .on("pointerleave", ocultarTip);
  if(primera && !sinMovimiento){
    p.style("opacity",0).transition().delay(d => 900 + (C[d.properties.nombre][1]/h)*700).duration(450).style("opacity",1)
     .on("end", function(){ d3.select(this).style("opacity",null); });
  }

  // Gasolineras: un punto por estación, con el color de su marca
  EST.forEach(e => e.p = proy([e.lon, e.lat]));
  const pe = gEst.selectAll("circle").data(EST, d => d.i).join("circle")
    .attr("class","est").attr("cx", d => d.p[0]).attr("cy", d => d.p[1]).attr("r", rEst()).attr("fill", d => colorMarca(d.marca))
    .on("pointermove", (ev,d) => tipEst(ev,d)).on("pointerleave", ocultarTip)
    .on("click", (ev,d) => { ev.stopPropagation(); if(eligiendo(ev)) return; clicEstacion(d); });
  if(primera && !sinMovimiento) pe.style("opacity",0).transition().delay(d => 1500 + (d.p[1]/h)*500).duration(300).style("opacity",null);
  primera = false;

  // Focos municipales de tomas reportadas (referencia, en la cabecera municipal)
  const rFoco = d3.scaleSqrt().domain([0, d3.max(DATOS.municipios, m => m.tomas) || 1]).range([4,22]);
  const f = gFocos.selectAll("g").data(DATOS.municipios.map(m => ({...m, p:proy([m.lon,m.lat]), r:rFoco(m.tomas)})), d => d.cve_mun)
    .join(en => { const g = en.append("g").attr("class","foco"); g.append("circle").attr("class","onda"); g.append("circle").attr("class","nucleo"); return g; })
    .attr("transform", d => `translate(${d.p})`)
    .on("pointermove", (ev,d) => tipFoco(ev,d)).on("pointerleave", ocultarTip)
    .on("click", (ev,d) => { ev.stopPropagation(); if(eligiendo(ev)) return; if(estado.sel !== d.entidad){ ui.secc.ent = "tomas"; seleccionar(d.entidad); } });
  f.select(".onda").attr("r", d => d.r/Math.sqrt(k)).style("animation-delay", (d,i) => (i*0.17)+"s");
  f.select(".nucleo").attr("r", 3/k);
  pintar(); armarHolo(); candado(false); pintarGeocerca(); pintarRuta(); marcarEstacion();
}

/* Colores, burbujas, etiquetas y capas según el estado actual */
function pintar(){
  const burb = estado.vista === "burb";
  gEdos.selectAll("path")
    .attr("fill", d => burb ? "#13233a" : color(d.properties.nombre))
    .classed("sel", d => d.properties.nombre === estado.sel)
    .classed("cmp", d => d.properties.nombre === estado.cmp)
    .classed("lider", d => !!estado.marca && E[d.properties.nombre].marca_lider === estado.marca)
    .classed("apagado", d => !!estado.marca && E[d.properties.nombre].marca_lider !== estado.marca);

  gBurb.selectAll("circle").data(burb ? ordenados().slice().reverse() : [], d => d).join(
      en => en.append("circle").attr("class","burbuja").attr("r",0)
              .attr("cx", d => C[d][0]).attr("cy", d => C[d][1])
              .on("click", (ev,d) => { ev.stopPropagation(); seleccionar(d, ev.shiftKey); })
              .on("pointermove", (ev,d) => tip(ev,d)).on("pointerleave", ocultarTip),
      up => up, ex => ex.transition().duration(300).attr("r",0).remove())
    .order()
    .attr("cx", d => C[d][0]).attr("cy", d => C[d][1])
    .transition().duration(sinMovimiento ? 0 : 600)
    .attr("r", d => rBurb(d)/Math.sqrt(k)).attr("fill", d => color(d));

  gEtq.selectAll("text").data(estado.capas.etiq ? NOMBRES : [], d => d).join(
      en => { const t = en.append("text").attr("class","etq"); t.append("tspan").attr("class","c"); t.append("tspan").attr("class","v num"); return t; })
    .attr("x", d => C[d][0]).attr("y", d => C[d][1]).attr("font-size", 10.5/k)
    .each(function(d){
      d3.select(this).select(".c").text(FT[d].properties.clave);
      d3.select(this).select(".v").attr("x", C[d][0]).attr("dy", 11/k).text(hay(val(d)) ? M().texto(val(d)) : "sin dato");
    });

  gEst.style("display", estado.capas.estaciones ? null : "none");
  gEst.selectAll("circle").classed("fuera-marca", d => !!estado.marca && d.marca !== estado.marca)
    .classed("en-sel", d => d.entidad === estado.sel || d.entidad === estado.cmp);
  gFocos.style("display", estado.capas.focos ? null : "none");
  gRet.style("display", estado.capas.ret ? null : "none");
  $("barrido").style.display = estado.capas.barrido ? "" : "none";
  $("cinta-caja").hidden = !estado.capas.cinta;
  app.classList.toggle("con-cinta", estado.capas.cinta);
}

/* ---------- retícula del cursor con lectura de coordenadas ---------- */
svg.on("pointermove", ev => {
  const [x,y] = d3.pointer(ev, svg.node()), w = cont.clientWidth, h = cont.clientHeight;
  miraV.attr("x1",x).attr("x2",x).attr("y1",0).attr("y2",h);
  miraH.attr("y1",y).attr("y2",y).attr("x1",0).attr("x2",w);
  miraC.attr("cx",x).attr("cy",y);
  const g = proy.invert(T.invert([x,y]));
  if(!g || g[0]<-120 || g[0]>-84 || g[1]<12 || g[1]>34){ $("hud-pos").innerHTML = "CURSOR <b>fuera del área</b>"; return; }
  const zona = Math.floor((g[0]+180)/6)+1;
  $("hud-pos").innerHTML = `LAT <b>${g[1].toFixed(4)}° N</b> · LON <b>${Math.abs(g[0]).toFixed(4)}° O</b> · UTM <b>${zona}N</b> (EPSG:326${zona})`;
});
svg.on("pointerleave", () => { miraV.attr("x1",-9).attr("x2",-9); miraH.attr("y1",-9).attr("y2",-9); miraC.attr("cx",-99); });
// Clic en el mapa: si se está eligiendo un punto, lo fija; si no, suelta el objetivo
svg.on("click", ev => { if(eligiendo(ev)) return; if(estado.sel) seleccionar(null); });

/* Modo "elegir en el mapa": el siguiente clic fija origen, destino, base o el centro de la geocerca */
function eligiendo(ev){
  if(!ui.elige) return false;
  const [x,y] = d3.pointer(ev, svg.node()), g = proy.invert(T.invert([x,y]));
  if(!g) return true;
  const punto = {lat:+g[1].toFixed(5), lon:+g[0].toFixed(5), rot:`Punto en el mapa (${g[1].toFixed(3)}, ${g[0].toFixed(3)})`};
  const tipo = ui.elige; ponerEleccion(null);
  if(tipo === "cerca") ponerCentro(punto, "mapa");
  else fijarPunto(tipo, punto);
  return true;
}
function ponerEleccion(tipo){
  ui.elige = tipo;
  app.classList.toggle("elige-punto", !!tipo);
  document.querySelectorAll("[data-elige]").forEach(b => b.setAttribute("aria-pressed", b.dataset.elige === tipo));
  $("cerca-mapa").setAttribute("aria-pressed", tipo === "cerca");
  aviso();
}

/* ================= 4. OBJETIVO FIJADO: LA SECUENCIA =================
   a) el país se atenúa y la cámara vuela      c) la entidad se levanta como holograma
   b) el marco se cierra y pasa el escaneo     d) el expediente se despliega por bloques */
const TIEMPOS = { vuelo:600, marco:160, escaneo:520, levantar:700, panel:820, fin:2000 };

function marco(n, margen){
  const [[x0,y0],[x1,y1]] = ruta.bounds(FT[n]), l = Math.min(18,(x1-x0)/3,(y1-y0)/3);
  const a=x0-margen, b=y0-margen, c=x1+margen, d=y1+margen;
  return `M${a},${b+l}V${b}H${a+l}M${c-l},${b}H${c}V${b+l}M${c},${d-l}V${d}H${c-l}M${a+l},${d}H${a}V${d-l}`;
}
function candado(animar){
  const poner = (g, n) => {
    g.interrupt();
    if(!n){ g.attr("d", null); return; }
    if(animar && !sinMovimiento){
      g.attr("opacity",0).transition().duration(480).ease(d3.easeCubicOut).attr("opacity",1)
       .attrTween("d", () => t => marco(n, 6 + 46*(1-t)));
    } else g.attr("opacity",1).attr("d", marco(n,6));
  };
  poner(gCand, estado.sel); poner(gCandB, estado.cmp);
  if(estado.sel){
    const [[x0,y0],[x1,y1]] = ruta.bounds(FT[estado.sel]);
    gAnillo.attr("cx",(x0+x1)/2).attr("cy",(y0+y1)/2).attr("r", Math.hypot(x1-x0,y1-y0)/2 + 10);
  } else gAnillo.attr("r",0);
}
function escanear(){
  const n = estado.cmp || estado.sel;
  if(!n || sinMovimiento) return;
  const [[x0,y0],[x1,y1]] = ruta.bounds(FT[n]), m = 6, alto = Math.max(8, (y1-y0)*.45);
  gBarre.interrupt().attr("x", x0-m).attr("width", x1-x0+2*m).attr("height", alto).attr("y", y0-m-alto).style("opacity",1)
    .transition().duration(380).ease(d3.easeQuadIn).attr("y", y1+m-alto)
    .transition().duration(140).style("opacity",0);
}

const holo = { t:0 };
function armarHolo(){
  const objetivos = [estado.sel && {n:estado.sel, c:"a"}, estado.cmp && {n:estado.cmp, c:"b"}].filter(Boolean);
  gHolo.selectAll("g.holo").data(objetivos, d => d.n).join(en => {
      const g = en.append("g");
      g.append("path").attr("class","holo-sombra");
      const cuerpo = g.append("g").attr("class","holo-cuerpo");
      cuerpo.append("path").attr("class","holo-relleno");
      cuerpo.append("g").attr("class","holo-trama").append("rect").attr("class","holo-lineas").attr("fill","url(#pat-lineas)");
      cuerpo.append("path").attr("class","holo-halo");
      cuerpo.append("path").attr("class","holo-borde");
      return g;
    })
    .attr("class", d => "holo " + d.c)
    .each(function(d){
      const g = d3.select(this), trazo = ruta(FT[d.n]), [[x0,y0],[x1,y1]] = ruta.bounds(FT[d.n]);
      g.selectAll("path").attr("d", trazo);
      d3.select(`#clip-holo-${d.c} path`).attr("d", trazo);
      g.select(".holo-trama").attr("clip-path", `url(#clip-holo-${d.c})`);
      g.select(".holo-lineas").attr("x", x0-2).attr("y", y0-10).attr("width", x1-x0+4).attr("height", y1-y0+20);
      g.select(".holo-relleno").attr("fill", estado.vista === "burb" ? "#1b3554" : color(d.n));
    });
  posarHolo();
}
function posarHolo(){
  const t = holo.t;
  gHolo.style("opacity", Math.min(1, t*4)).style("--paso", (4/k)+"px");
  gHolo.selectAll(".holo-cuerpo").attr("transform", `translate(${-5*t/k},${-10*t/k})`);
  gHolo.selectAll(".holo-sombra").attr("transform", `translate(${8*t/k},${13*t/k})`);
  d3.select("#pat-lineas").attr("patternTransform", `scale(${1/k})`);
}
function levantar(destino, dur){
  gHolo.interrupt("altura");
  if(sinMovimiento || !dur){ holo.t = destino; posarHolo(); return Promise.resolve(); }
  return gHolo.transition("altura").duration(dur).ease(d3.easeCubicOut)
    .tween("altura", () => { const i = d3.interpolateNumber(holo.t, destino); return t => { holo.t = i(t); posarHolo(); }; }).end().catch(() => {});
}

let relojes = [];
const luego = (ms, f) => relojes.push(setTimeout(f, sinMovimiento ? 0 : ms));
function cancelarSecuencia(){ relojes.forEach(clearTimeout); relojes = []; }

function secuencia(){
  cancelarSecuencia();
  const panel = $("panel"), estabaAbierto = panel.classList.contains("abierto");
  app.classList.toggle("hay-objetivo", !!estado.sel);
  enfocar();
  if(!estado.sel){
    candado(false); gBarre.interrupt().style("opacity",0);
    levantar(0, 220).then(() => { if(!estado.sel) armarHolo(); });
    pintarPanel();
    return;
  }
  holo.t = 0; armarHolo();
  gCand.interrupt().attr("d", null); gCandB.interrupt().attr("d", null);
  luego(TIEMPOS.marco, () => candado(true));
  luego(TIEMPOS.escaneo, escanear);
  luego(TIEMPOS.levantar, () => levantar(1, 420));
  if(sinMovimiento || estabaAbierto){
    panel.style.setProperty("--retraso", sinMovimiento ? "0ms" : (TIEMPOS.panel - 60) + "ms");
    pintarPanel();
  } else {
    panel.style.setProperty("--retraso", "120ms");
    luego(TIEMPOS.panel, () => pintarPanel());
  }
  luego(TIEMPOS.fin + 150, () => panel.style.setProperty("--retraso", "0ms"));
}

function seleccionar(n, comoSegunda, dePatrulla){
  if(!dePatrulla) pararPatrulla();
  if((comoSegunda || estado.eligeCmp) && n && estado.sel && n !== estado.sel){ estado.cmp = n; }
  else { estado.sel = (n === estado.sel && !estado.cmp) ? null : n; estado.cmp = null; }
  estado.eligeCmp = false;
  if(estado.sel){ ui.panel = null; estado.est = null; marcarEstacion(); }
  refrescar(); secuencia();
}

/* ================= 5. TOOLTIPS Y CIFRAS ANIMADAS ================= */
function miniSerie(n){
  const p = prodActual(), v = FECHAS.map((_,f) => precioEnt(E[n], p, f));
  if(FECHAS.length < 2) return "";
  const lo = d3.min(v.filter(hay)) ?? 0, mx = d3.max(v.filter(hay)) ?? 1, bw = 210/v.length, h = x => 6 + 22*(mx > lo ? (x-lo)/(mx-lo) : .5);
  return `<svg viewBox="0 0 210 34" aria-hidden="true">` + v.map((x,i) => !hay(x) ? "" :
    `<rect x="${i*bw+1}" y="${32-h(x)}" width="${Math.max(1,bw-2)}" height="${h(x)}" fill="${i===estado.f?"#62d3e8":"#2a4a66"}"/>`).join("") + `</svg>`;
}
function tip(ev, n){
  const e = E[n], f = estado.f, lugar = lugarDe(n, prodActual());
  mostrarTip(ev, `<strong>${n.toUpperCase()}</strong>
    <span class="num">${PRODUCTOS.map(p => `${NOM_PROD[p][0]} ${con(precioEnt(e,p,f), pesos)}`).join(" · ")}</span><br>
    <small class="num">${fmt(e.estaciones)} gasolineras${lugar ? ` · ${prodActual()} lugar ${lugar} (1 = más barata)` : ""}</small><br>
    <small>Marca con más estaciones: ${con(e.marca_lider, x => x)}${hay(tomas(e)) ? ` · tomas ${huach.anio}: ${fmt(tomas(e))} (ref.)` : ""}</small>
    ${miniSerie(n)}`);
}
function tipEst(ev, d){
  mostrarTip(ev, `<strong>${esc(d.nombre)}</strong><span class="punto-marca" style="background:${colorMarca(d.marca)}"></span>${esc(d.marca)} · ${esc(d.entidad ?? "")}<br>
    <span class="num">${PRODUCTOS.map(p => `${NOM_PROD[p][0]} ${con(d.precios[p], pesos)}`).join(" · ")}</span><br>
    <small>${esc(d.permiso)}${d.horario ? " · " + esc(d.horario) : ""}</small>`);
}
function tipFoco(ev, m){
  mostrarTip(ev, `<strong>${m.municipio.toUpperCase()}</strong>${m.entidad}<br>
    <span class="num">${fmt(m.tomas)} tomas clandestinas reportadas · ${m.anio} ${m.periodo}</span><br>
    <small>${esc(m.fuente)} · solo referencia agregada; el punto es la cabecera municipal</small>`);
}
function mostrarTip(ev, html){
  const t = $("tip"), [x,y] = d3.pointer(ev, cont), z = zonaLibre();
  t.innerHTML = html; t.style.display = "block";
  t.style.left = Math.max(0, Math.min(x, z.x1-250))+"px";
  t.style.top = Math.max(0, Math.min(y, z.y1-150))+"px";
}
function ocultarTip(){ $("tip").style.display = "none"; }

const previo = new Map();
function cifra(id, v, dec=0, suf="", pre=""){
  if(!hay(v)) return SIN;
  return `<span data-id="${id}" data-v="${v}" data-d="${dec}" data-s="${suf}" data-p="${pre}">${pre}${num(v,dec)}${suf}</span>`;
}
function num(v, dec){ return Number(v).toLocaleString("es-MX", {minimumFractionDigits:dec, maximumFractionDigits:dec}); }
function animarCifras(){
  document.querySelectorAll("[data-id]").forEach(el => {
    const id = el.dataset.id, a = +el.dataset.v, dec = +el.dataset.d, suf = el.dataset.s, pre = el.dataset.p ?? "", de = previo.get(id) ?? 0;
    previo.set(id, a);
    if(sinMovimiento || de === a) return;
    const it = d3.interpolateNumber(de, a), t0 = performance.now();
    (function paso(t){ const u = Math.min(1,(t-t0)/650), s = 1-Math.pow(1-u,3);
      el.textContent = pre + num(it(s), dec) + suf; if(u<1) requestAnimationFrame(paso); })(t0);
  });
}

/* ================= 6. PIEZAS DE LOS EXPEDIENTES ================= */
/* Barras: `etiquetas` debajo, `valores` (y opcionalmente `valoresB`) arriba. `sel` es la barra resaltada; `base` el piso del eje. */
function barras(valores, etiquetas, sel, valoresB, txt = v => fmt2(v), base = null){
  const W=300, H=96, todos = (valoresB ? valores.concat(valoresB) : valores).filter(hay), mx = d3.max(todos) || 1;
  const lo = base ?? 0, bw = W/valores.length, alto = v => Math.max(2,(H-34)*(v-lo)/Math.max(1e-9, mx-lo));
  const cada = Math.ceil(valores.length / 8);
  let s = `<svg class="serie" viewBox="0 0 ${W} ${H}" role="img" aria-label="Serie"><line x1="0" x2="${W}" y1="${H-16.5}" y2="${H-16.5}" stroke="#1c2a3b"/>`;
  valores.forEach((v,i) => {
    const on = i === sel, x = i*bw+Math.min(6, bw*.15), an = valoresB ? (bw-Math.min(14,bw*.3))/2 : bw-Math.min(12, bw*.3), h = hay(v) ? alto(v) : 0;
    if(hay(v)) s += `<rect x="${x}" y="${H-17-h}" width="${an}" height="${h}" fill="${on?"#62d3e8":(valoresB?"#2f7f93":"#24405a")}" style="animation-delay:${i*45}ms"/>`;
    if(valoresB){ const vb = valoresB[i], hb = hay(vb) ? alto(vb) : 0;
      if(hay(vb)) s += `<rect x="${x+an+2}" y="${H-17-hb}" width="${an}" height="${hb}" fill="${on?"#ffb224":"#8a6420"}" style="animation-delay:${i*45+20}ms"/>`; }
    else if(valores.length <= 8) s += `<text x="${x+an/2}" y="${H-21-h}" text-anchor="middle" ${on?'style="fill:#d9e4ef"':""}>${hay(v) ? txt(v) : "s/d"}</text>`;
    if(i % cada === 0 || on) s += `<text x="${i*bw+bw/2}" y="${H-4}" text-anchor="middle" ${on?'style="fill:#62d3e8"':""}>${etiquetas[i]}</text>`;
  });
  return s + "</svg>";
}
function reloj(pct, ref, col, rotulo){
  if(!hay(pct)) return `<div class="reloj"><svg viewBox="0 0 120 76" role="img" aria-label="${rotulo}: sin dato">
    <path class="pista" d="M14 62A46 46 0 0 1 106 62"/><text x="60" y="60" style="font-size:13px">sin dato</text></svg><div class="nota">${rotulo}</div></div>`;
  const p = Math.min(100, pct);
  let marca = "";
  if(hay(ref)){ const ang = Math.PI*(1-ref/100);
    marca = `<line class="ref" x1="${60+46*Math.cos(ang)}" y1="${62-46*Math.sin(ang)}" x2="${60+56*Math.cos(ang)}" y2="${62-56*Math.sin(ang)}"/>`; }
  return `<div class="reloj"><svg viewBox="0 0 120 76" role="img" aria-label="${rotulo}: ${fmt1(pct)} por ciento">
    <path class="pista" d="M14 62A46 46 0 0 1 106 62" />
    <path class="arco" data-p="${p}" d="M14 62A46 46 0 0 1 106 62" pathLength="100" stroke="${col}" stroke-dasharray="0 100"/>
    ${marca}<text x="60" y="60">${fmt1(pct)} %</text></svg><div class="nota">${rotulo}</div></div>`;
}
function animarRelojes(){
  requestAnimationFrame(() => requestAnimationFrame(() =>
    document.querySelectorAll(".seccion:not([hidden]) .reloj .arco").forEach(a => a.setAttribute("stroke-dasharray", `${a.dataset.p} 100`))));
}
function secciones(grupo, defs){
  const abierta = defs.some(d => d.k === ui.secc[grupo]) ? ui.secc[grupo] : defs[0].k;
  return `<div class="pestanas" role="group" aria-label="Secciones" data-grupo="${grupo}">` +
    defs.map(d => `<button type="button" class="pest" data-k="${d.k}" aria-expanded="${d.k===abierta}" aria-controls="s-${grupo}-${d.k}">${d.rot}</button>`).join("") + `</div>` +
    defs.map(d => `<div class="seccion" id="s-${grupo}-${d.k}" data-grupo="${grupo}" ${d.k===abierta ? "" : "hidden"}>${d.html}</div>`).join("");
}
function abrirSeccion(grupo, clave){
  ui.secc[grupo] = clave;
  document.querySelectorAll(`.pestanas[data-grupo="${grupo}"] .pest`).forEach(b => b.setAttribute("aria-expanded", b.dataset.k === clave));
  document.querySelectorAll(`.seccion[data-grupo="${grupo}"]`).forEach(s => s.hidden = s.id !== `s-${grupo}-${clave}`);
  animarRelojes();
}
$("panel").addEventListener("click", ev => {
  const q = ev.target.closest("[data-quitar]");
  if(q){ ev.stopPropagation(); quitarPedido(q.dataset.quitar); return; }
  const b = ev.target.closest(".pest");
  if(b) abrirSeccion(b.parentElement.dataset.grupo, b.dataset.k);
  const e = ev.target.closest("[data-permiso]");
  if(e){ const d = POR_PERMISO.get(e.dataset.permiso); if(d) verEstacion(d, true); }
});
// Pequeño holograma con un valor: una pieza de la composición
function pod(rotulo, valorHtml, claves, col, frac){
  return `<div class="pod" style="--c:${col}"><div class="pod-holo">${claves.map(c => Siluetas.plana(c)).join("")}</div>
    <b class="num">${valorHtml}</b><span class="nota">${rotulo}</span>
    <i class="pod-barra"><u style="transform:scaleX(${hay(frac) ? Math.max(0, Math.min(1, frac)) : 0})"></u></i></div>`;
}
const filaEst = (d, i, p) => `<li><button type="button" class="fila-est" data-permiso="${esc(d.permiso)}"><i class="num">${String(i+1).padStart(2,"0")}</i>
  <span><span class="punto-marca" style="background:${colorMarca(d.marca)}"></span>${esc(d.nombre)}<small>${esc(d.marca)}${d.extra ? " · " + d.extra : ""}</small></span>
  <span class="precio num">${con(d.precio ?? d.precios?.[p], pesos)}</span></button></li>`;

/* ---------- expediente de una entidad ---------- */
function entEsencial(n, f){
  const e = E[n], p = prodActual(), v = precioEnt(e, p, f), lugar = lugarDe(n, p);
  const varia = f > 0 ? variacion(v, precioEnt(e, p, f-1)) : null;
  return `<div class="gran num">${cifra("g-ent", v, 2, "", "$")}</div>
    <div class="esencial"><span>${NOM_PROD[p].toLowerCase()} promedio · <b>${fechaCorta(FECHAS[f])}</b></span>
      <span>${lugar ? `lugar <b class="num">${lugar}</b> de ${NOMBRES.length} (1 = más barata)` : `lugar ${SIN}`}</span>
      ${txtVariacion(varia, f)}</div>`;
}
function entPrecios(n, f){
  const e = E[n], p = prodActual(), r = e.precio[p], nac = NAC.precio[p];
  const serieE = FECHAS.map((_,i) => precioEnt(e,p,i));
  const grafica = FECHAS.length > 1
    ? barras(serieE, FECHAS.map(fechaCorta), f, null, fmt2, (d3.min(serieE.filter(hay)) ?? 0) * .98)
    : barras(PRODUCTOS.map(q => e.precio[q]?.prom), PRODUCTOS.map(q => NOM_PROD[q]), PRODUCTOS.indexOf(p), PRODUCTOS.map(q => NAC.precio[q]?.prom), fmt2, 18) +
      `<p class="nota">Azul: ${n}. Ámbar: promedio nacional. Hace falta más de un día de histórico para ver la tendencia.</p>`;
  return `${grafica}
    <div class="fila"><span>Más barata / más cara</span><span class="num">${r ? `${pesos(r.min)} / ${pesos(r.max)}` : SIN}</span></div>
    <div class="fila"><span>Mediana · estaciones con precio</span><span class="num">${r ? `${pesos(r.mediana)} · ${fmt(r.n)}` : SIN}</span></div>
    <div class="fila"><span>Diferencia vs nacional</span><span class="num">${r && nac ? `${r.prom - nac.prom >= 0 ? "+" : "−"}${pesos(Math.abs(r.prom - nac.prom))} por litro` : SIN}</span></div>`;
}
function htmlEntidad(n, f){
  const e = E[n], p = prodActual(), top = e.marcas.slice(0,3);
  const pctDiesel = e.estaciones ? (e.precio.diesel?.n ?? 0) / e.estaciones * 100 : null;
  const nacDiesel = NAC.estaciones ? (NAC.precio.diesel?.n ?? 0) / NAC.estaciones * 100 : null;
  const perfil = `
    <div class="relojes">${reloj(e.pct_pemex, NAC.pct_pemex, "#2fbf71", "Estaciones Pemex")}
      ${reloj(pctDiesel, nacDiesel, "#62d3e8", "Venden diésel")}</div>
    <div class="fila"><span>Gasolineras</span><span class="num">${fmt(e.estaciones)}</span></div>
    <div class="fila"><span>Marcas presentes</span><span class="num">${fmt(e.marcas.length)}</span></div>
    <p class="nota">Marca blanca: valor nacional (${con(NAC.pct_pemex, fmt1)} % Pemex · ${con(nacDiesel, fmt1)} % con diésel).</p>`;
  const marcas = `
    ${Siluetas.vitrina("bomba")}
    <div class="veh-ficha"><div class="eti">Marca con más estaciones</div>
      <div class="veh">${con(e.marca_lider, x => x)}</div>
      <div class="fila"><span>Estaciones de esa marca</span><span class="num">${e.marcas[0] ? `${fmt(e.marcas[0].n)} de ${fmt(e.estaciones)}` : SIN}</span></div>
      <p class="nota">Marca según la etiqueta brand de OpenStreetMap o el nombre registrado ante la CNE. Silueta genérica.</p></div>
    <div><div class="eti">Las tres marcas principales</div>
      <div class="trio">${top.length ? top.map(m => pod(esc(m.marca), fmt1(m.n/e.estaciones*100)+" %", ["bomba"], colorMarca(m.marca), m.n/e.estaciones)).join("") : `<p class="nota">${SIN}</p>`}</div></div>`;
  const baratas = (e.baratas[p] ?? []);
  const lista = baratas.length
    ? `<p class="nota">Las ${baratas.length} con ${NOM_PROD[p].toLowerCase()} más barata en el último corte. Clic para ver la ficha.</p><ol class="lista-est">${baratas.map((d,i) => filaEst(d, i, p)).join("")}</ol>`
    : `<p class="nota">${SIN}: ninguna estación de ${n} reporta ${NOM_PROD[p].toLowerCase()}.</p>`;
  const hq = e.huachicol ?? {}, munis = DATOS.municipios.filter(m => m.entidad === n), fte = Object.values(hq)[0];
  const tomasHtml = `
    <p class="nota">Solo referencia agregada. Periodos distintos no se suman. No hay ubicación de tomas ni ductos.</p>
    ${["petroliferos","gas_lp"].map(k => { const h = hq[k];
      return `<div class="fila"><span>${k === "gas_lp" ? "Gas LP" : "Petrolíferos"} · ${h ? h.anio + " " + h.periodo : "último año"}</span><span class="num">${h ? fmt(h.tomas) + " tomas" : SIN}</span></div>`; }).join("")}
    ${fte ? `<p class="nota">Fuente: <a href="${esc(fte.url)}" target="_blank" rel="noopener">${esc(fte.fuente)}</a></p>` : ""}
    ${munis.length ? `<div class="eti">Municipios foco</div>` + munis.map(m => `<div class="fila"><span>${m.municipio}</span><span class="num">${fmt(m.tomas)} · ${m.anio} ${m.periodo}</span></div>`).join("") : ""}`;
  return `
    <div class="exp-cab"><div class="eti">Objetivo fijado</div>
      <div class="cab"><h3>${n.toUpperCase()}</h3><button type="button" class="mini" id="b-cmp">Comparar</button></div>
      <div id="ent-esencial">${entEsencial(n,f)}</div></div>
    ${secciones("ent", [
      {k:"precios", rot:"Precios", html:`<div id="ent-precios">${entPrecios(n,f)}</div>`},
      {k:"perfil", rot:"Perfil", html:perfil},
      {k:"marcas", rot:"Marcas", html:marcas},
      {k:"baratas", rot:"Baratas", html:lista},
      {k:"tomas", rot:"Tomas", html:tomasHtml}])}`;
}

/* ---------- comparación de dos entidades ---------- */
function filaVs(rot, va, vb, f){
  const mx = Math.max(hay(va) ? va : 0, hay(vb) ? vb : 0) || 1;
  return `<span class="a num">${con(va, f)}</span><span class="m">${rot}</span><span class="b num">${con(vb, f)}</span>
    <span class="ba"><i style="width:${hay(va) ? va/mx*100 : 0}%"></i></span><span></span><span class="bb"><i style="width:${hay(vb) ? vb/mx*100 : 0}%"></i></span>`;
}
function cmpPrecios(A, B, f){
  const ea = E[A], eb = E[B];
  return `${barras(PRODUCTOS.map(p => precioEnt(ea,p,f)), PRODUCTOS.map(p => NOM_PROD[p]), PRODUCTOS.indexOf(prodActual()), PRODUCTOS.map(p => precioEnt(eb,p,f)), fmt2, 18)}
    <div class="vs">${PRODUCTOS.map(p => filaVs(NOM_PROD[p], precioEnt(ea,p,f), precioEnt(eb,p,f), pesos)).join("")}
      ${filaVs(`Lugar ${NOM_PROD[prodActual()].toLowerCase()}`, lugarDe(A, prodActual()), lugarDe(B, prodActual()), v => v+"°")}</div>
    <p class="nota">Corte ${fechaTxt(FECHAS[f])}. En «Lugar», 1 = la entidad más barata.</p>`;
}
function htmlComparacion(A, B, f){
  const ea = E[A], eb = E[B];
  const ficha = (e, col) => `<div class="pod" style="--c:${col}"><div class="pod-holo">${Siluetas.plana("bomba")}</div>
      <div class="veh">${con(e.marca_lider, x => x)}</div><span class="nota">marca con más estaciones</span></div>`;
  return `
    <div class="exp-cab"><div class="eti" id="cmp-eti">Comparación · ${fechaCorta(FECHAS[f])}</div>
      <h3><span style="color:var(--hielo)">${A.toUpperCase()}</span><br><span style="color:var(--ambar)">${B.toUpperCase()}</span></h3></div>
    ${secciones("cmp", [
      {k:"precios", rot:"Precios", html:`<div id="cmp-precios">${cmpPrecios(A,B,f)}</div>`},
      {k:"perfil", rot:"Perfil", html:`<div class="vs">${filaVs("Gasolineras", ea.estaciones, eb.estaciones, fmt)}
        ${filaVs("% Pemex", ea.pct_pemex, eb.pct_pemex, v => fmt1(v)+" %")}
        ${filaVs("Marcas", ea.marcas.length, eb.marcas.length, fmt)}
        ${filaVs(`Tomas ${huach ? huach.anio : ""} (ref.)`, tomas(ea), tomas(eb), fmt)}</div>`},
      {k:"marcas", rot:"Marcas", html:`<div class="duo">${ficha(ea,"var(--hielo)")}${ficha(eb,"var(--ambar)")}</div>
        <p class="nota">Siluetas genéricas; la marca solo aparece como texto.</p>`}])}`;
}

let expClave = null;
function expediente(){
  const el = $("exp"), f = estado.f;
  if(!estado.sel){ expClave = null; return; }
  const clave = estado.sel + "|" + (estado.cmp ?? "") + "|" + prodActual();
  if(clave !== expClave){
    expClave = clave; el.classList.remove("quieto");
    el.innerHTML = estado.cmp ? htmlComparacion(estado.sel, estado.cmp, f) : htmlEntidad(estado.sel, f);
    const b = $("b-cmp"); if(b) b.onclick = () => { estado.eligeCmp = !estado.eligeCmp; aviso(); };
  } else {
    el.classList.add("quieto");
    if(estado.cmp){ $("cmp-eti").textContent = `Comparación · ${fechaCorta(FECHAS[f])}`; $("cmp-precios").innerHTML = cmpPrecios(estado.sel, estado.cmp, f); }
    else { $("ent-esencial").innerHTML = entEsencial(estado.sel, f); $("ent-precios").innerHTML = entPrecios(estado.sel, f); }
  }
  animarRelojes();
}

/* ---------- panorama nacional (se abre con la cifra nacional) ---------- */
const precioNac = (p, f) => hay(NAC.serie[p]?.[f]) ? NAC.serie[p][f] : (f === ULT ? NAC.precio[p]?.prom : null);
function nacEsencial(f){
  const p = prodActual(), v = precioNac(p, f);
  return `<div class="gran num">${cifra("g-nac", v, 2, "", "$")}</div>
    <div class="esencial"><span>${NOM_PROD[p].toLowerCase()} · promedio nacional · <b>${fechaCorta(FECHAS[f])}</b></span>
    ${f > 0 ? txtVariacion(variacion(v, precioNac(p, f-1)), f) : ""}</div>`;
}
function nacPrecios(f){
  const serieN = FECHAS.map((_,i) => precioNac(prodActual(), i));
  return `<div class="kpis">${PRODUCTOS.map(p => `<div class="kpi"><span class="eti">${NOM_PROD[p]}</span><b class="num">${cifra("k-"+p, precioNac(p,f), 2, "", "$")}</b>
      <small class="num">${NAC.precio[p] ? `${pesos(NAC.precio[p].min)} – ${pesos(NAC.precio[p].max)}` : SIN}</small></div>`).join("")}
      <div class="kpi"><span class="eti">Gasolineras</span><b class="num">${cifra("k-est", NAC.estaciones)}</b><small>${DATOS.demo ? "sintéticas" : "con permiso CNE"}</small></div></div>
    ${FECHAS.length > 1 ? barras(serieN, FECHAS.map(fechaCorta), f, null, fmt2, (d3.min(serieN.filter(hay)) ?? 0)*.98) : ""}`;
}
let nacHecho = false;
function nacional(){
  const el = $("nac"), f = estado.f;
  if(!nacHecho){
    nacHecho = true;
    const hq = NAC.huachicol ?? {};
    el.innerHTML = `
      <div class="exp-cab"><div class="eti">Sin objetivo fijado</div><h3>REPÚBLICA MEXICANA</h3><div id="nac-esencial"></div></div>
      ${secciones("nac", [
        {k:"precios", rot:"Precios", html:`<div id="nac-precios"></div>`},
        {k:"marcas", rot:"Marcas", html:`<div class="eti">Gasolineras por marca</div><div class="tipos">` +
          NAC.marcas.slice(0,10).map(m => `<div class="fila" style="--c:${colorMarca(m.marca)}"><span>${Siluetas.plana("bomba")}${esc(m.marca)}</span>
            <span class="num">${fmt(m.n)} · ${fmt1(m.n/NAC.estaciones*100)} %</span></div>`).join("") + `</div>`},
        {k:"tomas", rot:"Tomas", html:`<p class="nota">Tomas clandestinas reportadas en ductos de Pemex. Solo referencia agregada; no es un total nacional, es la suma de los estados con dato.</p>` +
          ["petroliferos","gas_lp"].map(k => hq[k] ? `<div class="fila"><span>${k === "gas_lp" ? "Gas LP" : "Petrolíferos"} · ${hq[k].anio} ${hq[k].periodo}</span>
            <span class="num">${fmt(hq[k].suma_reportada)} en ${hq[k].estados_con_dato} estados</span></div>` : "").join("") +
          `<p class="nota">Fuentes: ${esc([...new Set(Object.values(hq).flatMap(h => h.fuentes))].join("; ")) || "sin dato"}.</p>`}])}`;
  }
  el.classList.toggle("quieto", el.dataset.f !== undefined);
  el.dataset.f = f;
  $("nac-esencial").innerHTML = nacEsencial(f);
  $("nac-precios").innerHTML = nacPrecios(f);
}
function cifraNacional(){
  const p = prodActual();
  $("cifra-eti").textContent = `${NOM_PROD[p]} · promedio nacional · ${fechaCorta(FECHAS[estado.f])}`;
  $("cifra-val").innerHTML = cifra("k-nac", precioNac(p, estado.f), 2, "", "$");
}

/* ---------- ficha de una gasolinera ---------- */
function htmlEstacion(d){
  const ent = E[d.entidad];
  const pods = PRODUCTOS.map(p => { const v = d.precios[p], r = ent?.precio[p], dif = hay(v) && r ? v - r.prom : null;
    return pod(`${NOM_PROD[p]}${dif === null ? "" : `<br>${dif >= 0 ? "+" : "−"}${fmt2(Math.abs(dif))} vs estatal`}`,
      con(v, pesos), ["bomba"], p === "diesel" ? "var(--ambar)" : (p === "premium" ? "var(--rojo)" : "var(--hielo)"),
      hay(v) && r ? 1 - (v - r.min) / Math.max(0.01, r.max - r.min) : null); }).join("");
  return `
    <div class="exp-cab"><div class="eti">Gasolinera</div>
      <div class="cab"><h3>${esc(d.nombre).toUpperCase()}</h3></div>
      <div class="esencial"><span><span class="punto-marca" style="background:${colorMarca(d.marca)}"></span><b>${esc(d.marca)}</b></span><span>${esc(d.entidad ?? "fuera de los límites")}</span></div></div>
    <div class="trio">${pods}</div>
    <p class="nota">La barra se llena más mientras más barata es dentro de su entidad.</p>
    <div>
      <div class="fila"><span>Permiso CNE</span><span class="num">${esc(d.permiso)}</span></div>
      <div class="fila"><span>Horario</span><span>${con(d.horario, esc)}</span></div>
      <div class="fila"><span>Coordenadas</span><span class="num">${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}</span></div>
    </div>
    <div class="seg dos"><button type="button" id="est-ir">➜ Cómo llegar</button><button type="button" id="est-surtir">＋ Agregar al surtido</button></div>
    ${DATOS.demo ? `<p class="nota">Estación SINTÉTICA de demostración.</p>` : ""}`;
}
function verEstacion(d, volando){
  estado.est = d;
  $("est").innerHTML = htmlEstacion(d);
  $("est-ir").onclick = () => comoLlegar(d);
  $("est-surtir").onclick = () => { agregarPedido(d); ui.panel = null; abrirPanel("ruta"); ponerModo("surtido"); };
  ui.panel = "estacion"; $("panel").style.setProperty("--retraso","0ms");
  pintarPanel(); marcarEstacion();
  if(volando) volarA([[d.lon, d.lat]], 40, 0.03);
}
function marcarEstacion(){
  const d = estado.est;
  gEstSel.attr("cx", d ? d.p[0] : 0).attr("cy", d ? d.p[1] : 0).attr("r", d ? 9/k : 0);
}
function clicEstacion(d){
  if(vistaActual() === "ruta" && ui.modo === "surtido"){ agregarPedido(d); return; }
  verEstacion(d, false);
}

/* ================= 7. HERRAMIENTAS ================= */
/* ---------- ranking ---------- */
function ranking(){
  const m = M(), filas = ordenados().map(n => ({n, v:val(n)}));
  const vs = filas.map(r => r.v).filter(hay), lo = d3.min(vs) ?? 0, hi = d3.max(vs) ?? 1;
  const largo = v => m.asc ? (hi > lo ? .15 + .85*(v-lo)/(hi-lo) : 1) : (hi ? v/hi : 0);
  $("rank-nota").textContent = (m.asc ? "De la más barata a la más cara. " : "") + "Clic fija la entidad · Mayús + clic la compara con la fijada.";
  const ol = d3.select("#rank"), antes = new Map();
  ol.selectAll("li").each(function(d){ antes.set(d.n, this.offsetTop); });
  const li = ol.selectAll("li").data(filas, d => d.n)
    .join(en => { const l = en.append("li"); l.append("button").attr("type","button"); return l; }).order();
  li.select("button")
    .attr("aria-current", d => d.n === estado.sel ? "true" : null)
    .classed("cmp", d => d.n === estado.cmp)
    .html((d,i) => `<i class="num">${String(i+1).padStart(2,"0")}</i><span>${d.n}</span><span class="num">${con(d.v, m.texto)}</span>
      <u style="width:calc(100% - 38px);transform:scaleX(${hay(d.v) ? Math.max(0, Math.min(1,largo(d.v))) : 0});background:${hay(d.v) ? m.rampa(m.escala(d.v)) : SIN_COLOR}"></u>`)
    .on("click", (ev,d) => seleccionar(d.n, ev.shiftKey));
  if(!sinMovimiento && vistaActual() === "ranking") li.each(function(d){
    const dy = (antes.get(d.n) ?? this.offsetTop) - this.offsetTop;
    if(dy) this.animate([{transform:`translateY(${dy}px)`},{transform:"none"}], {duration:480, easing:"cubic-bezier(.2,.8,.2,1)"});
  });
}

/* ---------- marcas: al elegir una se resaltan sus estaciones y las entidades donde domina ---------- */
function modelos(){
  const tope = d3.max(DATOS.marcas, s => s.estaciones) || 1;
  $("modelos").innerHTML = DATOS.marcas.map((s,i) => `
    <button type="button" class="mod" data-s="${esc(s.marca)}" aria-pressed="${estado.marca===s.marca}">
      <i class="num">${String(i+1).padStart(2,"0")}</i>${Siluetas.plana("bomba")}
      <span><span class="punto-marca" style="background:${colorMarca(s.marca)}"></span>${esc(s.marca)} <small>${PRODUCTOS.map(p => `${NOM_PROD[p][0]} ${con(s.precio[p], pesos)}`).join(" · ")}</small></span>
      <span class="num">${fmt(s.estaciones)}</span><u style="transform:scaleX(${s.estaciones/tope});animation-delay:${i*40}ms;background:${colorMarca(s.marca)}"></u></button>`).join("");
  document.querySelectorAll(".mod").forEach(b => b.onclick = () => ponerMarca(estado.marca === b.dataset.s ? null : b.dataset.s));
  ponerMarca(estado.marca);
}
function ponerMarca(s){
  estado.marca = s;
  document.querySelectorAll(".mod").forEach(x => x.setAttribute("aria-pressed", x.dataset.s === s));
  const info = DATOS.marcas.find(m => m.marca === s), n = info ? info.lider_en : [];
  $("marca-msj").textContent = !s ? `${DATOS.marcas.length} marcas, ${fmt(NAC.estaciones)} gasolineras. Elige una para ver sus estaciones y las entidades donde tiene más.`
    : `${s}: ${fmt(info.estaciones)} gasolineras; es la marca con más estaciones en ${n.length} ${n.length===1?"entidad":"entidades"}${n.length ? ` (${n.join(", ")})` : ""}.`;
  const chip = $("chip-marca");
  chip.hidden = !s;
  if(s){ chip.textContent = `◇ ${s} · ${fmt(info.estaciones)} gasolineras ✕`; chip.setAttribute("aria-label", `Quitar el filtro de ${s}`); }
  pintar();
}
$("chip-marca").onclick = () => ponerMarca(null);

/* ---------- cinta de datos ---------- */
function cinta(){
  const p = prodActual();
  const baratas = NOMBRES.flatMap(n => (E[n].baratas[p] ?? []).slice(0,1).map(d => ({...d, entidad:n}))).sort((a,b) => a.precio - b.precio).slice(0,12);
  const t = baratas.map(d => `<b>${esc(d.nombre).toUpperCase()}</b> ${esc(d.entidad)} · ${NOM_PROD[p].toLowerCase()} ${pesos(d.precio)}`)
    .concat(DATOS.municipios.map(m => `<b>${m.municipio.toUpperCase()}</b> <em>${fmt(m.tomas)} tomas ${m.anio} ${m.periodo} (ref.)</em>`)).join("  ◆  ") + "  ◆  ";
  $("cinta").innerHTML = t + t;
}

/* ---------- leyenda y aviso ---------- */
function leyenda(){
  const m = M();
  $("ley-tit").textContent = m.titulo + (m.serie ? " · " + fechaCorta(FECHAS[estado.f]) : "");
  $("ley-rampa").style.background = `linear-gradient(90deg,${d3.range(0,1.01,.1).map(t => m.rampa(t)).join(",")})`;
  $("ley-min").textContent = m.min; $("ley-max").textContent = m.max;
  $("ley-focos").innerHTML = `<span class="rojo">◉</span> ${DATOS.municipios.length} municipios con tomas reportadas (ref.)`;
  $("ley-focos").hidden = !estado.capas.focos || !DATOS.municipios.length;
}
function aviso(){
  const a = $("aviso");
  const textos = { origen:"Clic en el mapa para fijar el ORIGEN · Esc cancela", destino:"Clic en el mapa para fijar el DESTINO · Esc cancela",
    base:"Clic en el mapa para fijar la BASE de la pipa · Esc cancela",
    "f-origen":"Clic en el mapa para fijar de dónde SALE la unidad · Esc cancela", "f-destino":"Clic en el mapa para fijar a dónde VA la unidad · Esc cancela", cerca:"Clic en el mapa para centrar la geocerca · Esc cancela" };
  if(ui.elige){ a.hidden = false; a.textContent = textos[ui.elige]; }
  else if(estado.eligeCmp){ a.hidden = false; a.textContent = "Elige la segunda entidad · Esc cancela"; }
  else if(patrulla.id){ a.hidden = false; a.textContent = `Patrulla · ${patrulla.i+1} de ${patrulla.ruta.length} · P detiene`; }
  else a.hidden = true;
}

/* ---------- buscador: entidades, marcas, gasolineras y municipios foco ---------- */
const sinAcento = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase().trim();
EST.forEach(e => e.q = sinAcento(`${e.nombre} ${e.marca} ${e.entidad ?? ""} ${e.permiso}`));
function coincidencias(q){
  if(!q) return [];
  const ent = NOMBRES.filter(n => sinAcento(n).includes(q)).map(n => ({destino:n, rot:n, det:`entidad · ${fmt(E[n].estaciones)} gasolineras`, peso:sinAcento(n).startsWith(q) ? 0 : 1}));
  const mar = DATOS.marcas.filter(m => sinAcento(m.marca).includes(q)).map(m => ({marca:m.marca, rot:m.marca, det:`marca · ${fmt(m.estaciones)} gasolineras`, peso:0}));
  const mun = DATOS.municipios.filter(m => sinAcento(m.municipio+", "+m.entidad).includes(q))
    .map(m => ({destino:m.entidad, rot:m.municipio, det:`${m.entidad} · ${fmt(m.tomas)} tomas ${m.anio} (ref.)`, mun:true, peso:1}));
  const est = EST.filter(e => e.q.includes(q)).slice(0, 8).map(e => ({est:e, rot:e.nombre, det:`${e.marca} · ${e.entidad ?? ""} · ${hay(e.precios[prodActual()]) ? pesos(e.precios[prodActual()]) : "sin precio"}`, peso:2}));
  return ent.concat(mar, mun, est).sort((a,b) => a.peso - b.peso).slice(0, 14);
}
function listarBusqueda(){
  const q = sinAcento($("buscar").value), r = coincidencias(q);
  $("buscar-msj").textContent = q && !r.length ? `Sin coincidencia en entidades, marcas, gasolineras ni municipios foco.` : "";
  $("buscar-res").innerHTML = r.map((x,i) => `<li><button type="button" data-i="${i}" class="${i===0?"primero":""}"><span>${esc(x.rot)}</span><small>${esc(x.det)}</small></button></li>`).join("");
  $("buscar-res").querySelectorAll("button").forEach(b => b.onclick = () => irA(r[+b.dataset.i]));
  return r;
}
function irA(x){
  if(!x) return;
  if(x.est){ verEstacion(x.est, true); return; }
  if(x.marca){ ui.panel = null; abrirPanel("marcas"); ponerMarca(x.marca); return; }
  if(x.mun) ui.secc.ent = "tomas";
  estado.sel = null; estado.cmp = null; seleccionar(x.destino);
}
$("buscar").addEventListener("input", listarBusqueda);
$("buscar").addEventListener("keydown", ev => { if(ev.key === "Enter") irA(listarBusqueda()[0]); });

/* ---------- patrulla automática: recorre las primeras del ranking vigente ---------- */
const patrulla = { id:null, i:0, n:8, ruta:[] };
function pintarPatrulla(){
  const enMarcha = !!patrulla.id, lista = enMarcha ? patrulla.ruta : ordenados().filter(n => hay(val(n))).slice(0, patrulla.n);
  $("patrulla-txt").textContent = `Recorre sola las ${lista.length} primeras entidades del ranking vigente y fija cada una durante unos segundos.`;
  $("patrulla").setAttribute("aria-pressed", enMarcha);
  $("patrulla-rot").textContent = enMarcha ? "❚❚ Detener patrulla" : "▶ Iniciar patrulla";
  $("h-patrulla").classList.toggle("activa", enMarcha);
  $("patrulla-ruta").innerHTML = lista.map((n,i) => `<li class="${enMarcha && i===patrulla.i ? "va" : ""}"><span class="num">${String(i+1).padStart(2,"0")}</span><span>${n}</span><span class="num">${con(val(n), M().texto)}</span></li>`).join("");
}
function pararPatrulla(){ if(!patrulla.id) return; clearInterval(patrulla.id); patrulla.id = null; pintarPatrulla(); }
function alternarPatrulla(){
  if(patrulla.id){ pararPatrulla(); aviso(); return; }
  patrulla.ruta = ordenados().filter(n => hay(val(n))).slice(0, patrulla.n); patrulla.i = 0;
  if(!patrulla.ruta.length) return;
  const paso = () => { estado.sel = null; estado.cmp = null; seleccionar(patrulla.ruta[patrulla.i], false, true); };
  patrulla.id = setInterval(() => { patrulla.i = (patrulla.i+1) % patrulla.ruta.length; paso(); }, 4500);
  paso();
}
$("patrulla").onclick = alternarPatrulla;

/* ---------- cerca de mí: geocerca circular y gasolineras ordenadas ---------- */
const cerca = { centro:null, origen:null, radio:5, orden:"minutos", res:[] };
const R_TIERRA = 6371.0088;
function haversine(a, b){
  const r = x => x*Math.PI/180, dlat = r(b.lat-a.lat), dlon = r(b.lon-a.lon);
  const h = Math.sin(dlat/2)**2 + Math.cos(r(a.lat))*Math.cos(r(b.lat))*Math.sin(dlon/2)**2;
  return 2*R_TIERRA*Math.asin(Math.sqrt(h));
}
// Geocerca circular como polígono geográfico, para dibujarla con la misma proyección del mapa
function circuloGeo(c, km){ return d3.geoCircle().center([c.lon, c.lat]).radius(km / 111.195).precision(2)(); }
function ponerCentro(c, origen){ cerca.centro = c; cerca.origen = origen; buscarCerca(true); }
async function buscarCerca(volando){
  const c = cerca.centro;
  pintarGeocerca();
  if(!c){ $("cerca-lista").innerHTML = ""; return; }
  if(volando) volarA(circuloGeo(c, cerca.radio).coordinates[0], 60);
  const p = prodActual();
  // Dentro de la geocerca: filtro local en línea recta (rápido y sin red)
  const dentro = new Set(EST.filter(e => haversine(c, e) <= cerca.radio));
  gEst.selectAll("circle").classed("dentro", d => dentro.has(d));
  $("cerca-msj").textContent = `${dentro.size} gasolineras dentro de la geocerca de ${cerca.radio} km. Calculando tiempos…`;
  let lista;
  try {
    if(!MOTOR) throw new Error("sin motor");
    const q = new URLSearchParams({lat:c.lat, lon:c.lon, n:10, radio_km:cerca.radio, producto:p, ordenar_por:cerca.orden});
    if(estado.marca) q.append("marca", estado.marca);
    const r = await pedir(`/api/ruteo/cercanas?${q}`);
    lista = r.resultados.map(d => ({...d, precio:d.precio ?? d.precios?.[p], extra:`${fmt1(d.distancia_km)} km · ${Math.round(d.duracion_min)} min por carretera`}));
    $("cerca-msj").textContent = `${dentro.size} dentro de la geocerca de ${cerca.radio} km${cerca.origen === "gps" ? " alrededor de ti" : ""}. Las ${lista.length} mejores por ${({minutos:"tiempo de manejo", km:"distancia por carretera", precio:"precio"})[cerca.orden]} (motor ${MOTOR.motor}).`;
  } catch(err){
    lista = [...dentro].filter(e => !estado.marca || e.marca === estado.marca)
      .map(e => ({...e, km:haversine(c,e), precio:e.precios[p]})).filter(e => cerca.orden !== "precio" || hay(e.precio))
      .sort((a,b) => cerca.orden === "precio" ? a.precio - b.precio : a.km - b.km).slice(0,10)
      .map(e => ({...e, extra:`${fmt1(e.km)} km en línea recta`}));
    $("cerca-msj").textContent = `${dentro.size} dentro de la geocerca de ${cerca.radio} km. Sin tiempos de manejo (${err.message}): distancias en línea recta.`;
  }
  cerca.res = lista;
  $("cerca-lista").innerHTML = lista.length ? lista.map((d,i) => filaEst(d, i, p)).join("") : `<li class="nota" style="padding:8px 4px">Ninguna gasolinera dentro del radio. Agranda la geocerca.</li>`;
}
function pintarGeocerca(){
  const c = cerca.centro, datos = c && vistaActual() === "cerca" ? [c] : [];
  gGeo.selectAll("path.geocerca").data(datos).join("path").attr("class","geocerca").attr("d", d => ruta(circuloGeo(d, cerca.radio)));
  gGeo.selectAll("circle.yo-onda").data(datos).join("circle").attr("class","yo-onda").attr("r", 14/k).attr("cx", d => proy([d.lon,d.lat])[0]).attr("cy", d => proy([d.lon,d.lat])[1]);
  gGeo.selectAll("circle.yo").data(datos).join("circle").attr("class","yo").attr("r", 5/k).attr("cx", d => proy([d.lon,d.lat])[0]).attr("cy", d => proy([d.lon,d.lat])[1]);
  if(!datos.length) gEst.selectAll("circle.dentro").classed("dentro", false);
}
$("cerca-gps").onclick = () => {
  if(!navigator.geolocation){ $("cerca-msj").textContent = "Este navegador no da la ubicación. Usa «Elegir en el mapa»."; return; }
  $("cerca-msj").textContent = "Pidiendo tu ubicación al navegador…";
  navigator.geolocation.getCurrentPosition(
    pos => ponerCentro({lat:pos.coords.latitude, lon:pos.coords.longitude, rot:"Mi ubicación"}, "gps"),
    err => { $("cerca-msj").textContent = `No se obtuvo la ubicación (${err.message}). Usa «Elegir en el mapa».`; },
    {enableHighAccuracy:true, timeout:10000, maximumAge:60000});
};
$("cerca-mapa").onclick = () => ponerEleccion(ui.elige === "cerca" ? null : "cerca");
$("cerca-radio").addEventListener("input", ev => { cerca.radio = +ev.target.value; $("cerca-radio-val").textContent = `${cerca.radio} km`; pintarGeocerca(); });
$("cerca-radio").addEventListener("change", () => buscarCerca(true));
document.querySelectorAll("#cerca-orden button").forEach(b => b.onclick = () => {
  cerca.orden = b.dataset.o; document.querySelectorAll("#cerca-orden button").forEach(x => x.setAttribute("aria-pressed", x === b)); buscarCerca(false); });

/* ---------- ruta: viaje con recargas óptimas o surtido con pipa ---------- */
const rutaSt = { origen:null, destino:null, base:null, veh:VEHICULOS[0], objetivo:"costo", pedidos:[], res:null };
const opcionesCap = CAPITALES.map((c,i) => `<option value="${i}">${c[0]}</option>`).join("");
["r-origen","r-destino","s-base","f-origen","f-destino"].forEach(id => $(id).innerHTML = `<option value="">— elegir —</option><option value="mapa" hidden>Punto en el mapa</option>` + opcionesCap);
const cap = i => ({rot:CAPITALES[i][0], lat:CAPITALES[i][1], lon:CAPITALES[i][2]});
function fijarPunto(tipo, p){
  rutaSt[tipo] = p;
  const sel = $({origen:"r-origen", destino:"r-destino", base:"s-base"}[tipo] ?? tipo);   // "f-origen"/"f-destino" son ya el id
  const op = sel.querySelector('option[value="mapa"]');
  const i = p ? CAPITALES.findIndex(c => c[0] === p.rot) : -1;
  if(!p) sel.value = "";
  else if(i >= 0) sel.value = String(i);
  else { op.hidden = false; op.textContent = p.rot; sel.value = "mapa"; }
  pintarRuta();
}
[["r-origen","origen"],["r-destino","destino"],["s-base","base"],["f-origen","f-origen"],["f-destino","f-destino"]].forEach(([id,t]) => $(id).onchange = ev => {
  const v = ev.target.value; if(v === "mapa") return; fijarPunto(t, v === "" ? null : cap(+v)); });
document.querySelectorAll("[data-elige]").forEach(b => b.onclick = () => ponerEleccion(ui.elige === b.dataset.elige ? null : b.dataset.elige));
$("r-vehiculos").innerHTML = VEHICULOS.map((v,i) => `<button type="button" data-v="${i}" aria-pressed="${i===0}">${Siluetas.plana(v.k)}${v.rot}</button>`).join("");
function ponerVehiculo(i){
  rutaSt.veh = VEHICULOS[i];
  document.querySelectorAll("#r-vehiculos button").forEach(b => b.setAttribute("aria-pressed", +b.dataset.v === i));
  $("r-tanque").value = rutaSt.veh.tanque; $("r-rend").value = rutaSt.veh.rend; $("r-inicial").value = Math.round(rutaSt.veh.tanque/2);
}
document.querySelectorAll("#r-vehiculos button").forEach(b => b.onclick = () => ponerVehiculo(+b.dataset.v));
ponerVehiculo(0);
document.querySelectorAll("#r-objetivo button").forEach(b => b.onclick = () => {
  rutaSt.objetivo = b.dataset.o; document.querySelectorAll("#r-objetivo button").forEach(x => x.setAttribute("aria-pressed", x === b)); });
function ponerModo(m){
  ui.modo = m;
  document.querySelectorAll("#ruta-modo button").forEach(b => b.setAttribute("aria-pressed", b.dataset.modo === m));
  $("ruta-viaje").hidden = m !== "viaje"; $("ruta-surtido").hidden = m !== "surtido"; $("ruta-flotilla").hidden = m !== "flotilla";
  if(m === "flotilla") conectarFlota();
  rutaSt.res = null; $("ruta-res").innerHTML = ""; $("ruta-msj").textContent = ""; pintarRuta(); pintarPedidos();
}
document.querySelectorAll("#ruta-modo button").forEach(b => b.onclick = () => ponerModo(b.dataset.modo));

function comoLlegar(d){
  ui.panel = null; abrirPanel("ruta"); ponerModo("viaje");
  if(cerca.centro && !rutaSt.origen) fijarPunto("origen", {...cerca.centro, rot:cerca.centro.rot ?? "Punto en el mapa"});
  fijarPunto("destino", {lat:d.lat, lon:d.lon, rot:`Punto · ${d.nombre}`});
  $("ruta-msj").textContent = "Destino: " + d.nombre + (rutaSt.origen ? ". Pulsa calcular." : ". Falta el origen.");
}
function agregarPedido(d){
  if(rutaSt.pedidos.some(p => p.permiso === d.permiso)) return;
  rutaSt.pedidos.push(d); pintarPedidos(); pintarRuta();
}
function quitarPedido(permiso){ rutaSt.pedidos = rutaSt.pedidos.filter(p => p.permiso !== permiso); pintarPedidos(); pintarRuta(); }
function pintarPedidos(){
  const l = +$("s-litros").value || 10000;
  $("s-pedidos").innerHTML = rutaSt.pedidos.length ? rutaSt.pedidos.map((d,i) => `<li style="display:flex;align-items:center"><button type="button" class="fila-est" data-permiso="${esc(d.permiso)}" style="flex:1">
      <i class="num">${String(i+1).padStart(2,"0")}</i><span>${esc(d.nombre)}<small>${esc(d.marca)} · ${esc(d.entidad ?? "")}</small></span><span class="num">${fmt(l)} l</span></button>
      <button type="button" class="quitar" data-quitar="${esc(d.permiso)}" aria-label="Quitar ${esc(d.nombre)}">✕</button></li>`).join("")
    : `<li class="nota" style="padding:8px 4px">Sin pedidos todavía.</li>`;
}
$("s-litros").addEventListener("input", pintarPedidos);

const lonlat = p => [p.lon, p.lat];
function pintarRuta(){
  const v = vistaActual(), visible = v === "ruta" || (!!rutaSt.res && v !== "cerca");
  const r = visible ? rutaSt.res : null;
  const lineas = r ? (r.tipo === "viaje" ? [{c:r.linea, cls:""}] : r.viajes.filter(x => x.linea).map((x,i) => ({c:x.linea, cls:`pipa p${i%3}`}))) : [];
  gRuta.selectAll("path.ruta-halo").data(lineas).join("path").attr("class","ruta-halo").attr("d", d => ruta({type:"LineString", coordinates:d.c}));
  gRuta.selectAll("path.ruta-linea").data(lineas, (d,i) => `${r?.id}-${i}`).join("path").attr("class", d => "ruta-linea " + d.cls).attr("pathLength", 1)
    .attr("d", d => ruta({type:"LineString", coordinates:d.c}));
  const ext = visible ? (ui.modo === "viaje" ? [rutaSt.origen && {...rutaSt.origen, b:false}, rutaSt.destino && {...rutaSt.destino, b:true}]
                                            : [rutaSt.base && {...rutaSt.base, b:false}]).filter(Boolean) : [];
  const paradas = r ? (r.tipo === "viaje" ? r.paradas.map((p,i) => ({...p, n:i+1})) : r.viajes.flatMap(x => x.paradas.map((p,i) => ({...p, n:i+1}))))
                    : (visible && ui.modo === "surtido" ? rutaSt.pedidos.map((p,i) => ({...p, n:i+1})) : []);
  gMarcas.selectAll("circle.extremo").data(ext).join("circle").attr("class", d => "extremo" + (d.b ? " b" : ""))
    .attr("cx", d => proy(lonlat(d))[0]).attr("cy", d => proy(lonlat(d))[1]);
  const g = gMarcas.selectAll("g.parada-g").data(paradas).join(en => { const x = en.append("g").attr("class","parada-g");
    x.append("circle").attr("class","parada"); x.append("text").attr("class","parada-n"); return x; })
    .attr("transform", d => `translate(${proy(lonlat(d))})`);
  g.select("text").text(d => d.n);
  pintarFlota();
  escalarMarcas();
}
function escalarMarcas(){
  gMarcas.selectAll("circle.extremo").attr("r", 6/k);
  gMarcas.selectAll("circle.parada").attr("r", 8/k);
  gMarcas.selectAll("text.parada-n").attr("font-size", 10/k);
  gMarcas.selectAll("g.u-esc").attr("transform", `scale(${1/k})`);
  gMarcas.selectAll("circle.recarga-sug").attr("r", 10/k);
  gGeo.selectAll("circle.yo").attr("r", 5/k); gGeo.selectAll("circle.yo-onda").attr("r", 14/k);
}

$("r-calcular").onclick = async () => {
  const o = rutaSt.origen, d = rutaSt.destino, msj = $("ruta-msj");
  if(!o || !d){ msj.textContent = "Falta " + (!o ? "el origen" : "el destino") + "."; return; }
  if(!MOTOR){ msj.textContent = "El motor de rutas no responde (/api/ruteo). Revisa que el servidor lo haya cargado."; return; }
  const tanque = +$("r-tanque").value;
  const veh = { tanque_l:tanque, rendimiento_km_l:+$("r-rend").value, combustible_inicial_l:Math.min(+$("r-inicial").value, tanque),
                reserva_l:Math.max(2, Math.round(tanque*.08)), producto:rutaSt.veh.prod };
  msj.textContent = "Calculando ruta y paradas…"; $("ruta-res").innerHTML = "";
  try {
    const r = await enviar("/api/ruteo/ruta/recargas", { puntos:[[o.lat,o.lon],[d.lat,d.lon]], vehiculo:veh, objetivo:rutaSt.objetivo,
      corredor_km:+$("r-corredor").value || 3, evitar:[] });
    const linea = r.geojson.features.find(f => f.properties.tipo === "ruta").geometry.coordinates;
    rutaSt.res = { tipo:"viaje", id:Date.now(), linea, paradas:r.plan ? r.plan.paradas : [] };
    pintarRuta(); volarA(linea, 30);
    const autonomia = (veh.tanque_l - veh.reserva_l) * veh.rendimiento_km_l;
    msj.textContent = r.plan ? `Motor ${r.motor}. Autonomía útil ${fmt(Math.round(autonomia))} km con ${NOM_PROD[veh.producto].toLowerCase()}.` : (r.motivo ?? "No hay plan posible.");
    $("ruta-res").innerHTML = `<div class="kpis">
        <div class="kpi"><span class="eti">Distancia</span><b class="num">${fmt1(r.distancia_km)} km</b><small>${Math.floor(r.duracion_min/60)} h ${Math.round(r.duracion_min%60)} min con paradas</small></div>
        <div class="kpi"><span class="eti">Paradas</span><b class="num">${r.plan ? r.plan.num_paradas : SIN}</b><small>${r.plan ? `${fmt1(r.plan.litros_comprados)} l comprados` : ""}</small></div>
        <div class="kpi"><span class="eti">Gasto en ruta</span><b class="num">${r.plan ? pesos(r.plan.costo_combustible) : SIN}</b><small>solo lo que se carga en el camino</small></div>
        <div class="kpi"><span class="eti">Llega con</span><b class="num">${r.plan ? fmt1(r.plan.litros_al_llegar) + " l" : SIN}</b><small>reserva mínima ${veh.reserva_l} l</small></div></div>
      ${r.plan && r.plan.paradas.length ? `<div class="eti">Paradas de recarga</div><ol class="lista-est">${r.plan.paradas.map((p,i) =>
        filaEst({...p, extra:`km ${fmt1(p.km_ruta)} · desvío ${fmt2(p.desvio_km)} km · ${fmt1(p.litros)} l = ${pesos(p.costo)}`}, i, veh.producto)).join("")}</ol>` : ""}
      ${r.motor !== "osrm" ? `<p class="nota">Sin OSRM: la ruta usa la red vial de ejemplo y puede no seguir las carreteras reales.</p>` : ""}`;
  } catch(err){ msj.textContent = "No se pudo calcular: " + err.message; }
};
$("s-calcular").onclick = async () => {
  const b = rutaSt.base, msj = $("ruta-msj");
  if(!b){ msj.textContent = "Falta la base de la pipa."; return; }
  if(!rutaSt.pedidos.length){ msj.textContent = "Agrega al menos una gasolinera al surtido (clic en el mapa)."; return; }
  if(!MOTOR){ msj.textContent = "El motor de rutas no responde (/api/ruteo)."; return; }
  const litros = +$("s-litros").value || 10000, capL = +$("s-cap").value || 20000, n = Math.max(1, +$("s-pipas").value || 1);
  msj.textContent = "Planeando el surtido…"; $("ruta-res").innerHTML = "";
  try {
    const r = await enviar("/api/ruteo/ruta/surtido", { base:[b.lat,b.lon],
      pedidos:rutaSt.pedidos.map(p => ({id:p.permiso, lat:p.lat, lon:p.lon, litros, datos:{nombre:p.nombre}})),
      pipas:d3.range(n).map(i => ({id:`Pipa ${i+1}`, capacidad_l:capL})), segundos_busqueda:3 });
    rutaSt.res = { tipo:"surtido", id:Date.now(), viajes:r.viajes.map(v => ({...v, paradas:v.paradas.map(p => ({...p, ...(POR_PERMISO.get(p.id) ?? {})}))})) };
    pintarRuta();
    volarA([lonlat(b), ...rutaSt.pedidos.map(lonlat)], 30);
    msj.textContent = `Método: ${r.metodo === "ortools" ? "OR-Tools (VRP con capacidad)" : "heurística (vecino más cercano + 2-opt)"}. ${r.no_atendidas.length ? r.no_atendidas.length + " sin atender." : "Todas atendidas."}`;
    $("ruta-res").innerHTML = `<div class="kpis">
        <div class="kpi"><span class="eti">Viajes</span><b class="num">${r.viajes.length}</b><small>${fmt(r.litros_entregados)} l entregados</small></div>
        <div class="kpi"><span class="eti">Recorrido total</span><b class="num">${fmt1(r.distancia_total_km)} km</b><small>base → estaciones → base</small></div></div>
      ${r.viajes.map((v,i) => `<div class="pod" style="--c:${["var(--ambar)","#b48cff","#7ee08a"][i%3]};align-items:stretch;text-align:left">
          <div class="pod-holo">${Siluetas.plana("pipa")}</div>
          <div class="fila"><span>${esc(v.pipa)} · viaje ${i+1}</span><span class="num">${fmt1(v.distancia_km)} km · ${fmt(v.litros)} l</span></div>
          <span class="nota">${v.paradas.map((p,j) => `${j+1}. ${esc(POR_PERMISO.get(p.id)?.nombre ?? p.id)}`).join(" → ")}</span>
          <i class="pod-barra"><u style="transform:scaleX(${v.ocupacion ?? 0})"></u></i></div>`).join("")}`;
  } catch(err){ msj.textContent = "No se pudo planear: " + err.message; }
};


/* ---------- ruta: flotilla en vivo (varias unidades, WebSocket /api/ruteo/flotilla/ws) ----------
   El servidor calcula y recalcula las rutas; aquí solo se dibuja lo que llega:
   "estado" (foto completa), "ruta" (línea nueva), "posicion" (avance), "alerta" y "eliminado". */
const TIPOS_FLOTA = [
  {k:"pipa", rot:"Pipa", tanque:600, rend:2.4, prod:"diesel"},
  {k:"tracto", rot:"Tracto", tanque:600, rend:2.6, prod:"diesel"},
  {k:"comercial", rot:"Reparto", tanque:100, rend:7, prod:"diesel"},
  {k:"pickup", rot:"Pick up", tanque:80, rend:9, prod:"regular"},
  {k:"sedan", rot:"Auto", tanque:45, rend:14, prod:"regular"},
];
// `var`: pintarRuta() puede correr al arrancar, antes de que se evalúe esta línea
var flota = { ws:null, conectada:false, reintento:0, timer:null, unidades:new Map(), alertas:[], tipo:TIPOS_FLOTA[0], simulando:false, sel:null };
$("f-tipos").innerHTML = TIPOS_FLOTA.map((v,i) => `<button type="button" data-t="${i}" aria-pressed="${i===0}">${Siluetas.plana(v.k)}${v.rot}</button>`).join("");
document.querySelectorAll("#f-tipos button").forEach(b => b.onclick = () => {
  flota.tipo = TIPOS_FLOTA[+b.dataset.t];
  document.querySelectorAll("#f-tipos button").forEach(x => x.setAttribute("aria-pressed", x === b)); });

function conectarFlota(){
  if(flota.ws || !MOTOR) { if(!MOTOR) estadoFlota("El motor de rutas no responde (/api/ruteo)", "no"); return; }
  const ws = new WebSocket(location.origin.replace(/^http/, "ws") + "/api/ruteo/flotilla/ws");
  flota.ws = ws; estadoFlota("Conectando…");
  ws.onopen = () => { flota.conectada = true; flota.reintento = 0; estadoFlota("En vivo", "si"); };
  ws.onmessage = m => recibirFlota(JSON.parse(m.data));
  ws.onclose = () => {   // reconexión con espera creciente (1, 2, 4… hasta 30 s)
    flota.ws = null; flota.conectada = false;
    const espera = Math.min(30, 2 ** flota.reintento++);
    estadoFlota(`Sin conexión · reintento en ${espera} s`, "no");
    clearTimeout(flota.timer); flota.timer = setTimeout(conectarFlota, espera * 1000);
  };
}
function estadoFlota(texto, clase = ""){ $("f-estado").textContent = texto; $("f-luz").className = "luz " + clase; }

function guardarUnidad(v){
  const ant = flota.unidades.get(v.id);
  const u = {...ant, ...v};
  if(!v.linea && ant?.linea) u.linea = ant.linea;
  // Sentido de la silueta: mira hacia donde avanza (oeste → se voltea)
  if(ant && (v.lon !== ant.lon)) u.dir = v.lon < ant.lon ? -1 : 1;
  u.dir ??= 1;
  flota.unidades.set(v.id, u);
}
let pintaPendiente = false;
function repintarFlota(){   // varias posiciones llegan juntas: un solo repintado por cuadro
  if(pintaPendiente) return; pintaPendiente = true;
  requestAnimationFrame(() => { pintaPendiente = false; pintarFlota(); escalarMarcas(); listarFlota(); });
}
function recibirFlota(e){
  if(e.tipo === "estado"){
    flota.unidades.clear();
    const lineas = {};
    e.geojson.features.filter(f => f.properties.tipo === "ruta_vehiculo").forEach(f => lineas[f.properties.id] = f.geometry.coordinates);
    e.geojson.features.filter(f => f.properties.tipo === "vehiculo").forEach(f => guardarUnidad({...f.properties, linea:lineas[f.properties.id]}));
  } else if(e.tipo === "ruta" || e.tipo === "posicion") guardarUnidad(e.vehiculo);
  else if(e.tipo === "eliminado"){ flota.unidades.delete(e.id); if(flota.sel === e.id) flota.sel = null; }
  else if(e.tipo === "alerta" || e.tipo === "error"){
    flota.alertas.unshift({...e, hora:new Date()}); flota.alertas.length = Math.min(flota.alertas.length, 30); listarAlertas();
  }
  repintarFlota();
}

function pintarFlota(){
  if(!flota) return;
  const lista = [...flota.unidades.values()];
  gRuta.selectAll("path.flota-linea").data(lista.filter(u => u.linea && !u.llego), u => u.id).join("path")
    .attr("class","flota-linea").style("--c", u => u.color).attr("d", u => ruta({type:"LineString", coordinates:u.linea}));
  const sug = lista.filter(u => u.siguiente_recarga && !u.llego).map(u => ({...u.siguiente_recarga, id:u.id}));
  gMarcas.selectAll("circle.recarga-sug").data(sug, d => d.id).join("circle").attr("class","recarga-sug")
    .attr("cx", d => proy(lonlat(d))[0]).attr("cy", d => proy(lonlat(d))[1]);
  const g = gMarcas.selectAll("g.unidad").data(lista, u => u.id).join(en => {
    const x = en.append("g").attr("class","unidad").on("click", (ev, u) => { ev.stopPropagation(); enfocarUnidad(u.id); });
    const s = x.append("g").attr("class","u-esc");
    s.append("circle").attr("class","u-pulso").attr("r", 13);
    s.append("circle").attr("class","u-aro").attr("r", 11);
    s.append("g").attr("class","u-sil");
    s.append("text").attr("y", -16).attr("text-anchor","middle").attr("font-size", 10);
    x.append("title");
    return x;
  });
  g.classed("llego", u => !!u.llego).style("--c", u => u.color)
    .attr("transform", u => `translate(${proy([u.lon, u.lat])})`);
  g.select("g.u-sil").each(function(u){   // la silueta se dibuja una vez por tipo
    const sel = d3.select(this);
    if(sel.attr("data-k") !== (u.tipo ?? "pipa")) sel.attr("data-k", u.tipo ?? "pipa").html(Siluetas.plana(u.tipo ?? "pipa"));
    sel.attr("transform", `scale(${u.dir},1)`).select("svg").attr("x", -9).attr("y", -5).attr("width", 18).attr("height", 9);
  });
  g.select("text").text(u => u.nombre.length > 18 ? u.nombre.slice(0, 17) + "…" : u.nombre);
  g.select("title").text(u => `${u.nombre} · ${u.llego ? "llegó" : `${fmt1(u.km_restante)} km, ${duracion(u.min_restante)}`}`);
}
const duracion = min => min >= 60 ? `${Math.floor(min/60)} h ${Math.round(min%60)} min` : `${Math.round(min)} min`;
const horaLlegada = u => u.eta_epoch ? new Date(u.eta_epoch * 1000).toLocaleTimeString("es-MX", {hour:"2-digit", minute:"2-digit"}) : "—";

function listarFlota(){
  const lista = [...flota.unidades.values()];
  $("f-unidades").innerHTML = lista.length ? lista.map(u => `<li style="--c:${esc(u.color)}">
      <button type="button" class="fila-est${flota.sel === u.id ? " sel" : ""}" data-unidad="${esc(u.id)}">
        ${Siluetas.plana(u.tipo ?? "pipa")}
        <span>${esc(u.nombre)}<small>${u.llego ? `<b class="llego">Llegó</b>` : `${fmt1(u.km_restante)} km · ${duracion(u.min_restante)} · llega ${horaLlegada(u)}`}
          ${u.velocidad_kmh ? ` · ${Math.round(u.velocidad_kmh)} km/h` : ""}${hay(u.litros) ? ` · ${fmt(Math.round(u.litros))} l` : ""}
          ${u.siguiente_recarga ? `<br>⛽ cargar en ${esc(u.siguiente_recarga.nombre)}` : ""}</small>
          <i class="avance"><u style="transform:scaleX(${Math.min(1, u.avance ?? 0)})"></u></i></span>
        <span class="num">${Math.round(100 * Math.min(1, u.avance ?? 0))}%</span></button>
      <button type="button" class="quitar" data-quitar-unidad="${esc(u.id)}" aria-label="Quitar ${esc(u.nombre)}">✕</button></li>`).join("")
    : `<li class="nota" style="padding:8px 4px">Sin unidades. Agrega una o carga las de ejemplo.</li>`;
}
function listarAlertas(){
  $("f-alertas").innerHTML = flota.alertas.length ? flota.alertas.map(a => `<li class="${esc(a.alerta ?? a.tipo)}">
      <small>${a.hora.toLocaleTimeString("es-MX", {hour:"2-digit", minute:"2-digit", second:"2-digit"})}</small>${esc(a.mensaje)}</li>`).join("")
    : `<li class="nota">Sin alertas.</li>`;
}
$("f-unidades").addEventListener("click", async ev => {
  const q = ev.target.closest("[data-quitar-unidad]");
  if(q){ try { await pedir(`/api/ruteo/flotilla/vehiculos/${encodeURIComponent(q.dataset.quitarUnidad)}`, {method:"DELETE"}); }
         catch(err){ $("ruta-msj").textContent = "No se pudo quitar: " + err.message; } return; }
  const b = ev.target.closest("[data-unidad]"); if(b) enfocarUnidad(b.dataset.unidad);
});
function enfocarUnidad(id){
  const u = flota.unidades.get(id); if(!u) return;
  flota.sel = id; listarFlota();
  volarA(u.linea?.length ? u.linea : [[u.lon, u.lat]], 30, 0.3);
}

async function altaUnidades(vehiculos){
  if(!MOTOR){ $("ruta-msj").textContent = "El motor de rutas no responde (/api/ruteo)."; return; }
  conectarFlota();
  $("ruta-msj").textContent = vehiculos.length > 1 ? `Calculando ${vehiculos.length} rutas…` : "Calculando la ruta…";
  try {
    const r = await enviar("/api/ruteo/flotilla/vehiculos", {vehiculos});
    if(!flota.conectada) r.eventos.forEach(recibirFlota);   // si el WebSocket está abierto, los mismos eventos ya llegan por ahí
    $("ruta-msj").textContent = `${vehiculos.length} ${vehiculos.length > 1 ? "unidades agregadas" : "unidad agregada"}.`
      + (MOTOR.motor !== "osrm" ? " Sin OSRM las rutas usan la red vial de ejemplo." : "");
    const pts = [...flota.unidades.values()].flatMap(u => u.linea ?? [[u.lon, u.lat]]);
    if(pts.length) volarA(pts, 30);
  } catch(err){ $("ruta-msj").textContent = "No se pudo agregar: " + err.message; }
}
const unidadDe = (id, nombre, t, o, d, litros) => ({ id, nombre, posicion:[o.lat, o.lon], destinos:[[d.lat, d.lon]], datos:{tipo:t.k},
  ...(hay(litros) ? {combustible:{tanque_l:t.tanque, rendimiento_km_l:t.rend, combustible_inicial_l:Math.min(litros, t.tanque),
                                   reserva_l:Math.max(2, Math.round(t.tanque*.08)), producto:t.prod}} : {}) });
$("f-agregar").onclick = () => {
  const o = rutaSt["f-origen"], d = rutaSt["f-destino"];
  if(!o || !d){ $("ruta-msj").textContent = "Falta " + (!o ? "de dónde sale" : "a dónde va") + " la unidad."; return; }
  const n = flota.unidades.size + 1, litrosTxt = $("f-litros").value;
  const nombre = $("f-nombre").value.trim() || `${flota.tipo.rot} ${n}`;
  altaUnidades([unidadDe(`u${Date.now().toString(36)}`, nombre, flota.tipo, o, d, litrosTxt === "" ? null : +litrosTxt)]);
  $("f-nombre").value = "";
};
$("f-ejemplo").onclick = () => {
  const c = nombre => cap(CAPITALES.findIndex(x => x[0].startsWith(nombre)));
  const TF = Object.fromEntries(TIPOS_FLOTA.map(t => [t.k, t]));
  altaUnidades([
    unidadDe("ej-1", "Pipa 01 · CDMX → Monterrey", TF.pipa, c("CDMX"), c("Monterrey"), 260),
    unidadDe("ej-2", "Tracto 02 · CDMX → Guadalajara", TF.tracto, c("CDMX"), c("Guadalajara"), null),
    unidadDe("ej-3", "Pick up 03 · Querétaro → Zacatecas", TF.pickup, c("Querétaro"), c("Zacatecas"), null),
    unidadDe("ej-4", "Pipa 04 · Monterrey → N. Laredo", TF.pipa, c("Monterrey"), c("Nuevo Laredo"), null),
    unidadDe("ej-5", "Auto 05 · Puebla → Veracruz", TF.sedan, c("Puebla"), c("Veracruz"), 30),
    unidadDe("ej-6", "Reparto 06 · Toluca → Morelia", TF.comercial, c("Toluca"), c("Morelia"), null),
  ]);
};
async function simularFlota(activa){
  try {
    await enviar("/api/ruteo/flotilla/simulacion", {activa, cada_seg:1, acelerar:+$("f-vel").value});
    flota.simulando = activa;
    $("f-simular").setAttribute("aria-pressed", activa); $("f-simular").textContent = activa ? "⏸ Pausar" : "▶ Simular";
  } catch(err){ $("ruta-msj").textContent = "No se pudo cambiar la simulación: " + err.message; }
}
$("f-simular").onclick = () => simularFlota(!flota.simulando);
$("f-vel").onchange = () => { if(flota.simulando) simularFlota(true); };
listarFlota();

/* ================= 8. PANEL ÚNICO Y LÍNEA DE TIEMPO ================= */
const TITULOS = { indicador:"Indicador y vista", ranking:"Ranking de entidades", marcas:"Marcas", capas:"Capas", buscar:"Buscador",
  patrulla:"Patrulla automática", fuentes:"Fuentes y metodología", nacional:"Panorama nacional", expediente:"Expediente",
  cerca:"Cerca de mí · geocerca", ruta:"Ruta y recargas", estacion:"Ficha de gasolinera" };
function vistaActual(){ return ui.panel ?? (estado.sel ? "expediente" : null); }
function pintarPanel(){
  const v = vistaActual(), panel = $("panel");
  if(v){
    panel.querySelectorAll("[data-vista]").forEach(s => s.hidden = s.dataset.vista !== v);
    $("panel-tit").textContent = v === "expediente" && estado.cmp ? "Comparación" : TITULOS[v];
    $("panel-cerrar").setAttribute("aria-label", v === "expediente" ? "Soltar el objetivo" : "Cerrar el panel");
  }
  panel.classList.toggle("abierto", !!v); panel.inert = !v;
  app.classList.toggle("con-panel", !!v);
  document.querySelectorAll(".hta[data-panel]").forEach(b => b.setAttribute("aria-expanded", b.dataset.panel === ui.panel));
  $("cifra-nac").setAttribute("aria-expanded", ui.panel === "nacional");
  if(v !== "estacion" && estado.est){ estado.est = null; marcarEstacion(); }
  if(v !== "ruta" && v !== "cerca" && ui.elige) ponerEleccion(null);
  pintarGeocerca(); pintarRuta();
  if(v) animarRelojes();
}
function abrirPanel(nombre, boton){
  cancelarSecuencia();
  ui.panel = ui.panel === nombre ? null : nombre;
  ui.origen = boton ?? null;
  $("panel").style.setProperty("--retraso", "0ms");
  if(ui.panel === "ranking") ranking();
  pintarPanel(); acomodarCamara();
  if(ui.panel === "buscar"){ $("buscar").value = ""; listarBusqueda(); $("buscar").focus({preventScroll:true}); }
  else if(ui.panel === "cerca" && cerca.centro) buscarCerca(true);
  else if(ui.panel) $("panel").focus({preventScroll:true});
}
function cerrarPanel(){
  if(ui.panel){
    ui.panel = null; $("panel").style.setProperty("--retraso", "0ms");
    pintarPanel(); acomodarCamara();
    if(ui.origen && !vistaActual()) ui.origen.focus({preventScroll:true});
  } else if(estado.sel) seleccionar(null);
}
document.querySelectorAll(".hta[data-panel]").forEach(b => b.onclick = () => abrirPanel(b.dataset.panel, b));
$("cifra-nac").onclick = () => abrirPanel("nacional", $("cifra-nac"));
$("panel-cerrar").onclick = cerrarPanel;

/* ---------- línea de tiempo: cortes diarios de precio ---------- */
function armarLineaTiempo(){
  const r = $("anio"), pos = i => `calc(${FECHAS.length > 1 ? i/(FECHAS.length-1)*100 : 50}%)`;
  r.min = 0; r.max = ULT; r.value = estado.f;
  const v = FECHAS.map((_,i) => precioNac("regular", i)), lo = d3.min(v.filter(hay)) ?? 0, hi = d3.max(v.filter(hay)) ?? 1;
  const cada = Math.ceil(FECHAS.length / 8), ancho = Math.max(3, Math.min(22, 600/FECHAS.length));
  $("anio-barras").innerHTML = FECHAS.map((f,i) => `<i data-a="${i}" style="left:${pos(i)};width:${ancho}px;margin-left:-${ancho/2}px;height:${hay(v[i]) ? 4 + 22*(hi > lo ? (v[i]-lo)/(hi-lo) : .5) : 0}px" title="${fechaTxt(f)}"></i>`).join("");
  $("anio-marcas").innerHTML = FECHAS.map((f,i) => i % cada === 0 || i === ULT ? `<span data-a="${i}" style="left:${pos(i)}">${fechaCorta(f)}</span>` : "").join("");
  $("anio-barras").querySelectorAll("i").forEach(b => b.onclick = () => { detener(); ponerFecha(+b.dataset.a); });
}
function lineaTiempo(){
  $("anio-val").textContent = fechaCorta(FECHAS[estado.f]); $("anio").value = estado.f;
  document.querySelectorAll("#anio-barras i, #anio-marcas span").forEach(x => x.classList.toggle("va", +x.dataset.a === estado.f));
  const solo = !M().serie || FECHAS.length < 2;
  $("anio").disabled = solo; $("play").disabled = solo;
  const nota = FECHAS.length < 2 ? `Solo hay un corte de precios (${fechaTxt(FECHAS[ULT])}). El histórico crece con cada corrida diaria del pipeline.`
    : !M().serie ? "Este indicador no cambia por fecha." : `${FECHAS.length} cortes diarios de precio. Las barras son el promedio nacional de regular.`;
  $("nota-anio").textContent = nota; $("nota-metrica").textContent = nota;
}
function alternarFranja(abrir = !ui.franja){
  ui.franja = abrir;
  app.classList.toggle("con-franja", abrir);
  $("franja").inert = !abrir;
  $("h-tiempo").setAttribute("aria-expanded", abrir);
  acomodarCamara();
  if(abrir) $("play").focus({preventScroll:true}); else if(document.activeElement === document.body) $("h-tiempo").focus({preventScroll:true});
}
$("h-tiempo").onclick = () => alternarFranja();
$("franja-cerrar").onclick = () => { alternarFranja(false); $("h-tiempo").focus({preventScroll:true}); };

function refrescar(){
  pintar(); armarHolo(); ranking(); cifraNacional(); nacional(); expediente();
  leyenda(); aviso(); lineaTiempo(); pintarPatrulla(); animarCifras();
}

/* ================= 9. CONTROLES Y ATAJOS ================= */
function ponerMetrica(m){
  estado.metrica = m;
  document.querySelectorAll("#seg-metrica button, #seg-metrica-b button").forEach(x => x.setAttribute("aria-pressed", x.dataset.m === m));
  if(!M().serie){ detener(); estado.f = ULT; }
  refrescar(); cinta();
}
function ponerVista(v){
  estado.vista = v;
  document.querySelectorAll("#seg-vista button").forEach(x => x.setAttribute("aria-pressed", x.dataset.v === v));
  pintar(); armarHolo();
}
document.querySelectorAll("#seg-metrica button, #seg-metrica-b button").forEach(b => b.onclick = () => ponerMetrica(b.dataset.m));
document.querySelectorAll("#seg-vista button").forEach(b => b.onclick = () => ponerVista(b.dataset.v));
document.querySelectorAll("#capas button").forEach(b => b.onclick = () => {
  estado.capas[b.dataset.c] = !estado.capas[b.dataset.c]; b.setAttribute("aria-pressed", estado.capas[b.dataset.c]); pintar(); leyenda();
});
function ponerFecha(f){ if(!M().serie) return; estado.f = Math.max(0, Math.min(ULT, f)); refrescar(); }
$("anio").addEventListener("input", ev => { detener(); ponerFecha(+ev.target.value); });
let cine = null;
function detener(){ if(cine){ clearInterval(cine); cine = null; $("play").textContent = "▶"; $("play").setAttribute("aria-label","Reproducir la serie de precios"); } }
function reproducir(){
  if(cine){ detener(); return; }
  if(!M().serie || FECHAS.length < 2) return;
  $("play").textContent = "❚❚"; $("play").setAttribute("aria-label","Pausar la reproducción");
  if(estado.f === ULT) estado.f = -1;
  cine = setInterval(() => { estado.f++; refrescar(); if(estado.f >= ULT) detener(); }, Math.max(250, 6000/FECHAS.length));
}
$("play").onclick = reproducir;
$("z-mas").onclick = () => svg.transition().duration(250).call(zoom.scaleBy, 1.6);
$("z-menos").onclick = () => svg.transition().duration(250).call(zoom.scaleBy, 1/1.6);
$("z-rst").onclick = () => { camaraLibre = false; if(estado.sel) seleccionar(null); else enfocar(); };
function pantallaCompleta(){
  if(document.fullscreenElement){ document.exitFullscreen(); return; }
  const raiz = document.documentElement;
  if(raiz.requestFullscreen) raiz.requestFullscreen().catch(() => {});
}
$("z-full").onclick = pantallaCompleta;

document.addEventListener("keydown", ev => {
  if(ev.ctrlKey || ev.metaKey || ev.altKey) return;
  const t = ev.key.toLowerCase(), enCampo = ev.target.matches("input, textarea, select");
  if(t === "escape"){
    if(enCampo) ev.target.blur();
    if(ui.elige) ponerEleccion(null);
    else if(estado.eligeCmp){ estado.eligeCmp = false; aviso(); }
    else if(ui.panel) cerrarPanel();
    else if(estado.sel) seleccionar(null);
    else if(patrulla.id){ pararPatrulla(); aviso(); }
    else if(ui.franja){ alternarFranja(false); $("h-tiempo").focus({preventScroll:true}); }
    return;
  }
  if(enCampo) return;
  const metr = {"1":"regular","2":"premium","3":"diesel","4":"estaciones","5":"tomas"};
  if(t === "arrowright"){ detener(); ponerFecha(estado.f+1); }
  else if(t === "arrowleft"){ detener(); ponerFecha(estado.f-1); }
  else if(t === " " && !ev.target.matches("button")){ ev.preventDefault(); reproducir(); }
  else if(metr[t]) ponerMetrica(metr[t]);
  else if(t === "v") ponerVista(estado.vista === "coro" ? "burb" : "coro");
  else if(t === "p"){ alternarPatrulla(); aviso(); }
  else if(t === "g") abrirPanel("cerca", $("h-cerca"));
  else if(t === "r") abrirPanel("ruta", $("h-ruta"));
  else if(t === "f") pantallaCompleta();
  else if(t === "c" && estado.sel && !estado.cmp){ estado.eligeCmp = !estado.eligeCmp; aviso(); }
});

/* ---------- primera pintura y cambios de tamaño ---------- */
armarLineaTiempo(); modelos(); cinta(); pintarPedidos(); dibujar(); refrescar(); pintarPanel();
let ancho0 = cont.clientWidth, alto0 = cont.clientHeight;
new ResizeObserver(() => {
  if(cont.clientWidth === ancho0 && cont.clientHeight === alto0) return;
  ancho0 = cont.clientWidth; alto0 = cont.clientHeight;
  svg.interrupt("camara"); svg.call(zoom.transform, d3.zoomIdentity); camaraLibre = false;
  dibujar(); enfocar();
}).observe(cont);
// Para pruebas automáticas: expone el estado sin cambiar el comportamiento
window.__gas = { estado, ui, rutaSt, cerca, verEstacion, ponerCentro, fijarPunto, cap, agregarPedido, EST };
}

iniciar().catch(err => {
  const caja = $("arranque"), copia = caja.cloneNode(true);
  caja.replaceWith(copia);
  copia.classList.remove("fuera"); copia.style.cursor = "default";
  copia.querySelector("#arr-log").textContent = `NO SE PUDO CARGAR\n${err.message}\n\nEjecuta  python scripts\\construir_datos.py\ny vuelve a iniciar el servidor.`;
  copia.querySelector("#arr-nota").textContent = "Sin conexión con la API";
  console.error(err);
});

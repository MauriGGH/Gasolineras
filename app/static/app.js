/* Ojo de Dios · Robo vehicular MX — interfaz.
   Todas las cifras llegan de la API local (app/main.py); aquí no hay datos incrustados.
   Si un dato no existe se escribe "sin dato": nunca un cero ni un estimado.

   Orden del archivo:
     1. utilidades y arranque          6. piezas de los expedientes
     2. datos, estado y escalas        7. herramientas (ranking, submarcas, buscador…)
     3. mapa y cámara                  8. panel único y línea de tiempo
     4. objetivo fijado (secuencia)    9. controles y atajos de teclado
     5. tooltips y cifras animadas */
"use strict";

/* ================= 1. UTILIDADES Y ARRANQUE ================= */
const $ = id => document.getElementById(id);
const fmt  = n => Number(n).toLocaleString("es-MX");
const fmt1 = n => Number(n).toLocaleString("es-MX", {minimumFractionDigits:1, maximumFractionDigits:1});
const fmt2 = n => Number(n).toLocaleString("es-MX", {minimumFractionDigits:2, maximumFractionDigits:2});
const sinMovimiento = matchMedia("(prefers-reduced-motion: reduce)").matches;
const angosta = matchMedia("(max-width: 720px)");      // móvil: los paneles son hojas inferiores

// Datos faltantes: `hay` dice si un valor existe; `con` lo formatea o escribe "sin dato".
const SIN = `<span class="sd">sin dato</span>`;
const hay = v => typeof v === "number" ? Number.isFinite(v) : (v !== null && v !== undefined && v !== "");
const con = (v, f) => hay(v) ? f(v) : SIN;
const orden = v => hay(v) ? v : -Infinity;             // lo que falta va al final de cualquier ordenamiento

async function pedir(ruta){
  const r = await fetch(ruta);
  if(!r.ok) throw new Error(`${ruta} respondió ${r.status}`);
  return r.json();
}

/* Secuencia de arranque: cada línea reporta una comprobación real */
function arranque(lineas){
  const caja = $("arranque"), log = $("arr-log");
  const cerrar = () => caja.classList.add("fuera");
  caja.addEventListener("click", cerrar);
  if(sinMovimiento){ cerrar(); return; }
  lineas.forEach((t,i) => setTimeout(() => { log.textContent += t + "\n"; }, 170*i));
  setTimeout(cerrar, 170*lineas.length + 550);
}

async function iniciar(){
/* ================= 2. DATOS, ESTADO Y ESCALAS ================= */
const [DATOS, GEO] = await Promise.all([pedir("/api/datos"), pedir("/api/geo/estados")]);

const ANIOS = DATOS.anios, E = DATOS.entidades, NAC = DATOS.nacional;
const NOMBRES = Object.keys(E);
const ULT = ANIOS[ANIOS.length-1], PRI = ANIOS[0];

// Comprobación en el navegador: la suma de entidades debe igualar el total nacional de cada año
const cuadra = ANIOS.every(a => d3.sum(NOMBRES, n => E[n].robos[a]) === NAC.robos[a]);
arranque([
  "› enlace con API local ................. OK",
  `› entidades cargadas ................... ${NOMBRES.length}`,
  `› serie anual .......................... ${PRI}–${ULT}`,
  `› suma de entidades = total nacional ... ${cuadra ? "OK" : "NO CUADRA"}`,
  `› focos municipales / submarcas ........ ${DATOS.municipios.length} / ${DATOS.submarcas.length}`,
  "› proyección cónica conforme fijada .... OK",
]);
$("estatus").textContent = `En línea · ${NOMBRES.length} entidades · ${DATOS.municipios.length} focos · corte dic ${ULT}` + (cuadra ? " · sumas verificadas" : " · sumas no cuadran");

// Lo que el usuario eligió ver en el mapa
const estado = { metrica:"robos", anio:ULT, sel:null, cmp:null, eligeCmp:false, vista:"coro", marca:null,
                 capas:{focos:true, etiq:false, ret:true, barrido:true, cinta:false} };
// Lo que está abierto encima del mapa. `panel` es una herramienta; el expediente no se guarda aquí:
// aparece solo cuando hay objetivo fijado y ninguna herramienta lo tapa.
const ui = { panel:null, franja:false, origen:null, secc:{ent:"vehiculos", nac:"serie", cmp:"serie"} };
const app = $("app");

const maxRobos = d3.max(NOMBRES, n => d3.max(ANIOS, a => E[n].robos[a]));
const rampaCalor = d3.interpolateRgbBasis(["#17293b","#4a3230","#a35a1c","#ffb224","#ff4130"]);
const rampaFria  = d3.interpolateRgbBasis(["#17293b","#15475a","#2a8ba3","#62d3e8","#d8f7ff"]);
const METRICAS = {
  robos:{ titulo:"Vehículos asegurados robados", rampa:rampaCalor,
          escala:d3.scaleSqrt().domain([0,maxRobos]).range([0,1]).clamp(true),
          valor:(e,a)=>e.robos[a], texto:v=>fmt(v), min:"0", max:fmt(maxRobos) },
  viol:{  titulo:`% de robos con violencia · ${ULT}`, rampa:rampaCalor,
          escala:d3.scaleLinear().domain([20,85]).range([0,1]).clamp(true),
          valor:e=>e.pct_violencia, texto:v=>fmt2(v)+" %", min:"20 %", max:"85 %" },
  recu:{  titulo:`% de recuperación · ${ULT}`, rampa:rampaFria,
          escala:d3.scaleLinear().domain([25,100]).range([0,1]).clamp(true),
          valor:e=>e.pct_recuperacion, texto:v=>fmt2(v)+" %", min:"25 %", max:"100 % o más" }
};
const SIN_COLOR = "#161d29";                        // entidad sin dato: gris neutro, fuera de la rampa
const M = () => METRICAS[estado.metrica];
const val = n => M().valor(E[n], estado.anio);
const color = n => hay(val(n)) ? M().rampa(M().escala(val(n))) : SIN_COLOR;
const ordenados = () => NOMBRES.slice().sort((a,b) => orden(val(b)) - orden(val(a)));
const lugarDe = (n,a) => hay(E[n].robos[a])
  ? NOMBRES.slice().sort((x,y) => orden(E[y].robos[a]) - orden(E[x].robos[a])).indexOf(n)+1 : null;
// Variación porcentual contra el año anterior; null si falta alguno de los dos datos
const variacion = (ahora, antes) => (hay(ahora) && hay(antes) && antes !== 0) ? (ahora/antes-1)*100 : null;
const txtVariacion = (v, a) => v === null ? "" :
  `<span class="${v<0?"baja":"sube"} num">${v<0?"▼":"▲"} ${fmt1(Math.abs(v))} % vs ${a-1}</span>`;

/* ================= 3. MAPA Y CÁMARA ================= */
const svg = d3.select("#svg"), cont = $("mapa");
// Recursos del holograma de la entidad: trama de líneas, degradado del escaneo y recortes
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
const gFocos = gZoom.append("g");
const miraV = svg.append("line").attr("class","mira"), miraH = svg.append("line").attr("class","mira");
const miraC = svg.append("circle").attr("class","mira-c").attr("r",9).attr("cx",-99);
// Cónica Conforme de Lambert con los parámetros que usa INEGI para la República
const proy = d3.geoConicConformal().parallels([17.5,29.5]).rotate([102,0]).center([0,24]);
const ruta = d3.geoPath(proy);
const FT = Object.fromEntries(GEO.features.map(f => [f.properties.nombre, f]));
let k = 1, T = d3.zoomIdentity, C = {}, primera = true;
let PAIS = [[0,0],[1,1]];          // caja del país en la proyección vigente
let camaraLibre = false;           // true cuando el usuario movió la cámara a mano
const rBurb = n => hay(val(n)) ? 5 + 34*M().escala(val(n)) : 0;

const zoom = d3.zoom().scaleExtent([0.35,14]).on("zoom", ev => {
  if(ev.sourceEvent) camaraLibre = true;
  T = ev.transform; k = T.k; gZoom.attr("transform", T);
  gFocos.selectAll("circle.nucleo").attr("r", 3/k);
  gFocos.selectAll("circle.onda").attr("r", d => d.r/Math.sqrt(k));
  gBurb.selectAll("circle").attr("r", d => rBurb(d)/Math.sqrt(k));
  gEtq.selectAll("text").attr("font-size", 10.5/k);
  gEtq.selectAll("tspan.v").attr("dy", 11/k);
  posarHolo();
  $("hud-zoom").innerHTML = `ZOOM <b>×${k.toFixed(1)}</b>`;
});
svg.call(zoom).on("dblclick.zoom", null);

/* Zona de la ventana que el mapa puede usar sin quedar tapado.
   `conPaneles` = false da la zona de reposo (nada abierto). */
function zonaLibre(conPaneles = true){
  const w = cont.clientWidth, h = cont.clientHeight, movil = angosta.matches;
  const hayPanel = conPaneles && !!vistaActual(), hayFranja = conPaneles && ui.franja;
  const barra = movil ? $("barra").offsetHeight : $("barra").offsetWidth;
  const franja = hayFranja ? $("franja").offsetHeight : 0;
  if(movil) return { x0:0, y0:0, x1:w, y1:h - barra - franja - (hayPanel ? Math.round(h*(hayFranja ? .46 : .58)) : 0) };
  return { x0:0, y0:0, x1:w - barra - (hayPanel ? $("panel").offsetWidth : 0), y1:h - franja };
}
// Márgenes para ver el país completo: arriba queda el nombre y abajo la leyenda
function zonaPais(conPaneles){
  const z = zonaLibre(conPaneles), movil = angosta.matches;
  const m = movil ? {i:10, s:92, d:10, b:conPaneles && vistaActual() ? 10 : 92} : {i:20, s:112, d:16, b:40};
  return { x0:z.x0+m.i, y0:z.y0+m.s, x1:Math.max(z.x0+m.i+80, z.x1-m.d), y1:Math.max(z.y0+m.s+80, z.y1-m.b) };
}
// Transformación de cámara que mete una caja del mapa dentro de una zona de la ventana
function encuadre(caja, zona, factor = 1, tope = 14){
  const [[x0,y0],[x1,y1]] = caja, zw = zona.x1-zona.x0, zh = zona.y1-zona.y0;
  const s = Math.min(tope, factor * Math.min(zw/Math.max(1,x1-x0), zh/Math.max(1,y1-y0)));
  return d3.zoomIdentity.translate((zona.x0+zona.x1)/2, (zona.y0+zona.y1)/2).scale(s).translate(-(x0+x1)/2, -(y0+y1)/2);
}
function volar(t, dur = TIEMPOS.vuelo){
  camaraLibre = false;
  svg.interrupt("camara");
  svg.transition("camara").duration(sinMovimiento ? 0 : dur).call(zoom.transform, t);
}
// Vuela al objetivo (o a los dos que se comparan); sin objetivo, al país completo
function enfocar(){
  const obj = [estado.sel, estado.cmp].filter(Boolean);
  if(!obj.length){ volar(encuadre(PAIS, zonaPais(true))); return; }
  const cajas = obj.map(n => ruta.bounds(FT[n])), z = zonaLibre(), movil = angosta.matches;
  const caja = [[d3.min(cajas, c => c[0][0]), d3.min(cajas, c => c[0][1])], [d3.max(cajas, c => c[1][0]), d3.max(cajas, c => c[1][1])]];
  const zona = movil ? {x0:z.x0+26, y0:z.y0+96, x1:z.x1-26, y1:z.y1-22} : {x0:z.x0+60, y0:z.y0+110, x1:z.x1-60, y1:z.y1-70};
  volar(encuadre(caja, zona, .82, 9));
}
// Reacomoda la cámara cuando se abre o cierra algo; respeta la cámara si el usuario la movió a mano
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
    .on("click", (ev,d) => { ev.stopPropagation(); seleccionar(d.properties.nombre, ev.shiftKey); })
    .on("pointermove", (ev,d) => tip(ev, d.properties.nombre))
    .on("pointerleave", ocultarTip);
  if(primera && !sinMovimiento){   // entrada escalonada de norte a sur, solo la primera vez
    p.style("opacity",0).transition().delay(d => 900 + (C[d.properties.nombre][1]/h)*700).duration(450).style("opacity",1)
     .on("end", function(){ d3.select(this).style("opacity",null); });
  }
  primera = false;

  const rFoco = d3.scaleSqrt().domain([0, d3.max(DATOS.municipios, m => m.robos)]).range([4,22]);
  const f = gFocos.selectAll("g").data(DATOS.municipios.map(m => ({...m, p:proy([m.lon,m.lat]), r:rFoco(m.robos)})), d => d.municipio)
    .join(en => { const g = en.append("g").attr("class","foco"); g.append("circle").attr("class","onda"); g.append("circle").attr("class","nucleo"); return g; })
    .attr("transform", d => `translate(${d.p})`)
    .on("pointermove", (ev,d) => tipFoco(ev,d)).on("pointerleave", ocultarTip)
    .on("click", (ev,d) => { ev.stopPropagation(); if(estado.sel !== d.entidad) seleccionar(d.entidad); });
  f.select(".onda").attr("r", d => d.r/Math.sqrt(k)).style("animation-delay", (d,i) => (i*0.17)+"s");
  f.select(".nucleo").attr("r", 3/k);
  pintar(); armarHolo(); candado(false);
}

/* Colores, burbujas, etiquetas y capas según el estado actual */
function pintar(){
  const burb = estado.vista === "burb";
  gEdos.selectAll("path")
    .attr("fill", d => burb ? "#13233a" : color(d.properties.nombre))
    .classed("sel", d => d.properties.nombre === estado.sel)
    .classed("cmp", d => d.properties.nombre === estado.cmp)
    .classed("lider", d => !!estado.marca && E[d.properties.nombre].vehiculo_lider === estado.marca)
    .classed("apagado", d => !!estado.marca && E[d.properties.nombre].vehiculo_lider !== estado.marca);

  gBurb.selectAll("circle").data(burb ? ordenados() : [], d => d).join(
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
  const zona = Math.floor((g[0]+180)/6)+1;   // zona UTM a partir de la longitud
  $("hud-pos").innerHTML = `LAT <b>${g[1].toFixed(4)}° N</b> · LON <b>${Math.abs(g[0]).toFixed(4)}° O</b> · UTM <b>${zona}N</b> (EPSG:326${zona})`;
});
svg.on("pointerleave", () => { miraV.attr("x1",-9).attr("x2",-9); miraH.attr("y1",-9).attr("y2",-9); miraC.attr("cx",-99); });
// Clic fuera de cualquier entidad: suelta el objetivo (revierte la secuencia)
svg.on("click", () => { if(estado.sel) seleccionar(null); });

/* ================= 4. OBJETIVO FIJADO: LA SECUENCIA =================
   a) el país se atenúa y la cámara vuela      c) la entidad se levanta como holograma
   b) el marco se cierra y pasa el escaneo     d) el expediente se despliega por bloques
   Todo termina antes de 2 segundos. */
const TIEMPOS = { vuelo:600, marco:160, escaneo:520, levantar:700, panel:820, fin:2000 };

/* Marco de objetivo: cuatro esquinas que se cierran sobre la entidad */
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
/* Línea de escaneo: recorre de arriba abajo el marco de la entidad recién fijada */
function escanear(){
  const n = estado.cmp || estado.sel;
  if(!n || sinMovimiento) return;
  const [[x0,y0],[x1,y1]] = ruta.bounds(FT[n]), m = 6, alto = Math.max(8, (y1-y0)*.45);
  gBarre.interrupt().attr("x", x0-m).attr("width", x1-x0+2*m).attr("height", alto).attr("y", y0-m-alto).style("opacity",1)
    .transition().duration(380).ease(d3.easeQuadIn).attr("y", y1+m-alto)
    .transition().duration(140).style("opacity",0);
}

/* Holograma de la entidad: una copia del polígono que se separa del mapa.
   `holo.t` va de 0 (pegada al mapa) a 1 (levantada). */
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
// Coloca cuerpo y sombra según la altura actual; los desplazamientos son fijos en píxeles de pantalla
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

let relojes = [];                          // temporizadores de la secuencia en curso
const luego = (ms, f) => relojes.push(setTimeout(f, sinMovimiento ? 0 : ms));
function cancelarSecuencia(){ relojes.forEach(clearTimeout); relojes = []; }

function secuencia(){
  cancelarSecuencia();
  const panel = $("panel"), estabaAbierto = panel.classList.contains("abierto");
  app.classList.toggle("hay-objetivo", !!estado.sel);        // a) atenuar el resto del país…
  enfocar();                                                 //    …y volar

  if(!estado.sel){                                           // reversa: todo regresa a su sitio
    candado(false); gBarre.interrupt().style("opacity",0);
    levantar(0, 220).then(() => { if(!estado.sel) armarHolo(); });
    pintarPanel();
    return;
  }
  holo.t = 0; armarHolo();
  gCand.interrupt().attr("d", null); gCandB.interrupt().attr("d", null);
  luego(TIEMPOS.marco, () => candado(true));                 // b) marco de objetivo…
  luego(TIEMPOS.escaneo, escanear);                          //    …y línea de escaneo
  luego(TIEMPOS.levantar, () => levantar(1, 420));           // c) la entidad se levanta
  // d) expediente: si el panel ya estaba abierto cambia de contenido y espera su turno;
  //    si estaba cerrado, entra deslizándose cuando la entidad ya se levantó.
  if(sinMovimiento || estabaAbierto){
    panel.style.setProperty("--retraso", sinMovimiento ? "0ms" : (TIEMPOS.panel - 60) + "ms");
    pintarPanel();
  } else {
    panel.style.setProperty("--retraso", "120ms");
    luego(TIEMPOS.panel, () => pintarPanel());
  }
  luego(TIEMPOS.fin + 150, () => panel.style.setProperty("--retraso", "0ms"));
}

/* Fija, compara o suelta. `comoSegunda` = Mayús + clic; `dePatrulla` evita detener la patrulla. */
function seleccionar(n, comoSegunda, dePatrulla){
  if(!dePatrulla) pararPatrulla();
  if((comoSegunda || estado.eligeCmp) && n && estado.sel && n !== estado.sel){ estado.cmp = n; }
  else { estado.sel = (n === estado.sel && !estado.cmp) ? null : n; estado.cmp = null; }
  estado.eligeCmp = false;
  if(estado.sel) ui.panel = null;          // el expediente reemplaza a la herramienta que estuviera abierta
  refrescar(); secuencia();
}

/* ================= 5. TOOLTIPS Y CIFRAS ANIMADAS ================= */
function miniSerie(n){
  const v = ANIOS.map(a => E[n].robos[a]), mx = d3.max(v.filter(hay)) || 1, bw = 210/v.length;
  return `<svg viewBox="0 0 210 34" aria-hidden="true">` + v.map((x,i) => !hay(x) ? "" :
    `<rect x="${i*bw+2}" y="${32-28*x/mx}" width="${bw-4}" height="${Math.max(1,28*x/mx)}" fill="${ANIOS[i]===estado.anio?"#62d3e8":"#2a4a66"}"/>`).join("") + `</svg>`;
}
function tip(ev, n){
  const e = E[n], lugar = lugarDe(n, estado.anio);
  mostrarTip(ev, `<strong>${n.toUpperCase()}</strong>
    <span class="num">${con(e.robos[estado.anio], fmt)} robos en ${estado.anio}${lugar ? " · lugar "+lugar : ""}</span><br>
    <small class="num">${con(e.pct_violencia, fmt2)} % con violencia · ${con(e.pct_recuperacion, fmt2)} % recup. (${ULT})</small>
    ${miniSerie(n)}<small>${PRI}–${ULT} · más robado: ${con(e.vehiculo_lider, x => x)}</small>`);
}
function tipFoco(ev, m){
  mostrarTip(ev, `<strong>${m.municipio.toUpperCase()}</strong>${m.entidad}<br>
    <span class="num">${con(m.robos, fmt)} robos en ${ULT}</span><br><small class="num">${con(m.pct_violencia, fmt1)} % con violencia · ubicación referencial</small>`);
}
function mostrarTip(ev, html){
  const t = $("tip"), [x,y] = d3.pointer(ev, cont), z = zonaLibre();
  t.innerHTML = html; t.style.display = "block";
  t.style.left = Math.max(0, Math.min(x, z.x1-250))+"px";
  t.style.top = Math.max(0, Math.min(y, z.y1-150))+"px";
}
function ocultarTip(){ $("tip").style.display = "none"; }

/* Cifras con conteo animado: cada una recuerda su valor anterior por `id` */
const previo = new Map();
function cifra(id, v, dec=0, suf=""){
  if(!hay(v)) return SIN;
  return `<span data-id="${id}" data-v="${v}" data-d="${dec}" data-s="${suf}">${num(v,dec)}${suf}</span>`;
}
function num(v, dec){ return Number(v).toLocaleString("es-MX", {minimumFractionDigits:dec, maximumFractionDigits:dec}); }
function animarCifras(){
  document.querySelectorAll("[data-id]").forEach(el => {
    const id = el.dataset.id, a = +el.dataset.v, dec = +el.dataset.d, suf = el.dataset.s, de = previo.get(id) ?? 0;
    previo.set(id, a);
    if(sinMovimiento || de === a) return;
    const it = d3.interpolateNumber(de, a), t0 = performance.now();
    (function paso(t){ const u = Math.min(1,(t-t0)/650), s = 1-Math.pow(1-u,3);
      el.textContent = num(it(s), dec) + suf; if(u<1) requestAnimationFrame(paso); })(t0);
  });
}

/* ================= 6. PIEZAS DE LOS EXPEDIENTES ================= */
/* Barras por año. Con `valoresB` dibuja dos series lado a lado (comparación). */
function serie(valores, anioSel, valoresB){
  const W=300, H=96, todos = (valoresB ? valores.concat(valoresB) : valores).filter(hay), mx = d3.max(todos) || 1, bw = W/valores.length;
  let s = `<svg class="serie" viewBox="0 0 ${W} ${H}" role="img" aria-label="Robos por año de ${PRI} a ${ULT}"><line x1="0" x2="${W}" y1="${H-16.5}" y2="${H-16.5}" stroke="#1c2a3b"/>`;
  valores.forEach((v,i) => {
    const a = ANIOS[i], on = a === anioSel, x = i*bw+6, an = valoresB ? (bw-14)/2 : bw-12, h = hay(v) ? Math.max(2,(H-34)*v/mx) : 0;
    if(hay(v)) s += `<rect x="${x}" y="${H-17-h}" width="${an}" height="${h}" fill="${on?"#62d3e8":(valoresB?"#2f7f93":"#24405a")}" style="animation-delay:${i*45}ms"/>`;
    if(valoresB){ const vb = valoresB[i], hb = hay(vb) ? Math.max(2,(H-34)*vb/mx) : 0;
      if(hay(vb)) s += `<rect x="${x+an+2}" y="${H-17-hb}" width="${an}" height="${hb}" fill="${on?"#ffb224":"#8a6420"}" style="animation-delay:${i*45+20}ms"/>`; }
    else s += `<text x="${x+an/2}" y="${H-21-h}" text-anchor="middle" ${on?'style="fill:#d9e4ef"':""}>${hay(v) ? fmt(v) : "s/d"}</text>`;
    s += `<text x="${i*bw+bw/2}" y="${H-4}" text-anchor="middle" ${on?'style="fill:#62d3e8"':""}>${a}</text>`;
  });
  return s + "</svg>";
}
// Medidor de media luna; la marca blanca es la referencia nacional
function reloj(pct, ref, col, rotulo){
  if(!hay(pct)) return `<div class="reloj"><svg viewBox="0 0 120 76" role="img" aria-label="${rotulo}: sin dato">
    <path class="pista" d="M14 62A46 46 0 0 1 106 62"/><text x="60" y="60" style="font-size:13px">sin dato</text></svg><div class="nota">${rotulo}</div></div>`;
  const p = Math.min(100, pct);
  let marca = "";
  if(hay(ref)){ const ang = Math.PI*(1-ref/100);
    marca = `<line class="ref" x1="${60+46*Math.cos(ang)}" y1="${62-46*Math.sin(ang)}" x2="${60+56*Math.cos(ang)}" y2="${62-56*Math.sin(ang)}"/>`; }
  return `<div class="reloj"><svg viewBox="0 0 120 76" role="img" aria-label="${rotulo}: ${fmt2(pct)} por ciento">
    <path class="pista" d="M14 62A46 46 0 0 1 106 62" />
    <path class="arco" data-p="${p}" d="M14 62A46 46 0 0 1 106 62" pathLength="100" stroke="${col}" stroke-dasharray="0 100"/>
    ${marca}<text x="60" y="60">${fmt1(pct)} %</text></svg><div class="nota">${rotulo}</div></div>`;
}
// Los arcos se llenan cuando su sección está a la vista
function animarRelojes(){
  requestAnimationFrame(() => requestAnimationFrame(() =>
    document.querySelectorAll(".seccion:not([hidden]) .reloj .arco").forEach(a => a.setAttribute("stroke-dasharray", `${a.dataset.p} 100`))));
}

/* Secciones plegables: una fila de botones y un bloque por sección; solo una abierta a la vez.
   `grupo` dice qué expediente es (ent, nac, cmp) para recordar cuál sección dejó abierta el usuario. */
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
  const b = ev.target.closest(".pest");
  if(b) abrirSeccion(b.parentElement.dataset.grupo, b.dataset.k);
});

/* Tipo de vehículo para elegir la silueta. Primero el campo "tipo" de la lista nacional de submarcas;
   si la submarca no está ahí, solo se deduce cuando el nombre lo dice sin ambigüedad. */
function tipoDe(nombre){
  if(!hay(nombre)) return { clave:"neutra", texto:"tipo no disponible", origen:"" };
  const s = DATOS.submarcas.find(x => x.submarca === nombre);
  if(s && hay(s.tipo)) return { clave:Siluetas.clave(s.tipo), texto:s.tipo, origen:"" };
  const d = Siluetas.porNombre(nombre);
  if(d) return { clave:d.clave, texto:d.texto, origen:"deducido del nombre; no figura en la lista nacional de submarcas" };
  return { clave:"neutra", texto:"tipo no disponible", origen:"no figura en la lista nacional de submarcas" };
}
// Holograma pequeño con porcentaje: una pieza de la composición de la entidad
function pod(rotulo, v, claves, col){
  return `<div class="pod" style="--c:${col}"><div class="pod-holo">${claves.map(c => Siluetas.plana(c)).join("")}</div>
    <b class="num">${con(v, x => fmt1(x)+" %")}</b><span class="nota">${rotulo}</span>
    <i class="pod-barra"><u style="transform:scaleX(${hay(v) ? Math.min(1, v/100) : 0})"></u></i></div>`;
}

/* ---------- expediente de una entidad ---------- */
function entEsencial(n, a){
  const e = E[n], lugar = lugarDe(n,a), v = variacion(e.robos[a], e.robos[a-1]);
  return `<div class="gran num">${cifra("g-ent", e.robos[a])}</div>
    <div class="esencial"><span>robos en <b>${a}</b></span>
      <span>${lugar ? `lugar <b class="num">${lugar}</b> de ${NOMBRES.length}` : `lugar ${SIN}`}</span>
      ${v === null ? (hay(e.robos[a-1]) || a === PRI ? (a === PRI ? "<span>primer año de la serie</span>" : "") : `<span>variación ${SIN}</span>`) : txtVariacion(v, a)}</div>`;
}
function entSerie(n, a){
  const e = E[n], parte = hay(e.robos[a]) && hay(NAC.robos[a]) && NAC.robos[a] ? e.robos[a]/NAC.robos[a]*100 : null;
  return `${serie(ANIOS.map(y => e.robos[y]), a)}
    <div class="fila"><span>Parte del total nacional en ${a}</span><span class="num">${con(parte, x => fmt1(x)+" %")}</span></div>`;
}
function htmlEntidad(n, a){
  const e = E[n], t = tipoDe(e.vehiculo_lider), munis = DATOS.municipios.filter(m => m.entidad === n);
  const perfil = `
    <div class="relojes">${reloj(e.pct_violencia, NAC.pct_violencia_2025, hay(e.pct_violencia) ? rampaCalor(METRICAS.viol.escala(e.pct_violencia)) : "#62d3e8", `Con violencia ${ULT}`)}
      ${reloj(e.pct_recuperacion, NAC.pct_recuperacion_2025, "#62d3e8", `Recuperación ${ULT}`)}</div>
    <div class="fila"><span>Unidades recuperadas ${ULT}</span><span class="num">${con(e.recuperados, fmt)}</span></div>
    <p class="nota">Marca blanca: valor nacional (${con(NAC.pct_violencia_2025, fmt1)} % y ${con(NAC.pct_recuperacion_2025, fmt1)} %).${hay(e.pct_recuperacion) && e.pct_recuperacion>100 ? ` Recuperación real ${fmt2(e.pct_recuperacion)} %: incluye unidades robadas en otra entidad.` : ""}</p>`;
  const vehiculos = `
    ${Siluetas.vitrina(t.clave)}
    <div class="veh-ficha"><div class="eti">Vehículo más robado</div>
      <div class="veh">${con(e.vehiculo_lider, x => x)}</div>
      <div class="fila"><span>Tipo</span><span>${t.clave === "neutra" && t.texto === "tipo no disponible" ? `<span class="sd">tipo no disponible</span>` : t.texto}</span></div>
      <p class="nota">AMIS vía prensa, marzo de 2026${t.origen ? " · " + t.origen : ""}. Silueta genérica.</p></div>
    <div><div class="eti">Qué se roban · ${ULT}</div>
      <div class="trio">${pod("Automóviles", e.pct_autos, ["sedan"], "var(--hielo)")}
        ${pod("Equipo pesado y pick up", e.pct_pesado_pickup, ["tracto","pickup"], "var(--ambar)")}
        ${pod("Motocicletas", e.pct_motos, ["moto"], "var(--rojo)")}</div></div>`;
  const focos = munis.length
    ? `<p class="nota">Municipios de la entidad entre los ${DATOS.municipios.length} con más robos del país en ${ULT}.</p>` +
      munis.map(m => `<div class="fila"><span>${m.municipio}</span><span class="num">${con(m.robos, fmt)} · ${con(m.pct_violencia, fmt1)} % viol.</span></div>`).join("")
    : `<p class="nota">${SIN} municipal: ninguno de sus municipios está entre los ${DATOS.municipios.length} con más robos del país en ${ULT}, que son los únicos cargados.</p>`;
  return `
    <div class="exp-cab"><div class="eti">Objetivo fijado</div>
      <div class="cab"><h3>${n.toUpperCase()}</h3><button type="button" class="mini" id="b-cmp">Comparar</button></div>
      <div id="ent-esencial">${entEsencial(n,a)}</div></div>
    ${secciones("ent", [
      {k:"serie", rot:"Serie", html:`<div id="ent-serie">${entSerie(n,a)}</div>`},
      {k:"perfil", rot:"Perfil", html:perfil},
      {k:"vehiculos", rot:"Vehículos", html:vehiculos},
      {k:"municipios", rot:"Municipios", html:focos}])}`;
}

/* ---------- comparación de dos entidades ---------- */
function filaVs(rot, va, vb, f){
  const mx = Math.max(hay(va) ? va : 0, hay(vb) ? vb : 0) || 1;
  return `<span class="a num">${con(va, f)}</span><span class="m">${rot}</span><span class="b num">${con(vb, f)}</span>
    <span class="ba"><i style="width:${hay(va) ? va/mx*100 : 0}%"></i></span><span></span><span class="bb"><i style="width:${hay(vb) ? vb/mx*100 : 0}%"></i></span>`;
}
function cmpSerie(A, B, a){
  const ea = E[A], eb = E[B];
  return `${serie(ANIOS.map(y => ea.robos[y]), a, ANIOS.map(y => eb.robos[y]))}
    <div class="vs">${filaVs(`Robos ${a}`, ea.robos[a], eb.robos[a], fmt)}${filaVs(`Lugar ${a}`, lugarDe(A,a), lugarDe(B,a), v => v+"°")}</div>
    <p class="nota">Las barras comparan solo estas dos entidades entre sí. En «Lugar», menor es más robos.</p>`;
}
function htmlComparacion(A, B, a){
  const ea = E[A], eb = E[B], p2 = v => fmt2(v)+" %", p1 = v => fmt1(v)+" %";
  const ficha = (e, col) => { const t = tipoDe(e.vehiculo_lider);
    return `<div class="pod" style="--c:${col}"><div class="pod-holo">${Siluetas.plana(t.clave)}</div>
      <div class="veh">${con(e.vehiculo_lider, x => x)}</div><span class="nota">${t.texto}</span></div>`; };
  return `
    <div class="exp-cab"><div class="eti" id="cmp-eti">Comparación · ${a}</div>
      <h3><span style="color:var(--hielo)">${A.toUpperCase()}</span><br><span style="color:var(--ambar)">${B.toUpperCase()}</span></h3></div>
    ${secciones("cmp", [
      {k:"serie", rot:"Serie", html:`<div id="cmp-serie">${cmpSerie(A,B,a)}</div>`},
      {k:"perfil", rot:"Perfil", html:`<div class="vs">${filaVs(`Violencia ${ULT}`, ea.pct_violencia, eb.pct_violencia, p2)}
        ${filaVs(`Recuperación ${ULT}`, ea.pct_recuperacion, eb.pct_recuperacion, p2)}
        ${filaVs(`Recuperados ${ULT}`, ea.recuperados, eb.recuperados, fmt)}</div>`},
      {k:"vehiculos", rot:"Vehículos", html:`<div class="duo">${ficha(ea,"var(--hielo)")}${ficha(eb,"var(--ambar)")}</div>
        <p class="nota">Vehículo más robado: AMIS vía prensa, marzo de 2026. Siluetas genéricas por tipo.</p>
        <div class="vs">${filaVs("Automóviles", ea.pct_autos, eb.pct_autos, p1)}
        ${filaVs("Pesado y pick up", ea.pct_pesado_pickup, eb.pct_pesado_pickup, p1)}
        ${filaVs("Motocicletas", ea.pct_motos, eb.pct_motos, p1)}</div>`}])}`;
}

/* El expediente se construye una vez por objetivo. Al cambiar solo el año se actualizan
   las cifras que dependen de él, para no reiniciar el holograma ni las animaciones. */
let expClave = null;
function expediente(){
  const el = $("exp"), a = estado.anio;
  if(!estado.sel){ expClave = null; return; }       // se conserva el contenido mientras el panel sale
  const clave = estado.sel + "|" + (estado.cmp ?? "");
  if(clave !== expClave){
    expClave = clave; el.classList.remove("quieto");
    el.innerHTML = estado.cmp ? htmlComparacion(estado.sel, estado.cmp, a) : htmlEntidad(estado.sel, a);
    const b = $("b-cmp"); if(b) b.onclick = () => { estado.eligeCmp = !estado.eligeCmp; aviso(); };
  } else {
    el.classList.add("quieto");
    if(estado.cmp){ $("cmp-eti").textContent = `Comparación · ${a}`; $("cmp-serie").innerHTML = cmpSerie(estado.sel, estado.cmp, a); }
    else { $("ent-esencial").innerHTML = entEsencial(estado.sel, a); $("ent-serie").innerHTML = entSerie(estado.sel, a); }
  }
  animarRelojes();
}

/* ---------- panorama nacional (se abre con la cifra nacional) ---------- */
function nacEsencial(a){
  return `<div class="gran num">${cifra("g-nac", NAC.robos[a])}</div>
    <div class="esencial"><span>vehículos asegurados robados en <b>${a}</b></span>
    ${a === PRI ? "<span>primer año de la serie</span>" : txtVariacion(variacion(NAC.robos[a], NAC.robos[a-1]), a)}</div>`;
}
function nacSerie(a){
  const t = NAC.robos[a], rec = NAC.recuperados[a], dias = (a%4===0) ? 366 : 365;
  return `${serie(ANIOS.map(y => NAC.robos[y]), a)}
    <div class="kpis">
      <div class="kpi"><span class="eti">Por día · ${a}</span><b class="num">${cifra("k-dia", hay(t) ? Math.round(t/dias) : null)}</b><small>promedio calculado</small></div>
      <div class="kpi"><span class="eti">Recuperados ${a}</span><b class="num">${cifra("k-rec", rec)}</b><small class="num">${hay(rec) && hay(t) && t ? fmt1(rec/t*100)+" % del robo" : SIN}</small></div>
    </div>`;
}
let nacHecho = false;
function nacional(){
  const el = $("nac"), a = estado.anio;
  if(!nacHecho){
    nacHecho = true;
    const tp = NAC.tipos_2025 ?? [], col = ["var(--hielo)","var(--ambar)","var(--rojo)","#8a6cff"];
    el.innerHTML = `
      <div class="exp-cab"><div class="eti">Sin objetivo fijado</div><h3>REPÚBLICA MEXICANA</h3><div id="nac-esencial"></div></div>
      ${secciones("nac", [
        {k:"serie", rot:"Serie", html:`<div id="nac-serie"></div>`},
        {k:"perfil", rot:"Perfil", html:`<div class="relojes">${reloj(NAC.pct_violencia_2025, NAC.pct_violencia_2025, "#ff4130", `Con violencia ${ULT}`)}
            ${reloj(NAC.pct_recuperacion_2025, NAC.pct_recuperacion_2025, "#62d3e8", `Recuperación ${ULT}`)}</div>
          <div class="fila"><span>Robos con violencia ${ULT}</span><span class="num">${con(NAC.violencia_2025, fmt)} unidades</span></div>`},
        {k:"vehiculos", rot:"Vehículos", html:`<div class="eti">Tipo de vehículo · ${ULT}</div><div class="tipos">` +
          (tp.length ? tp.map((d,i) => `<div class="fila" style="--c:${col[i % col.length]}"><span>${Siluetas.plana(Siluetas.clave(d.tipo))}${d.tipo}</span>
            <span class="num">${con(d.robos, fmt)} · recup. ${con(d.pct_recuperacion, x => x+" %")}</span></div>`).join("") : `<p class="nota">${SIN}</p>`) +
          `</div><p class="nota">Siluetas genéricas por tipo.</p>`}])}`;
  }
  el.classList.toggle("quieto", el.dataset.anio !== undefined);
  el.dataset.anio = a;
  $("nac-esencial").innerHTML = nacEsencial(a);
  $("nac-serie").innerHTML = nacSerie(a);
}
// La cifra que queda sobre el mapa en reposo
function cifraNacional(){
  $("cifra-eti").textContent = `Robos ${estado.anio} · nacional`;
  $("cifra-val").innerHTML = cifra("k-rob", NAC.robos[estado.anio]);
}

/* ================= 7. HERRAMIENTAS ================= */
/* ---------- ranking (con reacomodo animado) ---------- */
function ranking(){
  const m = M(), filas = ordenados().map(n => ({n, v:val(n)})), tope = orden(filas[0].v) > 0 ? filas[0].v : 1;
  const ol = d3.select("#rank"), antes = new Map();
  ol.selectAll("li").each(function(d){ antes.set(d.n, this.offsetTop); });
  const li = ol.selectAll("li").data(filas, d => d.n)
    .join(en => { const l = en.append("li"); l.append("button").attr("type","button"); return l; }).order();
  li.select("button")
    .attr("aria-current", d => d.n === estado.sel ? "true" : null)
    .classed("cmp", d => d.n === estado.cmp)
    .html((d,i) => `<i class="num">${String(i+1).padStart(2,"0")}</i><span>${d.n}</span><span class="num">${con(d.v, m.texto)}</span>
      <u style="width:calc(100% - 38px);transform:scaleX(${hay(d.v) ? Math.max(0, Math.min(1,d.v/tope)) : 0});background:${hay(d.v) ? m.rampa(m.escala(d.v)) : SIN_COLOR}"></u>`)
    .on("click", (ev,d) => seleccionar(d.n, ev.shiftKey));
  if(!sinMovimiento && vistaActual() === "ranking") li.each(function(d){
    const dy = (antes.get(d.n) ?? this.offsetTop) - this.offsetTop;
    if(dy) this.animate([{transform:`translateY(${dy}px)`},{transform:"none"}], {duration:480, easing:"cubic-bezier(.2,.8,.2,1)"});
  });
}

/* ---------- submarcas: al elegir una se resaltan las entidades donde es la más robada ---------- */
function modelos(){
  const tope = d3.max(DATOS.submarcas, s => s.robos) || 1;
  $("modelos").innerHTML = DATOS.submarcas.map((s,i) => `
    <button type="button" class="mod" id="mod-${i}" data-s="${s.submarca}" aria-pressed="${estado.marca===s.submarca}">
      <i class="num">${String(i+1).padStart(2,"0")}</i>${Siluetas.plana(Siluetas.clave(s.tipo))}
      <span>${s.submarca} <small>${con(s.tipo, x => x)} · viol. ${con(s.pct_violencia, x => fmt1(x)+" %")}</small></span>
      <span class="num">${con(s.robos, fmt)}</span><u style="transform:scaleX(${hay(s.robos) ? s.robos/tope : 0});animation-delay:${i*40}ms"></u></button>`).join("");
  document.querySelectorAll(".mod").forEach(b => b.onclick = () => ponerMarca(estado.marca === b.dataset.s ? null : b.dataset.s));
  ponerMarca(estado.marca);
}
function ponerMarca(s){
  estado.marca = s;
  document.querySelectorAll(".mod").forEach(x => x.setAttribute("aria-pressed", x.dataset.s === s));
  const n = s ? NOMBRES.filter(x => E[x].vehiculo_lider === s) : [];
  $("marca-msj").textContent = !s ? `Las ${DATOS.submarcas.length} submarcas más robadas del país en ${ULT}. Elige una para ver en qué entidades es la más robada.`
    : n.length ? `${s}: la más robada en ${n.length} ${n.length===1?"entidad":"entidades"} (${n.join(", ")}). AMIS vía prensa.`
    : `${s}: no es la más robada en ninguna entidad según la lista disponible (AMIS vía prensa).`;
  // Aviso en la leyenda, para poder quitar el resaltado aunque el panel esté cerrado
  const chip = $("chip-marca");
  chip.hidden = !s;
  if(s) chip.textContent = `◇ ${s} · ${n.length} ${n.length===1?"entidad":"entidades"} ✕`;
  if(s) chip.setAttribute("aria-label", `Quitar el resaltado de ${s}`);
  pintar();
}
$("chip-marca").onclick = () => ponerMarca(null);

/* ---------- cinta de datos ---------- */
function cinta(){
  const t = DATOS.municipios.map(m => `<b>${m.municipio.toUpperCase()}</b> ${con(m.robos, fmt)} robos · <em>${con(m.pct_violencia, fmt1)} % viol.</em>`)
    .concat(DATOS.submarcas.map(s => `<b>${s.submarca.toUpperCase()}</b> ${con(s.robos, fmt)} uds.`)).join("  ◆  ") + "  ◆  ";
  $("cinta").innerHTML = t + t;   // duplicado para que el desplazamiento sea continuo
}

/* ---------- leyenda y aviso ---------- */
function leyenda(){
  const m = M();
  $("ley-tit").textContent = m.titulo + (estado.metrica === "robos" ? " · " + estado.anio : "");
  $("ley-rampa").style.background = `linear-gradient(90deg,${d3.range(0,1.01,.1).map(t => m.rampa(t)).join(",")})`;
  $("ley-min").textContent = m.min; $("ley-max").textContent = m.max;
  $("ley-focos").innerHTML = `<span class="rojo">◉</span> ${DATOS.municipios.length} municipios con más robos en ${ULT}`;
  $("ley-focos").hidden = !estado.capas.focos;
}
function aviso(){
  const a = $("aviso");
  if(estado.eligeCmp){ a.hidden = false; a.textContent = "Elige la segunda entidad · Esc cancela"; }
  else if(patrulla.id){ a.hidden = false; a.textContent = `Patrulla · ${patrulla.i+1} de ${patrulla.ruta.length} · P detiene`; }
  else a.hidden = true;
}

/* ---------- buscador ---------- */
const sinAcento = s => s.normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase().trim();
function coincidencias(q){
  if(!q) return [];
  const ent = NOMBRES.filter(n => sinAcento(n).includes(q)).map(n => ({destino:n, rot:n, det:"entidad", peso:sinAcento(n).startsWith(q) ? 0 : 1}));
  const mun = DATOS.municipios.filter(m => sinAcento(m.municipio+", "+m.entidad).includes(q))
    .map(m => ({destino:m.entidad, rot:m.municipio, det:`${m.entidad} · ${con(m.robos, fmt)} robos en ${ULT}`, mun:true, peso:sinAcento(m.municipio).startsWith(q) ? 0 : 1}));
  return ent.concat(mun).sort((a,b) => a.peso - b.peso).slice(0, 12);
}
function listarBusqueda(){
  const q = sinAcento($("buscar").value), r = coincidencias(q);
  $("buscar-msj").textContent = q && !r.length ? `Sin coincidencia. Solo hay entidades y los ${DATOS.municipios.length} municipios cargados.` : "";
  $("buscar-res").innerHTML = r.map((x,i) => `<li><button type="button" data-i="${i}" class="${i===0?"primero":""}"><span>${x.rot}</span><small>${x.det}</small></button></li>`).join("");
  $("buscar-res").querySelectorAll("button").forEach(b => b.onclick = () => irA(r[+b.dataset.i]));
  return r;
}
function irA(x){
  if(!x) return;
  if(x.mun) ui.secc.ent = "municipios";      // si se buscó un municipio, el expediente abre en sus focos
  estado.sel = null; estado.cmp = null; seleccionar(x.destino);
}
$("buscar").addEventListener("input", listarBusqueda);
$("buscar").addEventListener("keydown", ev => { if(ev.key === "Enter") irA(listarBusqueda()[0]); });

/* ---------- patrulla automática: recorre las primeras del ranking vigente ---------- */
const patrulla = { id:null, i:0, n:8, ruta:[] };
function pintarPatrulla(){
  const enMarcha = !!patrulla.id, lista = enMarcha ? patrulla.ruta : ordenados().slice(0, patrulla.n);
  $("patrulla-txt").textContent = `Recorre sola las ${lista.length} primeras entidades del ranking vigente y fija cada una durante unos segundos.`;
  $("patrulla").setAttribute("aria-pressed", enMarcha);
  $("patrulla-rot").textContent = enMarcha ? "❚❚ Detener patrulla" : "▶ Iniciar patrulla";
  $("h-patrulla").classList.toggle("activa", enMarcha);
  $("patrulla-ruta").innerHTML = lista.map((n,i) => `<li class="${enMarcha && i===patrulla.i ? "va" : ""}"><span class="num">${String(i+1).padStart(2,"0")}</span><span>${n}</span><span class="num">${con(val(n), M().texto)}</span></li>`).join("");
}
function pararPatrulla(){
  if(!patrulla.id) return;
  clearInterval(patrulla.id); patrulla.id = null; pintarPatrulla();
}
function alternarPatrulla(){
  if(patrulla.id){ pararPatrulla(); aviso(); return; }
  patrulla.ruta = ordenados().slice(0, patrulla.n); patrulla.i = 0;
  const paso = () => { estado.sel = null; estado.cmp = null; seleccionar(patrulla.ruta[patrulla.i], false, true); };
  patrulla.id = setInterval(() => { patrulla.i = (patrulla.i+1) % patrulla.ruta.length; paso(); }, 4500);
  paso();
}
$("patrulla").onclick = alternarPatrulla;

/* ================= 8. PANEL ÚNICO Y LÍNEA DE TIEMPO ================= */
const TITULOS = { indicador:"Indicador y vista", ranking:"Ranking de entidades", submarcas:"Submarcas más robadas", capas:"Capas",
  buscar:"Buscador", patrulla:"Patrulla automática", fuentes:"Fuentes y metodología", nacional:"Panorama nacional", expediente:"Expediente" };
/* Qué muestra el panel: la herramienta abierta o, si no hay, el expediente del objetivo fijado. */
function vistaActual(){ return ui.panel ?? (estado.sel ? "expediente" : null); }
function pintarPanel(){
  const v = vistaActual(), panel = $("panel");
  if(v){   // al cerrar se deja el contenido como estaba, para que no se vacíe mientras sale
    panel.querySelectorAll("[data-vista]").forEach(s => s.hidden = s.dataset.vista !== v);
    $("panel-tit").textContent = v === "expediente" && estado.cmp ? "Comparación" : TITULOS[v];
    $("panel-cerrar").setAttribute("aria-label", v === "expediente" ? "Soltar el objetivo" : "Cerrar el panel");
  }
  panel.classList.toggle("abierto", !!v); panel.inert = !v;
  app.classList.toggle("con-panel", !!v);
  document.querySelectorAll(".hta[data-panel]").forEach(b => b.setAttribute("aria-expanded", b.dataset.panel === ui.panel));
  $("cifra-nac").setAttribute("aria-expanded", ui.panel === "nacional");
  if(v) animarRelojes();
}
/* Abre una herramienta (o la cierra si ya estaba abierta). Abrir otra reemplaza la anterior. */
function abrirPanel(nombre, boton){
  cancelarSecuencia();
  ui.panel = ui.panel === nombre ? null : nombre;
  ui.origen = boton ?? null;
  $("panel").style.setProperty("--retraso", "0ms");
  if(ui.panel === "ranking") ranking();
  pintarPanel(); acomodarCamara();
  if(ui.panel === "buscar"){ $("buscar").value = ""; listarBusqueda(); $("buscar").focus({preventScroll:true}); }
  else if(ui.panel) $("panel").focus({preventScroll:true});
}
/* Cierra lo que muestre el panel: una herramienta (y regresa el expediente si hay objetivo) o el objetivo. */
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

/* ---------- línea de tiempo: franja inferior que puede convivir con el panel ---------- */
function armarLineaTiempo(){
  const r = $("anio"), mx = d3.max(ANIOS, a => NAC.robos[a]) || 1, pos = i => `calc(${ANIOS.length > 1 ? i/(ANIOS.length-1)*100 : 50}%)`;
  r.min = PRI; r.max = ULT; r.value = estado.anio;
  $("anio-barras").innerHTML = ANIOS.map((a,i) => `<i data-a="${a}" style="left:${pos(i)};height:${hay(NAC.robos[a]) ? Math.max(3, 26*NAC.robos[a]/mx) : 0}px" title="${a}"></i>`).join("");
  $("anio-marcas").innerHTML = ANIOS.map((a,i) => `<span data-a="${a}" style="left:${pos(i)}">${a}</span>`).join("");
  $("anio-barras").querySelectorAll("i").forEach(b => b.onclick = () => { detener(); ponerAnio(+b.dataset.a); });
}
function lineaTiempo(){
  $("anio-val").textContent = estado.anio; $("anio").value = estado.anio;
  document.querySelectorAll("#anio-barras i, #anio-marcas span").forEach(x => x.classList.toggle("va", +x.dataset.a === estado.anio));
  const solo = estado.metrica !== "robos";
  $("anio").disabled = solo; $("play").disabled = solo;
  const nota = solo ? `Este indicador solo está cargado para ${ULT}.` : `Serie anual ${PRI}–${ULT} disponible para robos. Las barras son el total nacional.`;
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

/* ---------- refresco general ---------- */
function refrescar(){
  pintar(); armarHolo(); ranking(); cifraNacional(); nacional(); expediente();
  leyenda(); aviso(); lineaTiempo(); pintarPatrulla(); animarCifras();
}

/* ================= 9. CONTROLES Y ATAJOS ================= */
function ponerMetrica(m){
  estado.metrica = m;
  document.querySelectorAll("#seg-metrica button").forEach(x => x.setAttribute("aria-pressed", x.dataset.m === m));
  if(m !== "robos"){ detener(); estado.anio = ULT; }
  refrescar();
}
function ponerVista(v){
  estado.vista = v;
  document.querySelectorAll("#seg-vista button").forEach(x => x.setAttribute("aria-pressed", x.dataset.v === v));
  pintar(); armarHolo();
}
document.querySelectorAll("#seg-metrica button").forEach(b => b.onclick = () => ponerMetrica(b.dataset.m));
document.querySelectorAll("#seg-vista button").forEach(b => b.onclick = () => ponerVista(b.dataset.v));
document.querySelectorAll("#capas button").forEach(b => b.onclick = () => {
  estado.capas[b.dataset.c] = !estado.capas[b.dataset.c]; b.setAttribute("aria-pressed", estado.capas[b.dataset.c]); pintar(); leyenda();
});
function ponerAnio(a){ if(estado.metrica !== "robos") return; estado.anio = Math.max(PRI, Math.min(ULT, a)); refrescar(); }
$("anio").addEventListener("input", ev => { detener(); ponerAnio(+ev.target.value); });
let cine = null;
function detener(){ if(cine){ clearInterval(cine); cine = null; $("play").textContent = "▶"; $("play").setAttribute("aria-label","Reproducir la serie"); } }
function reproducir(){
  if(cine){ detener(); return; }
  if(estado.metrica !== "robos") return;
  $("play").textContent = "❚❚"; $("play").setAttribute("aria-label","Pausar la reproducción");
  if(estado.anio === ULT) estado.anio = PRI-1;
  cine = setInterval(() => { estado.anio++; refrescar(); if(estado.anio >= ULT) detener(); }, 1200);
}
$("play").onclick = reproducir;
$("z-mas").onclick = () => svg.transition().duration(250).call(zoom.scaleBy, 1.6);
$("z-menos").onclick = () => svg.transition().duration(250).call(zoom.scaleBy, 1/1.6);
$("z-rst").onclick = () => { camaraLibre = false; if(estado.sel) seleccionar(null); else enfocar(); };
function pantallaCompleta(){
  if(document.fullscreenElement){ document.exitFullscreen(); return; }
  const raiz = document.documentElement;     // toda la app, para conservar barra y paneles
  if(raiz.requestFullscreen) raiz.requestFullscreen().catch(() => {});
}
$("z-full").onclick = pantallaCompleta;

/* Atajos de teclado. Esc deshace por capas: comparación pendiente → panel → objetivo → patrulla → línea de tiempo. */
document.addEventListener("keydown", ev => {
  if(ev.ctrlKey || ev.metaKey || ev.altKey) return;
  const t = ev.key.toLowerCase(), enCampo = ev.target.matches("input, textarea");
  if(t === "escape"){
    if(enCampo) ev.target.blur();
    if(estado.eligeCmp){ estado.eligeCmp = false; aviso(); }
    else if(ui.panel) cerrarPanel();
    else if(estado.sel) seleccionar(null);
    else if(patrulla.id){ pararPatrulla(); aviso(); }
    else if(ui.franja){ alternarFranja(false); $("h-tiempo").focus({preventScroll:true}); }
    return;
  }
  if(enCampo) return;
  if(t === "arrowright"){ detener(); ponerAnio(estado.anio+1); }
  else if(t === "arrowleft"){ detener(); ponerAnio(estado.anio-1); }
  else if(t === " " && !ev.target.matches("button")){ ev.preventDefault(); reproducir(); }
  else if(t === "1") ponerMetrica("robos");
  else if(t === "2") ponerMetrica("viol");
  else if(t === "3") ponerMetrica("recu");
  else if(t === "v") ponerVista(estado.vista === "coro" ? "burb" : "coro");
  else if(t === "p"){ alternarPatrulla(); aviso(); }
  else if(t === "f") pantallaCompleta();
  else if(t === "c" && estado.sel && !estado.cmp){ estado.eligeCmp = !estado.eligeCmp; aviso(); }
});

/* ---------- primera pintura y cambios de tamaño ---------- */
armarLineaTiempo(); modelos(); cinta(); dibujar(); refrescar(); pintarPanel();
let ancho0 = cont.clientWidth, alto0 = cont.clientHeight;
new ResizeObserver(() => {
  if(cont.clientWidth === ancho0 && cont.clientHeight === alto0) return;
  ancho0 = cont.clientWidth; alto0 = cont.clientHeight;
  svg.interrupt("camara"); svg.call(zoom.transform, d3.zoomIdentity); camaraLibre = false;
  dibujar(); enfocar();
}).observe(cont);
}

iniciar().catch(err => {
  // Si la API no responde se dice qué falló y cómo arreglarlo; no se muestra un mapa vacío.
  const caja = $("arranque"), copia = caja.cloneNode(true);
  caja.replaceWith(copia);                              // quita el "clic para omitir" y el cierre automático
  copia.classList.remove("fuera"); copia.style.cursor = "default";
  copia.querySelector("#arr-log").textContent = `NO SE PUDO CARGAR\n${err.message}\n\nEjecuta  python scripts\\construir_datos.py\ny vuelve a iniciar el servidor.`;
  copia.querySelector("#arr-nota").textContent = "Sin conexión con la API";
  console.error(err);
});

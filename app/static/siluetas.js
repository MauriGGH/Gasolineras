/* Ojo de Dios · Gasolineras MX — siluetas de vehículos, bombas y pipas.
   Dibujos GENÉRICOS por tipo, en líneas (malla de alambre). No representan ningún
   modelo real ni llevan logotipos: la marca y la submarca solo aparecen como texto.
   Aquí no hay cifras; este archivo solo sabe dibujar. */
"use strict";

const Siluetas = (() => {
  // Lienzo común de todos los dibujos: 240 × 110, con el piso en y = 96.
  const ANCHO = 240, ALTO = 110;

  // Una rueda es un círculo escrito como trayecto, para poder "trazarla" igual que las demás líneas.
  const circulo = (cx, cy, r) => `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0`;

  /* Cada tipo tiene:
       cuerpo     contorno lateral
       lineas     detalles interiores (ventanas, puertas, bastidor)
       ruedas     [cx, cy, radio]
       fondo      media anchura del vehículo, para separar sus dos costados en la vitrina
       cuadernas  secciones transversales [x, yArriba, yAbajo, mediaAnchura opcional];
                  unen los dos costados y dan el aspecto de malla al girar */
  const TIPOS = {
    sedan: {
      nombre: "Automóvil sedán", fondo: 32,
      cuerpo: "M22 84L22 64Q23 57 30 56L54 53L80 35Q84 32 92 32L126 32Q134 32 140 37L160 52L204 59Q216 61 218 68L220 80L220 84L196 84A18 18 0 0 0 160 84L82 84A18 18 0 0 0 46 84Z",
      lineas: ["M60 53L82 37L106 36L106 53Z", "M112 36L128 36Q133 36 138 40L152 53L112 53Z",
               "M109 53L109 82", "M154 54L158 82", "M30 61L204 64", "M84 78L158 78"],
      ruedas: [[64, 81, 14], [178, 81, 14]],
      cuadernas: [[24, 58, 84], [54, 53, 84], [80, 35, 84], [127, 32, 84], [160, 52, 84], [205, 59, 84], [219, 68, 84]],
    },
    pickup: {
      nombre: "Pick up", fondo: 34,
      cuerpo: "M16 84L16 58L20 54L96 54L98 34Q99 30 104 30L140 30Q146 30 150 34L166 52L210 57Q220 59 222 66L224 80L224 84L202 84A20 20 0 0 0 162 84L82 84A20 20 0 0 0 42 84Z",
      lineas: ["M104 36L138 36Q142 36 145 39L156 52L104 52Z", "M96 54L96 84", "M100 52L100 82",
               "M154 53L158 82", "M20 62L94 62", "M22 54L22 84"],
      ruedas: [[62, 80, 16], [182, 80, 16]],
      cuadernas: [[18, 56, 84], [58, 54, 84], [96, 54, 84], [99, 32, 84], [148, 31, 84], [166, 52, 84], [210, 57, 84], [223, 66, 84]],
    },
    // Comercial ligero: cabina adelantada sobre bastidor y caja de redilas separada de la cabina.
    comercial: {
      nombre: "Comercial ligero", fondo: 34,
      cuerpo: "M18 66L18 36L146 36L146 66L150 66L150 34Q150 30 155 30L186 30Q192 30 196 35L205 54L217 58Q222 60 222 66L222 84L194 84A18 18 0 0 0 158 84L78 84A18 18 0 0 0 42 84L26 84L26 72L18 72Z",
      lineas: ["M156 36L184 36Q189 36 191 40L198 53L156 53Z", "M34 36V66M50 36V66M66 36V66M82 36V66",
               "M98 36V66M114 36V66M130 36V66", "M18 46H146", "M18 56H146", "M154 53V80", "M201 55L203 80", "M26 72H150"],
      ruedas: [[60, 82, 14], [176, 82, 14]],
      cuadernas: [[18, 36, 72], [60, 36, 72], [103, 36, 72], [146, 36, 72], [151, 32, 84], [194, 33, 84], [205, 54, 84], [221, 62, 84]],
    },
    tracto: {
      nombre: "Tractocamión", fondo: 36,
      cuerpo: "M30 70L30 62L118 62L118 22Q118 18 122 18L156 18Q161 18 163 22L170 44L206 50Q212 51 213 57L214 84L202 84A20 20 0 0 0 162 84L136 84L136 70Z",
      lineas: ["M140 24L156 24L162 42L140 42Z", "M58 62L62 56L96 56L100 62", "M126 18V5", "M136 20V70",
               "M139 45V68", "M170 44V70", "M209 54V78", "M140 73H158V82H140Z"],
      ruedas: [[64, 80, 16], [100, 80, 16], [182, 80, 16]],
      cuadernas: [[31, 62, 70], [75, 62, 70], [118, 20, 70], [137, 18, 84], [162, 20, 84], [170, 44, 84], [206, 50, 84], [213, 58, 84]],
    },
    // Semirremolque genérico: volumen de carga sobre bastidor. No distingue caja seca, tanque ni plataforma.
    semi: {
      nombre: "Semirremolque", fondo: 36,
      cuerpo: "M14 14L226 14L226 66L14 66Z",
      lineas: ["M56 14V66M98 14V66", "M141 14V66M184 14V66", "M28 66L28 73L102 73L102 66", "M170 66V92",
               "M163 92H177", "M204 66V73", "M14 66L14 76L22 76"],
      ruedas: [[48, 82, 14], [82, 82, 14]],
      cuadernas: [[14, 14, 66], [56, 14, 66], [98, 14, 66], [141, 14, 66], [184, 14, 66], [226, 14, 66]],
    },
    moto: {
      nombre: "Motocicleta", fondo: 3,
      cuerpo: "M84 44Q102 32 126 37L142 45Q128 53 106 53L72 51L58 45Q70 41 84 44Z",
      lineas: ["M150 30L188 74", "M140 26L160 31", "M150 30L145 21", "M142 45L120 74L86 74L72 51", "M120 74L106 53",
               "M86 74L52 74", "M58 45Q40 45 33 60", "M170 55Q188 47 206 58", "M94 57H118V72H94Z", "M104 76L62 82",
               circulo(163, 34, 5)],
      ruedas: [[52, 74, 20], [188, 74, 20]],
      cuadernas: [[150, 26, 27, 22], [52, 73, 75, 7], [188, 73, 75, 7], [86, 45, 51, 9], [106, 57, 72, 10]],
    },
    // Bomba despachadora genérica: cuerpo, pantalla, manguera y pistola. Sin logotipos.
    bomba: {
      nombre: "Bomba despachadora", fondo: 20,
      cuerpo: "M92 92L92 20Q92 14 98 14L142 14Q148 14 148 20L148 92Z",
      lineas: ["M100 24H140V44H100Z", "M104 52H116M124 52H136", "M100 60H140", "M100 68H140", "M84 92H156V96H84Z",
               "M148 34Q172 34 172 54L172 78Q172 86 164 86", "M160 80L168 76L176 82L170 90Z", "M88 14H152"],
      ruedas: [],
      cuadernas: [[92, 14, 92, 20], [120, 14, 92, 20], [148, 14, 92, 20]],
    },
    // Pipa: tractocamión con tanque cilíndrico. No distingue capacidad ni producto.
    pipa: {
      nombre: "Pipa de combustible", fondo: 34,
      cuerpo: "M14 62L14 30Q14 22 24 22L150 22Q160 22 160 30L160 62Q160 70 150 70L24 70Q14 70 14 62Z",
      lineas: ["M166 84L166 34Q166 30 170 30L196 30Q202 30 205 36L214 52L222 56Q226 58 226 64L226 84", "M172 36H196L206 52H172Z",
               "M18 76H226", "M56 22V70M104 22V70", "M80 18H96V22", "M160 46H166"],
      ruedas: [[40, 84, 12], [70, 84, 12], [196, 84, 12]],
      cuadernas: [[14, 30, 62], [56, 22, 70], [104, 22, 70], [150, 22, 70], [166, 32, 84], [226, 60, 84]],
    },
    // Silueta neutra: se usa cuando los datos no dicen de qué tipo es el vehículo.
    neutra: {
      nombre: "Tipo no disponible", fondo: 30,
      cuerpo: "M30 84L30 50Q30 40 42 40L198 40Q210 40 210 50L210 84L190 84A18 18 0 0 0 154 84L86 84A18 18 0 0 0 50 84Z",
      lineas: ["M108 56Q108 47 120 47Q132 47 132 56Q132 62 120 65L120 70", "M120 75L120 77"],
      ruedas: [[68, 82, 14], [172, 82, 14]],
      cuadernas: [[30, 46, 84], [80, 40, 84], [120, 40, 84], [160, 40, 84], [210, 46, 84]],
    },
  };

  const sinAcento = s => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

  // Palabras de tipo que pueden aparecer en el campo "tipo" de los datos.
  const POR_PALABRA = [
    ["semirremolque", "semi"], ["tractocamion", "tracto"], ["equipo pesado", "tracto"], ["motocicleta", "moto"],
    ["pick up", "pickup"], ["pickup", "pickup"], ["comercial", "comercial"], ["automovil", "sedan"],
    ["sedan", "sedan"], ["bomba", "bomba"], ["pipa", "pipa"], ["moto", "moto"], ["tracto", "tracto"],
  ];

  /* Silueta que corresponde a un texto de tipo tal como viene en los datos
     ("Automóvil", "Pick up", "Comercial"…). Si no se reconoce, la neutra. */
  function clave(tipo) {
    const t = sinAcento(tipo ?? "");
    const par = POR_PALABRA.find(([palabra]) => t.startsWith(palabra));
    return par ? par[1] : "neutra";
  }

  /* Deduce el tipo a partir del NOMBRE del vehículo, solo si el nombre lo dice de forma
     inequívoca (contiene la palabra del tipo, como "Semirremolque tanque").
     Nunca se deduce a partir de la marca o del modelo. Devuelve null si no se puede. */
  function porNombre(nombre) {
    const n = sinAcento(nombre ?? "");
    const reglas = [["semirremolque", "semi", "Semirremolque"], ["tractocamion", "tracto", "Tractocamión"],
                    ["motocicleta", "moto", "Motocicleta"], ["pick up", "pickup", "Pick up"]];
    const r = reglas.find(([palabra]) => n.includes(palabra));
    return r ? { clave: r[1], texto: r[2] } : null;
  }

  // Todas las líneas de un tipo, en el orden en que se trazan.
  function trazos(k) {
    const t = TIPOS[k] ?? TIPOS.neutra;
    return [t.cuerpo, ...t.lineas, ...t.ruedas.flatMap(([x, y, r]) => [circulo(x, y, r), circulo(x, y, r * 0.42)])];
  }

  // Trayectos SVG con su turno (--i) para la animación de trazado. pathLength="1" permite animar cualquier largo.
  const trayectos = k => trazos(k).map((d, i) => `<path d="${d}" pathLength="1" style="--i:${Math.min(i, 16)}"/>`).join("");

  /* Silueta plana y pequeña: renglones de submarcas, composición y comparación. */
  function plana(k, clase = "") {
    return `<svg class="sil ${clase}" viewBox="0 0 ${ANCHO} ${ALTO}" aria-hidden="true" focusable="false">${trayectos(k)}</svg>`;
  }

  /* Vitrina holográfica: los dos costados del vehículo separados en profundidad y unidos por
     cuadernas, sobre una base circular. Gira con transformaciones CSS; no hay motor 3D. */
  function vitrina(k) {
    const t = TIPOS[k] ?? TIPOS.neutra;
    const cara = (clase, z) => `<svg class="vit-cara ${clase}" style="--z:${z}px" viewBox="0 0 ${ANCHO} ${ALTO}">${trayectos(k)}</svg>`;
    const cuadernas = t.cuadernas.map(([x, y0, y1, medio], i) => {
      const m = medio ?? t.fondo;
      return `<i class="vit-cuad" style="left:${x - m}px;top:${y0}px;width:${2 * m}px;height:${Math.max(1, y1 - y0)}px;--i:${i}"></i>`;
    }).join("");
    return `<div class="vitrina" role="img" aria-label="Holograma genérico: ${t.nombre}">
      <div class="vit-escena">
        <div class="vit-base"><i></i><i></i></div>
        <div class="vit-giro">${cara("lejos", -t.fondo)}${cuadernas}${cara("cerca", t.fondo)}</div>
      </div>
      <div class="vit-barrido"></div>
    </div>`;
  }

  return { clave, porNombre, plana, vitrina, nombre: k => (TIPOS[k] ?? TIPOS.neutra).nombre };
})();

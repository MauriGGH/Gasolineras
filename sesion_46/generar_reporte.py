"""Arma el reporte técnico PDF de la Sesión 46 a partir de clima_sucursales.csv.

Formato tomado del reporte de la Sesión 44: portada con logos, encabezado, secciones
numeradas, conclusiones y referencias.
"""
import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

F = "/usr/share/fonts/truetype/liberation/"
for nombre, arch in (("Serif", "LiberationSerif-Regular"), ("Serif-B", "LiberationSerif-Bold"),
                     ("Serif-I", "LiberationSerif-Italic"), ("Mono", "LiberationMono-Regular")):
    pdfmetrics.registerFont(TTFont(nombre, F + arch + ".ttf"))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-B", italic="Serif-I", boldItalic="Serif-B")

PORTADA = {
    "titulo": "Fusión de datos espaciales y temporales en tiempo real",
    "subtitulo": "Laboratorio con GeoPandas y Open-Meteo<br/>y su uso en la app de gasolineras",
    "materia": "Ingeniería de Datos",
    "profesor": "Armando Roman Gallardo Heredia",
    "alumno": "Mauricio Gerardo Gómez Hernández (23460330)",
    "sesion": "Sesión 46",
    "entrega": "19 de noviembre de 2026",
    "lugar": "Villa de Álvarez, Colima a 19 de noviembre de 2026.",
}
SALIDA = "Sesion_46_Gomez_Mauricio.pdf"
NEGRO = colors.HexColor("#111111")

df = pd.read_csv("clima_sucursales.csv")
ok = df[df["error"].isna()]
estados = gpd.read_file("../datos/crudos/estados_mx.geojson").to_crs(4326)

# Figura 1: mapa
fig, ax = plt.subplots(figsize=(6.4, 3.7), dpi=200)
estados.plot(ax=ax, color="#eef0f2", edgecolor="#b9bec4", linewidth=0.4)
pts = gpd.GeoDataFrame(ok, geometry=gpd.points_from_xy(ok.lon, ok.lat), crs=4326)
pts.plot(ax=ax, column="temperature_2m", cmap="YlOrRd", markersize=45, edgecolor="#333",
         linewidth=0.5, legend=True, legend_kwds={"label": "Temperatura actual (°C)", "shrink": 0.75})
for _, r in ok.iterrows():
    ax.annotate(r["id"], (r.lon, r.lat), xytext=(4, 3), textcoords="offset points", fontsize=5.5)
ax.set_xlim(-118.5, -86); ax.set_ylim(14, 33.5); ax.set_axis_off()
fig.tight_layout(); fig.savefig("mapa_clima.png")

# Estilos
cuerpo = ParagraphStyle("c", fontName="Serif", fontSize=10.5, leading=13.6, spaceAfter=6,
                        alignment=4, textColor=NEGRO)
h1 = ParagraphStyle("h1", parent=cuerpo, fontName="Serif-B", fontSize=14.5, leading=18,
                    spaceBefore=10, spaceAfter=6, alignment=0)
pie = ParagraphStyle("pie", parent=cuerpo, fontSize=9.2, leading=11.5, alignment=4)
viñeta = ParagraphStyle("v", parent=cuerpo, leftIndent=18, bulletIndent=4, spaceAfter=3)
cen = ParagraphStyle("cen", parent=cuerpo, alignment=1, spaceAfter=3)
tit = ParagraphStyle("tit", parent=cen, fontName="Serif-B", fontSize=22, leading=27, spaceAfter=10)
sub = ParagraphStyle("sub", parent=cen, fontSize=13.5, leading=18)
cel = ParagraphStyle("cel", parent=cuerpo, fontSize=9, leading=11, spaceAfter=0, alignment=0)
mono = lambda t: f"<font face='Mono' size='9'>{t}</font>"

def encabezado(canvas, doc):
    canvas.saveState()
    canvas.setFont("Serif", 10.5)
    canvas.drawString(2.4 * cm, letter[1] - 1.5 * cm, PORTADA["materia"])
    canvas.drawRightString(letter[0] - 2.4 * cm, letter[1] - 1.5 * cm, "Tarea - " + PORTADA["sesion"])
    canvas.setLineWidth(0.4)
    canvas.line(2.4 * cm, letter[1] - 1.7 * cm, letter[0] - 2.4 * cm, letter[1] - 1.7 * cm)
    canvas.drawCentredString(letter[0] / 2, 1.3 * cm, str(doc.page - 1))
    canvas.restoreState()

def logos(canvas, doc):
    canvas.saveState()
    y = letter[1] - 4.6 * cm
    canvas.drawImage("assets/logos_sep_tecnm.png", 2.6 * cm, y, width=10.2 * cm, height=10.2 * cm * 90 / 370, mask="auto")
    canvas.drawImage("assets/logo_colima.png", 13.4 * cm, y - 0.9 * cm, width=3.1 * cm, height=3.1 * cm, mask="auto")
    canvas.setFont("Serif", 11)
    canvas.drawCentredString(letter[0] / 2, 3.6 * cm, "TECNM COLIMA")
    canvas.drawCentredString(letter[0] / 2, 3.0 * cm, PORTADA["lugar"])
    canvas.restoreState()

def tabla(datos, anchos):
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Serif-B"), ("FONTNAME", (0, 1), (-1, -1), "Serif"),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("LINEABOVE", (0, 0), (-1, 0), 0.8, NEGRO),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, NEGRO), ("LINEBELOW", (0, -1), (-1, -1), 0.8, NEGRO),
        ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
    ]))
    return t

def etiqueta(k, v):
    return Paragraph(f"<b>{k}:</b> {v}", cen)

hoja = [Spacer(1, 6.2 * cm), Paragraph(PORTADA["titulo"], tit), Paragraph(PORTADA["subtitulo"], sub),
        Spacer(1, 2.4 * cm), etiqueta("Materia", PORTADA["materia"]), etiqueta("Profesor", PORTADA["profesor"]),
        Paragraph("<b>Alumno:</b>", cen), Paragraph(PORTADA["alumno"], cen), etiqueta("Sesión", PORTADA["sesion"]),
        Spacer(1, 1 * cm), etiqueta("Fecha de entrega", PORTADA["entrega"]), PageBreak()]

mx, mn = ok.loc[ok.temperature_2m.idxmax()], ok.loc[ok.temperature_2m.idxmin()]
corto = lambda r: r.nombre.replace("Sucursal ", "")
lluvia = ok[ok.precipitation > 0]
txt_lluvia = (", ".join(f"{corto(r)} ({r.precipitation} mm)" for r in lluvia.itertuples()) if len(lluvia) else "ninguna")
consulta = ok["consultado_utc"].iloc[0]

hoja += [
    Paragraph("1&nbsp;&nbsp;&nbsp;Qué hace el pipeline", h1),
    Paragraph("Tomé una capa de puntos con sucursales y le agregué a cada una la temperatura y la precipitación "
              "actuales que reporta Open-Meteo. La salida es una tabla donde cada sucursal conserva su identificador "
              "junto con el clima del momento de la consulta. Es el paso que une las dos sesiones previas, "
              "los datos espaciales y los que cambian con el tiempo. Para el proyecto de "
              "la app de gasolineras (repositorio https://github.com/MauriGGH/Gasolineras), sirve como evidencia del cruce "
              "y del linaje de los datos.", cuerpo),
    Paragraph(f"La capa {mono('sucursales.geojson')} tiene {len(df)} puntos en EPSG:4326, con los campos {mono('id')} y "
              f"{mono('nombre')}. Son sucursales de práctica en ciudades de México, entre ellas Colima y Manzanillo. "
              "No son estaciones reales de la app. El mismo script acepta la capa de estaciones del repositorio si se "
              f"le pasa la columna identificadora, por ejemplo {mono('--id permiso')}.", cuerpo),
    Paragraph("2&nbsp;&nbsp;&nbsp;Método", h1),
    Paragraph(f"Cargo la capa con GeoPandas y recorro cada registro con {mono('iterrows')}. De la geometría saco la "
              f"latitud ({mono('geometry.y')}) y la longitud ({mono('geometry.x')}) y hago un GET a "
              f"{mono('api.open-meteo.com/v1/forecast')} con {mono('current=temperature_2m,precipitation')}. Con las "
              "respuestas armo un DataFrame que guarda el id, el nombre, las coordenadas y los valores devueltos.", cuerpo),
    Paragraph("Al código de la guía le agregué cuatro cosas:", cuerpo),
    Paragraph(f"un timeout de 15 segundos y {mono('raise_for_status')}, para no leer respuestas con error;", viñeta, bulletText="•"),
    Paragraph("hasta tres reintentos con espera creciente cuando falla la red;", viñeta, bulletText="•"),
    Paragraph(f"una columna {mono('error')}, para que un punto fallido quede anotado sin detener el lote;", viñeta, bulletText="•"),
    Paragraph("reproyección a EPSG:4326 antes de leer las coordenadas, porque la API espera grados.", viñeta, bulletText="•"),
    Spacer(1, 4),
    Preformatted(
        "def obtener_clima(lat, lon, sesion=None, reintentos=3):\n"
        "    for intento in range(1, reintentos + 1):\n"
        "        try:\n"
        "            res = (sesion or requests).get(URL, timeout=15, params={\n"
        "                \"latitude\": lat, \"longitude\": lon,\n"
        "                \"current\": \"temperature_2m,precipitation\"})\n"
        "            res.raise_for_status()\n"
        "            return res.json()[\"current\"]\n"
        "        except (requests.RequestException, KeyError, ValueError):\n"
        "            if intento == reintentos:\n"
        "                raise\n"
        "            time.sleep(2 ** intento)", ParagraphStyle("code", fontName="Mono", fontSize=7.8, leading=9.6,
                                                              leftIndent=14, textColor=NEGRO)),
    Spacer(1, 4),
    Paragraph("3&nbsp;&nbsp;&nbsp;Resultados", h1),
    Paragraph(f"Las {len(ok)} de {len(df)} consultas respondieron bien el {consulta}. La sucursal más cálida fue "
              f"{corto(mx)} con {mx.temperature_2m} °C y la más fría {corto(mn)} con {mn.temperature_2m} °C. "
              f"Con precipitación mayor a cero: {txt_lluvia}. La Tabla 1 es la salida completa del pipeline y la Figura 1 "
              "la ubica sobre el mapa de estados.", cuerpo),
]
filas = [["id", "Sucursal", "Lat", "Lon", "Temp. (°C)", "Precip. (mm)", "Hora del dato (GMT)"]]
for r in ok.itertuples():
    filas.append([r.id, corto(r), f"{r.lat:.4f}", f"{r.lon:.4f}", f"{r.temperature_2m:.1f}",
                  f"{r.precipitation:.1f}", r.hora_clima.replace("T", " ")])
hoja += [KeepTogether([tabla(filas, [1.1*cm, 3.9*cm, 2*cm, 2.4*cm, 2*cm, 2.3*cm, 3.5*cm]), Spacer(1, 3),
                       Paragraph("Tabla 1: Clima actual por sucursal, salida de pipeline_clima.py.", pie)]),
         Spacer(1, 8),
         KeepTogether([Image("mapa_clima.png", width=12.5 * cm, height=12.5 * cm * 3.7 / 6.4),
                       Paragraph("Figura 1: Sucursales sobre los estados de México, coloreadas por temperatura actual.", pie)]),
         Paragraph("4&nbsp;&nbsp;&nbsp;Linaje de datos", h1)]
lin = [["Elemento", "Detalle"],
       ["Capa espacial", "sucursales.geojson, propia, 14 puntos en EPSG:4326. Llave: id."],
       ["Fuente temporal", "Open-Meteo, endpoint /v1/forecast, bloque current."],
       ["Variables", "temperature_2m (°C) y precipitation (mm)."],
       ["Cruce", "Una consulta por punto con su latitud y longitud. El id viaja en la fila de salida."],
       ["Frescura", "Open-Meteo actualiza el bloque current cada 15 minutos (interval = 900 s). La hora del dato "
                    "viene en GMT y la hora de consulta se guarda en UTC en la columna consultado_utc."],
       ["Salida", "clima_sucursales.csv, con una fila por sucursal."],
       ["Límite", "El valor viene de un modelo en malla, no de una estación en la sucursal."]]
lin = [[Paragraph(c, cel) for c in f] for f in lin]
lin[0] = [Paragraph(f"<b>{c.text}</b>", cel) for c in lin[0]]
hoja += [tabla(lin, [3 * cm, 14.2 * cm]), Spacer(1, 6),
         Paragraph("5&nbsp;&nbsp;&nbsp;Conclusiones", h1),
         Paragraph("1. El cruce se hace por coordenada: cada punto de la capa pide su propio clima, y el identificador "
                   "que se conserva en la fila es lo que permite volver a unir el resultado con la capa original.", cuerpo),
         Paragraph("2. Un registro de clima es una foto de un instante. Sin la hora de consulta no se puede saber qué "
                   "tan viejo es el dato, y por eso la guardé junto con la hora que reporta la API.", cuerpo),
         Paragraph("3. Una petición por punto basta para 14 sucursales, pero con las miles de estaciones de la app "
                   "sería lenta. Open-Meteo acepta varias coordenadas separadas por comas en una sola petición "
                   "(lo comprobé con dos puntos), así que el siguiente paso sería consultar por lotes.", cuerpo),
         Paragraph("Referencias", h1),
         Paragraph("Open-Meteo. Weather Forecast API, parámetro current, open-meteo.com/en/docs.", pie),
         Paragraph("GeoPandas Documentation: GeoDataFrame y GeoSeries, geopandas.org.", pie),
         Paragraph("IETF (2016). RFC 7946: The GeoJSON Format. datatracker.ietf.org.", pie),
         Paragraph("INEGI. Marco Geoestadístico, límites de entidades federativas (capa de estados usada en la Figura 1).", pie)]

SimpleDocTemplate(SALIDA, pagesize=letter, leftMargin=2.4*cm, rightMargin=2.4*cm, topMargin=2.3*cm,
                  bottomMargin=2*cm, title=f"{PORTADA['sesion']}: {PORTADA['titulo']}",
                  author="Mauricio Gerardo Gómez Hernández").build(hoja, onFirstPage=logos, onLaterPages=encabezado)
print("ok", SALIDA)

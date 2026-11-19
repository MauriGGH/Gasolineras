"""Arma el reporte técnico PDF de la Sesión 46 a partir de clima_sucursales.csv."""
import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

# Datos de la portada: ajustar cuando llegue el PDF de ejemplo.
PORTADA = {
    "institucion": "Institución",
    "programa": "Programa académico",
    "materia": "Materia",
    "sesion": "Sesión 46",
    "titulo": "Laboratorio: fusión de datos espaciales y temporales en tiempo real (GeoPandas + Open-Meteo)",
    "alumno": "Apellido Nombre",
    "equipo": "Proyecto: Gasolineras",
    "fecha": "19 de noviembre de 2026",
}
SALIDA = "Sesion_46_Apellido_Nombre.pdf"

df = pd.read_csv("clima_sucursales.csv")
ok = df[df["error"].isna()]
estados = gpd.read_file("../datos/crudos/estados_mx.geojson").to_crs(4326)

# Mapa
fig, ax = plt.subplots(figsize=(5.6, 3.6), dpi=200)
estados.plot(ax=ax, color="#eef0f2", edgecolor="#b9bec4", linewidth=0.4)
pts = gpd.GeoDataFrame(ok, geometry=gpd.points_from_xy(ok.lon, ok.lat), crs=4326)
pts.plot(ax=ax, column="temperature_2m", cmap="YlOrRd", markersize=45,
         edgecolor="#333", linewidth=0.5, legend=True,
         legend_kwds={"label": "Temperatura actual (°C)", "shrink": 0.75})
for _, r in ok.iterrows():
    ax.annotate(r["id"], (r.lon, r.lat), xytext=(4, 3), textcoords="offset points", fontsize=5.5)
ax.set_xlim(-118.5, -86); ax.set_ylim(14, 33.5)
ax.set_axis_off()
fig.tight_layout()
fig.savefig("mapa_clima.png")

# Estilos
ss = getSampleStyleSheet()
cuerpo = ParagraphStyle("c", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.6,
                        leading=13.2, spaceAfter=5)
h = ParagraphStyle("h", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
                   spaceBefore=7, spaceAfter=3, textColor=colors.HexColor("#1f3a5f"))
pie = ParagraphStyle("p", parent=cuerpo, fontSize=8, leading=10, textColor=colors.HexColor("#555"))
cp = ParagraphStyle("cp", parent=cuerpo, alignment=1, fontSize=12, leading=17)
ct = ParagraphStyle("ct", parent=cp, fontName="Helvetica-Bold", fontSize=17, leading=23,
                    textColor=colors.HexColor("#1f3a5f"))

def tabla(datos, anchos, fs=8):
    t = Table(datos, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), fs), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dfe7f1")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9aa5b1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t

hoja = []
# Portada
hoja += [Spacer(1, 2.2 * cm), Paragraph(PORTADA["institucion"], cp),
         Paragraph(PORTADA["programa"], cp), Paragraph(PORTADA["materia"], cp),
         Spacer(1, 2.2 * cm), Paragraph(PORTADA["sesion"], cp),
         Paragraph(PORTADA["titulo"], ct), Spacer(1, 2.2 * cm),
         Paragraph(PORTADA["alumno"], cp), Paragraph(PORTADA["equipo"], cp),
         Spacer(1, 1 * cm), Paragraph(PORTADA["fecha"], cp), PageBreak()]

mx, mn = ok.loc[ok.temperature_2m.idxmax()], ok.loc[ok.temperature_2m.idxmin()]
lluvia = ok[ok.precipitation > 0]
consulta = ok["consultado_utc"].iloc[0]
txt_lluvia = (", ".join(f"{r.nombre.replace('Sucursal ', '')} ({r.precipitation} mm)" for r in lluvia.itertuples())
              if len(lluvia) else "ninguna")

hoja += [
    Paragraph("Objetivo", h),
    Paragraph("Construí un pipeline en Python que toma una capa de puntos con sucursales y "
              "le agrega a cada una la temperatura y la precipitación actuales que reporta Open-Meteo. "
              "El resultado es una tabla donde cada sucursal conserva su identificador junto con el clima "
              "del momento de la consulta. Esta ejecución queda como evidencia del cruce de datos para el "
              "proyecto final.", cuerpo),
    Paragraph("Datos de entrada", h),
    Paragraph(f"La capa <font face='Courier'>sucursales.geojson</font> tiene {len(df)} puntos en ciudades de México, "
              "en EPSG:4326, con los campos <font face='Courier'>id</font> y <font face='Courier'>nombre</font>. "
              "Son sucursales ilustrativas que armé para la práctica y no corresponden a estaciones reales del "
              "proyecto Gasolineras. El mismo script acepta la capa <font face='Courier'>estaciones.geojson</font> "
              "del proyecto si se le indica la columna identificadora con <font face='Courier'>--id permiso</font>.", cuerpo),
    Paragraph("Método", h),
    Paragraph("Cargo la capa con GeoPandas y recorro cada registro con <font face='Courier'>iterrows</font>, "
              "tomando <font face='Courier'>geometry.y</font> como latitud y <font face='Courier'>geometry.x</font> "
              "como longitud. Con esas coordenadas hago un GET a <font face='Courier'>api.open-meteo.com/v1/forecast</font> "
              "con <font face='Courier'>current=temperature_2m,precipitation</font> y armo un DataFrame con "
              "el identificador, el nombre, las coordenadas y los valores devueltos.", cuerpo),
    Paragraph("Sobre el código de la guía agregué cuatro cosas: un timeout de 15 segundos, "
              "<font face='Courier'>raise_for_status</font> para no leer respuestas con error, hasta tres reintentos "
              "con espera creciente, y una columna <font face='Courier'>error</font> para que un punto fallido "
              "quede anotado sin detener el lote. También reproyecto a EPSG:4326 antes de leer las coordenadas, "
              "porque la API espera grados.", cuerpo),
    Paragraph("Resultados", h),
    Paragraph(f"Las {len(ok)} de {len(df)} consultas respondieron bien el {consulta}. La más cálida fue "
              f"{mx.nombre.replace('Sucursal ', '')} con {mx.temperature_2m} °C y la más fría "
              f"{mn.nombre.replace('Sucursal ', '')} con {mn.temperature_2m} °C. Con precipitación mayor a cero: {txt_lluvia}.", cuerpo),
]
filas = [["id", "Sucursal", "Lat", "Lon", "Temp. (°C)", "Precip. (mm)", "Hora del dato (GMT)"]]
for r in ok.itertuples():
    filas.append([r.id, r.nombre.replace("Sucursal ", ""), f"{r.lat:.4f}", f"{r.lon:.4f}",
                  f"{r.temperature_2m:.1f}", f"{r.precipitation:.1f}", r.hora_clima.replace("T", " ")])
hoja += [tabla(filas, [1.1*cm, 4.2*cm, 2*cm, 2.3*cm, 2*cm, 2.2*cm, 3.7*cm]), Spacer(1, 3),
         Paragraph("Tabla 1. Clima actual por sucursal (salida de pipeline_clima.py).", pie),
         Image("mapa_clima.png", width=11 * cm, height=11 * cm * 3.6 / 5.6), 
         Paragraph("Figura 1. Sucursales sobre el mapa de estados, coloreadas por temperatura.", pie),
         Paragraph("Linaje de datos", h)]
lin = [["Elemento", "Detalle"],
       ["Capa espacial", "sucursales.geojson (propia, 12 puntos, EPSG:4326). Llave: id."],
       ["Fuente temporal", "Open-Meteo, endpoint /v1/forecast, bloque current."],
       ["Variables", "temperature_2m (°C) y precipitation (mm)."],
       ["Cruce", "Una consulta por punto con su latitud y longitud. El id viaja en la fila de salida."],
       ["Frescura", "Open-Meteo actualiza el bloque current cada 15 minutos (interval = 900 s). "
                    "La hora del dato va en GMT y la de consulta se guarda en UTC."],
       ["Salida", "clima_sucursales.csv y esta tabla."],
       ["Límite", "El valor viene de un modelo en malla y no de una estación en la sucursal."]]
lin = [[Paragraph(c, ParagraphStyle("t", parent=cuerpo, fontSize=8, leading=10, spaceAfter=0)) for c in f] for f in lin]
t = tabla(lin, [3 * cm, 14.5 * cm]); hoja.append(t)

SimpleDocTemplate(SALIDA, pagesize=letter, leftMargin=2*cm, rightMargin=2*cm,
                  topMargin=1.6*cm, bottomMargin=1.5*cm,
                  title=PORTADA["sesion"], author=PORTADA["alumno"]).build(hoja)
print("ok", SALIDA)

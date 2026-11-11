# Imagen de la aplicación "Ojo de Dios · Gasolineras MX"
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Primero dependencias: esta capa se reutiliza mientras no cambie requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Genera los JSON del mapa en la construcción, para que la imagen arranque aunque no haya red.
# Intenta bajar los datos del día (rama `datos`); si no puede, usa los de ejemplo con aviso DEMO.
# Si una validación falla, la construcción falla aquí.
RUN python scripts/construir_datos.py

EXPOSE 8000
# Al arrancar vuelve a construir los datos para tomar el corte más reciente; si falla, se queda con los de la imagen.
CMD ["sh", "-c", "python scripts/construir_datos.py || echo 'Aviso: se usan los datos de la imagen'; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

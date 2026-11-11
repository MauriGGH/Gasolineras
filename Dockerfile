# Imagen de la aplicación "Ojo de Dios · Robo vehicular MX"
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Primero dependencias: esta capa se reutiliza mientras no cambie requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Valida los CSV contra los totales nacionales y genera los JSON.
# Si las sumas no cuadran, la construcción de la imagen falla aquí.
RUN python scripts/construir_datos.py

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

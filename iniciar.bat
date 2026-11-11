@echo off
rem Arranca la aplicacion en http://127.0.0.1:8000
rem La primera vez crea el entorno virtual e instala dependencias.
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv || goto :error
    .venv\Scripts\python -m pip install -r requirements.txt || goto :error
)
.venv\Scripts\python scripts\construir_datos.py || goto :error
start "" http://127.0.0.1:8000
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
goto :eof
:error
echo.
echo Algo fallo. Revisa el mensaje de arriba.
pause

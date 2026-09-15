FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc gdal-bin libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY core ./core
COPY repositorios ./repositorios
COPY motor_analitico ./motor_analitico
COPY api ./api
# El CLI usa DATOS_DIR (core/config.py) con default datos/mapa_color.csv;
# sin esto la ingesta dentro del contenedor falla con FileNotFoundError.
COPY datos ./datos

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim

WORKDIR /app

# Sin .pyc y logs sin buffer (para que salgan en Cloud Logging en tiempo real).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# En Cloud Run el filesystem del contenedor es de solo lectura salvo /tmp.
# El pipeline escribe los 3 artefactos (2 JSON + el .pptx) por dominio.
ENV DIR_DIAGNOSTICOS=/tmp/diagnosticos

# Cloud Run inyecta $PORT; el default 8080 es solo para correr la imagen en local.
ENV PORT=8080
EXPOSE 8080

# Forma shell (no JSON) para que $PORT se expanda en tiempo de arranque.
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT}

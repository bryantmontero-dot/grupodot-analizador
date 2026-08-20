#!/usr/bin/env bash
#
# Deploy del Analizador Web Grupodot a Cloud Run.
#
# Requisitos previos (ya cumplidos):
#   - gcloud instalado y autenticado (gcloud auth login)
#   - Billing habilitado en el proyecto
#   - Secreto "anthropic-api-key" creado en Secret Manager
#   - Rol roles/secretmanager.secretAccessor otorgado a la SA de cómputo por defecto
#
# Uso (Git Bash):
#   bash deploy.sh
#
set -euo pipefail

PROJECT_ID="grupodot-analizador"
REGION="us-central1"
SERVICE="analizador-web"

# ------------------------------------------------------------------
# 1. Fijar el proyecto activo
# ------------------------------------------------------------------
gcloud config set project "$PROJECT_ID"

# ------------------------------------------------------------------
# 2. Habilitar las APIs que necesita el build + deploy
#    - run:              el servicio en sí
#    - cloudbuild:       construye la imagen desde el Dockerfile
#    - artifactregistry: guarda la imagen construida
#    - secretmanager:    inyecta ANTHROPIC_API_KEY en runtime
#    Idempotente: si ya están activas, no hace nada.
# ------------------------------------------------------------------
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com

# ------------------------------------------------------------------
# 3. Build + deploy en un solo paso
#
#    --source .                sube el repo (respetando .gcloudignore), lo
#                              construye con el Dockerfile y despliega la imagen
#    --allow-unauthenticated   servicio público, sin IAM de por medio
#    --set-secrets             monta el secreto como env var; la key nunca
#                              queda en la imagen, en .env ni en el repo
#    --memory=2Gi              el pipeline carga el HTML scrapeado, la respuesta
#                              de Claude y arma el PPTX en memoria; además /tmp
#                              es tmpfs y consume de este mismo presupuesto
#    --cpu=2                   acelera scraping + generación del deck
#    --timeout=3600            el pipeline completo tarda ~60 s, pero un sitio
#                              lento o un reintento de Claude puede estirarse;
#                              3600 s es el máximo de Cloud Run
#    --concurrency=4           4 análisis simultáneos por instancia: más que eso
#                              y 2Gi se queda corto
#    --min-instances=0         escala a cero: no se paga por idle (a cambio de
#                              un cold start de ~10-15 s en la primera petición)
#
#    DIR_DIAGNOSTICOS=/tmp/diagnosticos NO se pasa aquí: ya viene fijado como
#    ENV en el Dockerfile, que es el único lugar donde debe vivir.
# ------------------------------------------------------------------
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --set-secrets=ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --concurrency=4 \
  --min-instances=0

# ------------------------------------------------------------------
# 4. Mostrar la URL y verificar que el servicio responde
#    /salud confirma que la API key llegó desde Secret Manager
#    (devuelve api_key_configurada: true, nunca el valor).
# ------------------------------------------------------------------
URL="$(gcloud run services describe "$SERVICE" \
  --region "$REGION" --format='value(status.url)')"

echo
echo "Servicio desplegado: $URL"
echo
echo "Verificando /salud ..."
curl -s "$URL/salud"
echo

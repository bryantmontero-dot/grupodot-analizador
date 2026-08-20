# Grupodot Analizador Web — Contexto del proyecto

## Contexto de empresa
Lee **`CONTEXTO_GRUPODOT.md`** (raíz) antes de proponer arquitectura: rol esperado, negocio de Grupodot, los 4 servicios reales del portafolio, principios de desarrollo y stack preferido. Incluye la restricción de este proyecto: usa Claude API (Anthropic), **no** Vertex AI / Gemini / BigQuery, y no se agrega infra GCP extra sin pedirlo.

## Qué es
Pipeline Python interno de Grupodot para analizar sitios web y generar diagnósticos comerciales MarTech. Tres fases: scraping → análisis IA → PPTX.

## Estado actual
- **Front web (demo)**: ✅ `app.py` (FastAPI) + `static/` — UI para correr el pipeline desde el navegador y descargar el PPTX.
- **Pipeline completo**: ✅ `run_pipeline.py <URL>` — CLI y **librería**: `ejecutar_pipeline(url)` corre las 3 fases en proceso (import directo, sin subprocess) y lanza `PipelineError(fase, nombre, detalle)` si alguna falla. `app.py` reutiliza esa función.
- **Fase 1 (Scraping)**: ✅ Funciona — `analizador_web.py`
- **Fase 2 (Análisis IA)**: ✅ Migrada de Gemini a Claude API — `analisis_claude.py` (claude-sonnet-4-6, key desde .env, salida en diagnosticos/)
- **Fase 3 (PPTX)**: ✅ Funciona — `generar_pptx.py` (deck 7 slides con branding Grupodot, salida en `diagnosticos/presentacion_<dominio>.pptx`)

## Utilidades / soporte
- `validar_fase2_simulado.py` — prueba la Fase 2 sin gastar API (simula la respuesta de Claude).
- `.env.example` — plantilla de variables de entorno (copiar a `.env` y rellenar `ANTHROPIC_API_KEY`).

## Seguridad
- API keys solo desde `.env` (nunca hardcodeadas)
- `.gitignore` protege `.env`, `venv/`, `diagnosticos/*.json`
- Archivos Gemini (`analisis_gemini.py`, `prueba_fase2.py`) quedan como referencia, tienen keys hardcodeadas — NO usar

## Front local (demo)
```
venv\Scripts\python.exe -m uvicorn app:app --reload
```
→ http://localhost:8000

- `POST /analizar` `{"url": "..."}` → corre el pipeline y devuelve madurez, score, sector, resumen ejecutivo, servicios, quick wins y la ruta de descarga del PPTX.
- `GET /descargar/{dominio}` → sirve `diagnosticos/presentacion_<dominio>.pptx` (dominio = netloc con `.` → `_`).
- `GET /salud` → verifica que la API key esté cargada (no expone su valor).
- `GET /logo-dot.png` → sirve el logo de la raíz si existe; si no, el front cae al wordmark.
- Front: `static/index.html` + `styles.css` + `app.js` (JS vanilla, sin build step). El loader avanza por tiempo estimado porque el pipeline es una sola petición (~60 s).
- CORS restringido a localhost; la API key nunca sale al navegador.

## Próximo paso
1. Agregar `logo-dot.png` en la raíz (hoy el deck y el front usan el wordmark de texto como fallback)
2. Dockerfile + despliegue en Cloud Run (API key vía Secret Manager)

## Fase 3 — Notas
- `generar_pptx.py <ruta_analisis.json>` → deck 16:9 de 7 slides: Portada · Resumen+Madurez · Fortalezas · Oportunidades (por impacto) · Servicios (por prioridad) · Quick wins · Cierre.
- Colores por impacto: Alto=Coral, Medio=Amarillo, Bajo=Verde. Por prioridad: Inmediata=Coral, Corto plazo=Amarillo, Mediano plazo=Turquesa.
- Logo: inserta `logo-dot.png` si existe, si no usa wordmark "grupodot" (azul en "dot"). Único punto: `_insertar_logo_o_wordmark`.
- Dependencia: `python-pptx` (trae Pillow). Salida `.pptx` ignorada por `.gitignore`.

## Branding Grupodot (para Fase 3)
- Logo: `logo-dot.png` (G negra geométrica)
- Colores: Azul Digital #2EA6FF, Turquesa Digital #38C0BD, Verde Crecimiento #48C555, Coral Decisión #F35E59, Amarillo Claridad #F3CB04, Negro #000000, Blanco #FEFEFE

## Fase 2 — Notas
- El prompt de `analisis_claude.py` recomienda **solo los 4 servicios reales** de `CONTEXTO_GRUPODOT.md`: Plataforma Unificada de Publicidad y Analítica · Creative IA · Nodus · Sentiment. Si el portafolio cambia, se actualizan los dos archivos.

## Stack
Python + venv, anthropic, python-dotenv, requests, beautifulsoup4, python-pptx, fastapi, uvicorn, python-multipart

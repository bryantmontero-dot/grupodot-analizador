# Analizador Web Grupodot

Herramienta interna del equipo MarTech. Le das la URL de un cliente (o prospecto)
y te devuelve un diagnóstico comercial en PowerPoint: en qué nivel de madurez
digital está, qué le falta, y cuáles de nuestros servicios le encajan.

La idea es dejar de armar esos decks a mano. Toma alrededor de un minuto por sitio.

## Cómo funciona

Son tres pasos encadenados:

1. **Scraping** (`analizador_web.py`) — baja el HTML y saca lo medible: qué tags
   de analítica y ads tiene instalados, meta tags, si hay chatbot, formularios,
   pixeles de redes, tiempos de carga.
2. **Análisis** (`analisis_claude.py`) — le pasa ese diagnóstico a Claude
   (`claude-sonnet-4-6`) y le pide de vuelta un JSON estructurado: sector,
   score de madurez, fortalezas, oportunidades priorizadas por impacto,
   quick wins, y qué servicios recomendar.
3. **Presentación** (`generar_pptx.py`) — arma el deck 16:9 de 7 slides con los
   colores de la marca.

Cada paso guarda su salida en `diagnosticos/`, así que si algo falla en el paso 3
no hay que volver a pagar la llamada a Claude.

`run_pipeline.py` es quien los encadena. Funciona como script y como librería —
`app.py` importa `ejecutar_pipeline()` en vez de invocar subprocesos, para que no
haya dos versiones de la misma lógica.

## Correrlo en local

Necesitas Python 3.11+ y una API key de Anthropic.

```bash
python -m venv venv
venv\Scripts\activate          # en Linux/Mac: source venv/bin/activate
pip install -r requirements.txt

copy .env.example .env         # y le pones tu ANTHROPIC_API_KEY
```

Desde la terminal:

```bash
python run_pipeline.py https://www.rappi.com.co
```

Deja los tres archivos en `diagnosticos/` y te imprime el resumen.

O con la interfaz web:

```bash
uvicorn app:app --reload
```

y abres http://localhost:8000. Pegas la URL, esperas el minuto, descargas el pptx.

Si quieres probar sin gastar créditos de API, `validar_fase2_simulado.py` corre el
paso 2 con una respuesta falsa de Claude.

## La API

| | |
|---|---|
| `POST /analizar` | `{"url": "..."}` → corre todo y devuelve el resumen + link de descarga |
| `GET /descargar/{dominio}` | el .pptx (dominio = el host con los puntos cambiados por `_`) |
| `GET /historial` | los análisis que ya están en disco |
| `DELETE /historial/{dominio}` | borra los 3 archivos de ese dominio |
| `GET /salud` | confirma que la API key cargó (no devuelve su valor) |

El front es HTML, CSS y JS plano en `static/`. No hay build step, no hay
node_modules. La barra de progreso avanza por tiempo estimado y no por progreso
real, porque `/analizar` es una sola petición larga.

## Deploy

Va a Cloud Run. El `deploy.sh` tiene los comandos comentados:

```bash
bash deploy.sh
```

Construye la imagen con Cloud Build, la despliega en `us-central1` y saca la
`ANTHROPIC_API_KEY` de Secret Manager. La key nunca entra a la imagen ni al repo.

Detalles que importan si vas a tocar el deploy:

- El `Dockerfile` arranca uvicorn con `$PORT`, que es lo que Cloud Run inyecta.
  No lo cambies a un puerto fijo.
- El filesystem del contenedor es de solo lectura salvo `/tmp`, así que la imagen
  define `DIR_DIAGNOSTICOS=/tmp/diagnosticos`. En local esa variable no existe y
  todo sigue yendo a `diagnosticos/` como siempre.
- Los flags de memoria y timeout no son arbitrarios: el pipeline arma el PPTX en
  memoria y una llamada a Claude con un sitio grande no es instantánea.

### Lo que todavía no está bien

**El historial no sirve en producción.** Los archivos viven en `/tmp`, que es
memoria y es de cada instancia. Con `min-instances=0` se borra todo cuando el
servicio escala a cero, y si hay dos instancias corriendo cada una ve una lista
distinta. Analizar y descargar sí funciona, porque pasa dentro de la misma
petición. Arreglarlo bien es mover los artefactos a un bucket de GCS.

**No hay caché.** Analizar dos veces el mismo sitio son dos llamadas a Claude.

## Estructura

```
analizador_web.py     scraping
analisis_claude.py    llamada a Claude + parseo del JSON
generar_pptx.py       construcción del deck
run_pipeline.py       orquestador (CLI y librería)
app.py                API FastAPI
static/               front
deploy.sh             deploy a Cloud Run
```

`CONTEXTO_GRUPODOT.md` tiene el contexto de negocio: los servicios reales del
portafolio y cómo debe sonar el diagnóstico. El prompt de `analisis_claude.py`
solo puede recomendar esos servicios — si el portafolio cambia hay que actualizar
los dos archivos, no solo uno.

## Notas

Las API keys van en `.env` y nada más. Está en el `.gitignore` junto con `venv/`
y los archivos generados.

Si el `logo-dot.png` no está en la raíz, tanto el deck como el front caen a un
wordmark de texto en vez de reventar.

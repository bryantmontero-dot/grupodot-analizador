"""
Front-end de demo del Analizador Web Grupodot (FastAPI).

Expone el pipeline de 3 fases por HTTP y sirve una interfaz estática simple:

    GET    /                    -> static/index.html
    POST   /analizar            -> {"url": "..."} corre el pipeline completo
    GET    /descargar/{dominio} -> descarga el .pptx generado
    GET    /historial           -> lista los análisis ya generados en diagnosticos/
    DELETE /historial/{dominio} -> borra los 3 artefactos de ese dominio

Levantar en local:
    uvicorn app:app --reload   ->  http://localhost:8000

La lógica de las 3 fases NO se duplica aquí: se reutiliza
run_pipeline.ejecutar_pipeline(). La ANTHROPIC_API_KEY vive solo en .env y
nunca se envía al navegador.

Autor: Equipo MarTech Grupodot
"""

import json
import os
import re
import sys
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from run_pipeline import (
    DIR_DIAGNOSTICOS,
    RAIZ,
    PipelineError,
    ejecutar_pipeline,
    normalizar_url,
    rutas_artefactos,
    url_valida,
)

DIR_STATIC = os.path.join(RAIZ, "static")

# Las fases imprimen emojis/acentos. Bajo uvicorn en Windows, stdout hereda
# cp1252 y un print reventaría la petición con UnicodeEncodeError.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Dominio normalizado: solo letras, dígitos, guiones y guiones bajos.
# Bloquea path traversal en /descargar/{dominio}.
RE_DOMINIO = re.compile(r"^[A-Za-z0-9_-]+$")

app = FastAPI(
    title="Analizador Web Grupodot",
    description="Demo interna: scraping + análisis MarTech con Claude + PPTX.",
    version="1.0.0",
)

# Solo localhost por ahora; al desplegar en Cloud Run se agrega el dominio real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ============================================================
# ESQUEMAS
# ============================================================

class AnalizarRequest(BaseModel):
    url: str


# ============================================================
# HISTORIAL — HELPERS
# ============================================================

# Los 3 artefactos que el pipeline deja por dominio en diagnosticos/.
# El nombre de la clave coincide con el de run_pipeline.rutas_artefactos().
ARTEFACTOS = {
    "diagnostico": ("diagnostico_", ".json"),
    "analisis": ("analisis_", ".json"),
    "presentacion": ("presentacion_", ".pptx"),
}


def _ruta_segura(dominio: str, tipo: str) -> str:
    """Ruta absoluta de un artefacto, validando el dominio contra path traversal.

    Lanza HTTPException 400 si el dominio no es un slug válido o si la ruta
    resuelta se sale de diagnosticos/ (defensa en profundidad).
    """
    if not RE_DOMINIO.match(dominio):
        raise HTTPException(status_code=400, detail="Dominio inválido.")

    ruta = rutas_artefactos(dominio)[tipo]

    if os.path.commonpath(
        [os.path.realpath(ruta), os.path.realpath(DIR_DIAGNOSTICOS)]
    ) != os.path.realpath(DIR_DIAGNOSTICOS):
        raise HTTPException(status_code=400, detail="Dominio inválido.")

    return ruta


def _leer_json(ruta: str) -> dict:
    """Carga un JSON del historial; devuelve {} si falta o está corrupto.

    Un archivo dañado no debe tumbar el listado completo: esa fila simplemente
    sale con menos datos.
    """
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _dominios_en_disco() -> dict:
    """Escanea diagnosticos/ y agrupa los archivos por dominio.

    Devuelve {dominio: {"diagnostico": bool, "analisis": bool, "presentacion": bool}}.
    """
    encontrados = {}

    try:
        nombres = os.listdir(DIR_DIAGNOSTICOS)
    except OSError:
        return encontrados  # la carpeta aún no existe: historial vacío

    for nombre in nombres:
        for tipo, (prefijo, sufijo) in ARTEFACTOS.items():
            if not (nombre.startswith(prefijo) and nombre.endswith(sufijo)):
                continue

            dominio = nombre[len(prefijo) : -len(sufijo)]
            # Ignora nombres que no encajan en el slug esperado (evita que un
            # archivo suelto genere una fila con dominio no descargable).
            if not dominio or not RE_DOMINIO.match(dominio):
                continue

            encontrados.setdefault(
                dominio, {t: False for t in ARTEFACTOS}
            )[tipo] = True
            break

    return encontrados


def _fila_historial(dominio: str, presentes: dict) -> dict:
    """Arma la entrada del historial para un dominio a partir de sus archivos."""
    rutas = rutas_artefactos(dominio)

    analisis = _leer_json(rutas["analisis"]) if presentes["analisis"] else {}
    meta = analisis.get("meta") or {}
    madurez = analisis.get("madurez_digital") or {}
    sector = analisis.get("sector") or {}

    # URL: la del análisis; si no hay, la del diagnóstico crudo.
    url = meta.get("url_analizada")
    if not url and presentes["diagnostico"]:
        diagnostico = _leer_json(rutas["diagnostico"])
        url = diagnostico.get("url")

    # Fecha: la que dejó el pipeline; si falta, el mtime del archivo más reciente.
    fecha = meta.get("fecha_diagnostico")
    if not fecha:
        mtimes = [
            os.path.getmtime(rutas[t])
            for t, existe in presentes.items()
            if existe and os.path.isfile(rutas[t])
        ]
        fecha = datetime.fromtimestamp(max(mtimes)).isoformat() if mtimes else None

    return {
        "dominio": dominio,
        "url": url,
        "fecha": fecha,
        "madurez": {"nivel": madurez.get("nivel"), "score": madurez.get("score")},
        "sector": {"industria": sector.get("industria")},
        "archivos": presentes,
        # El front solo habilita el botón de descarga si hay .pptx en disco.
        "descarga": f"/descargar/{dominio}" if presentes["presentacion"] else None,
    }


# ============================================================
# ENDPOINTS
# ============================================================

@app.post("/analizar")
def analizar(payload: AnalizarRequest):
    """Corre el pipeline completo y devuelve el resumen para la tarjeta del front."""
    url = normalizar_url(payload.url)
    if not url_valida(url):
        raise HTTPException(
            status_code=400,
            detail="URL inválida. Ejemplo válido: https://www.rappi.com.co",
        )

    try:
        resultado = ejecutar_pipeline(url)
    except PipelineError as e:
        # Fase 1 = problema del sitio del cliente (culpa del input) -> 400.
        # Fases 2/3 = fallo interno (API key, Claude, python-pptx) -> 502.
        codigo = 400 if e.fase in (0, 1) else 502
        raise HTTPException(
            status_code=codigo,
            detail=f"Falló la fase {e.fase} ({e.nombre_fase}): {e.detalle}",
        )

    analisis = resultado["analisis"]
    madurez = analisis.get("madurez_digital", {})
    sector = analisis.get("sector", {})

    return {
        "estado": "ok",
        "url": resultado["url"],
        "dominio": resultado["dominio"],
        "duracion_segundos": resultado["duracion_segundos"],
        "madurez": {
            "nivel": madurez.get("nivel"),
            "score": madurez.get("score"),
            "justificacion": madurez.get("justificacion"),
        },
        "sector": {
            "industria": sector.get("industria"),
            "subsector": sector.get("subsector"),
        },
        "resumen_ejecutivo": analisis.get("resumen_ejecutivo"),
        "servicios_recomendados": analisis.get("servicios_recomendados", []),
        "quick_wins": analisis.get("quick_wins", []),
        "pptx": {
            "dominio": resultado["dominio"],
            "ruta": os.path.relpath(resultado["rutas"]["presentacion"], RAIZ),
            "descarga": f"/descargar/{resultado['dominio']}",
        },
    }


@app.get("/descargar/{dominio}")
def descargar(dominio: str):
    """Sirve diagnosticos/presentacion_<dominio>.pptx como descarga."""
    ruta = _ruta_segura(dominio, "presentacion")

    if not os.path.isfile(ruta):
        raise HTTPException(
            status_code=404,
            detail=f"No hay presentación generada para {dominio}. Corre el análisis primero.",
        )

    return FileResponse(
        ruta,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"presentacion_{dominio}.pptx",
    )


@app.get("/historial")
def historial():
    """Lista los análisis ya generados, agrupados por dominio (más reciente primero)."""
    encontrados = _dominios_en_disco()
    filas = [_fila_historial(d, presentes) for d, presentes in encontrados.items()]

    # Más recientes arriba. Las filas sin fecha van al final.
    filas.sort(key=lambda f: (f["fecha"] is not None, f["fecha"] or ""), reverse=True)

    return {"total": len(filas), "analisis": filas}


@app.delete("/historial/{dominio}")
def eliminar_historial(dominio: str):
    """Borra los 3 artefactos de un dominio. El front confirma antes de llamar."""
    # Valida los 3 dominios antes de borrar nada: si uno falla, no dejamos
    # el historial a medio borrar.
    rutas = {tipo: _ruta_segura(dominio, tipo) for tipo in ARTEFACTOS}

    if not any(os.path.isfile(r) for r in rutas.values()):
        raise HTTPException(
            status_code=404, detail=f"No hay análisis guardado para {dominio}."
        )

    eliminados = []
    for tipo, ruta in rutas.items():
        if not os.path.isfile(ruta):
            continue
        try:
            os.remove(ruta)
        except OSError as e:
            # Típico en Windows: el .pptx sigue abierto en PowerPoint.
            raise HTTPException(
                status_code=409,
                detail=f"No se pudo borrar {os.path.basename(ruta)}: {e}",
            )
        eliminados.append(tipo)

    return {"estado": "ok", "dominio": dominio, "eliminados": eliminados}


@app.get("/logo-dot.png")
def logo():
    """Sirve el logo desde la raíz si existe; si no, 404 y el front usa el wordmark."""
    ruta = os.path.join(RAIZ, "logo-dot.png")
    if not os.path.isfile(ruta):
        raise HTTPException(status_code=404, detail="Sin logo; se usa el wordmark.")
    return FileResponse(ruta, media_type="image/png")


@app.get("/salud")
def salud():
    """Chequeo rápido: ¿está la API key cargada? (nunca devuelve su valor)."""
    from analisis_claude import ANTHROPIC_API_KEY, MODELO

    return {"estado": "ok", "modelo": MODELO, "api_key_configurada": bool(ANTHROPIC_API_KEY)}


# El montaje en "/" va al final: StaticFiles captura todo lo no declarado arriba.
app.mount("/", StaticFiles(directory=DIR_STATIC, html=True), name="static")

"""
Pipeline completo Grupodot - orquestador de las 3 fases.

Ejecuta en secuencia, para una sola URL:
    Fase 1  scraping        -> analizador_web.analizar_url        -> diagnosticos/diagnostico_<dominio>.json
    Fase 2  analisis IA     -> analisis_claude.analizar_con_claude -> diagnosticos/analisis_<dominio>.json
    Fase 3  presentacion    -> generar_pptx.construir_presentacion -> diagnosticos/presentacion_<dominio>.pptx

Uso como script:
    python run_pipeline.py <URL>
    python run_pipeline.py https://www.rappi.com.co

Uso como libreria (lo que hace app.py):
    from run_pipeline import ejecutar_pipeline, PipelineError
    resultado = ejecutar_pipeline("https://www.rappi.com.co")

Las tres fases se invocan en proceso (import directo), no por subprocess: asi
el front-end FastAPI reutiliza exactamente la misma logica sin duplicarla. Si
una fase falla se lanza PipelineError con el numero y nombre de la fase.

Autor: Equipo MarTech Grupodot
"""

import json
import os
import sys
import time
from urllib.parse import urlparse

import analisis_claude
import generar_pptx
from analizador_web import analizar_url


# ============================================================
# CONFIGURACIÓN
# ============================================================

# Directorio raíz del proyecto (donde vive este script y los demás).
RAIZ = os.path.dirname(os.path.abspath(__file__))

# Dónde se dejan los 3 artefactos por dominio. En local es diagnosticos/ junto
# al código; en Cloud Run el filesystem del contenedor es de solo lectura salvo
# /tmp, así que la imagen define DIR_DIAGNOSTICOS=/tmp/diagnosticos.
# Único punto de escritura del servidor: las fases solo guardan a disco desde
# sus main() de CLI, nunca desde ejecutar_pipeline().
DIR_DIAGNOSTICOS = os.environ.get("DIR_DIAGNOSTICOS") or os.path.join(
    RAIZ, "diagnosticos"
)


class PipelineError(RuntimeError):
    """Fallo en una fase del pipeline. Lleva el número y nombre de la fase."""

    def __init__(self, fase: int, nombre: str, detalle: str):
        super().__init__(f"Fase {fase} ({nombre}): {detalle}")
        self.fase = fase
        self.nombre_fase = nombre
        self.detalle = detalle


def normalizar_url(url: str) -> str:
    """Antepone https:// si falta el esquema (igual que analizador_web)."""
    url = (url or "").strip()
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def dominio_desde_url(url: str) -> str:
    """netloc con puntos -> guiones bajos. Mismo criterio que las 3 fases."""
    return urlparse(normalizar_url(url)).netloc.replace(".", "_")


def url_valida(url: str) -> bool:
    """Valida el host antes de normalizarlo (el netloc real, con puntos)."""
    netloc = urlparse(normalizar_url(url)).netloc
    return bool(netloc) and "." in netloc and " " not in netloc


def rutas_artefactos(dominio: str) -> dict:
    """Rutas absolutas de los 3 artefactos para un dominio normalizado."""
    return {
        "diagnostico": os.path.join(DIR_DIAGNOSTICOS, f"diagnostico_{dominio}.json"),
        "analisis": os.path.join(DIR_DIAGNOSTICOS, f"analisis_{dominio}.json"),
        "presentacion": os.path.join(DIR_DIAGNOSTICOS, f"presentacion_{dominio}.pptx"),
    }


def _guardar_json(ruta: str, datos: dict) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


# ============================================================
# ORQUESTADOR REUTILIZABLE
# ============================================================

def ejecutar_pipeline(url: str, log=print) -> dict:
    """Corre las 3 fases para una URL y devuelve rutas + datos generados.

    Devuelve:
        {
          "url", "dominio", "duracion_segundos",
          "diagnostico": {...}, "analisis": {...},
          "rutas": {"diagnostico": ..., "analisis": ..., "presentacion": ...},
        }

    Lanza PipelineError si alguna fase falla.
    """
    url = normalizar_url(url)
    if not url:
        raise PipelineError(0, "Validación", "La URL está vacía.")

    if not url_valida(url):
        raise PipelineError(0, "Validación", f"URL inválida: {url!r}")

    dominio = dominio_desde_url(url)

    os.makedirs(DIR_DIAGNOSTICOS, exist_ok=True)
    rutas = rutas_artefactos(dominio)

    inicio = time.time()

    # --- Fase 1: scraping ---------------------------------------------------
    log(f"[1/3] Escaneando sitio: {url}")
    try:
        diagnostico = analizar_url(url)
    except Exception as e:  # red, parseo, etc.
        raise PipelineError(1, "Scraping", str(e))

    # analizar_url no lanza excepción si la URL es inalcanzable: devuelve un
    # dict con campo "error". Lo cortamos aquí para no gastar la llamada a
    # Claude ni generar un deck basura.
    if diagnostico.get("error"):
        raise PipelineError(1, "Scraping", diagnostico["error"])

    _guardar_json(rutas["diagnostico"], diagnostico)

    # --- Fase 2: análisis IA ------------------------------------------------
    log(f"[2/3] Generando análisis con IA ({analisis_claude.MODELO})...")
    if not analisis_claude.ANTHROPIC_API_KEY:
        raise PipelineError(
            2, "Análisis IA",
            "Falta ANTHROPIC_API_KEY. Defínela en el archivo .env de la raíz.",
        )
    try:
        analisis = analisis_claude.analizar_con_claude(diagnostico)
    except Exception as e:
        raise PipelineError(2, "Análisis IA", str(e))

    _guardar_json(rutas["analisis"], analisis)

    # --- Fase 3: presentación PPTX -----------------------------------------
    log("[3/3] Creando presentación...")
    try:
        prs = generar_pptx.construir_presentacion(analisis)
        prs.save(rutas["presentacion"])
    except Exception as e:
        raise PipelineError(3, "Presentación PPTX", str(e))

    if not os.path.isfile(rutas["presentacion"]):
        raise PipelineError(3, "Presentación PPTX", "No se generó el archivo .pptx.")

    return {
        "url": url,
        "dominio": dominio,
        "duracion_segundos": round(time.time() - inicio, 1),
        "diagnostico": diagnostico,
        "analisis": analisis,
        "rutas": rutas,
    }


# ============================================================
# ENTRY POINT (CLI)
# ============================================================

def main():
    # Las fases imprimen emojis/acentos; en consola Windows (cp1252) eso
    # reventaría con UnicodeEncodeError. Antes se resolvía forzando UTF-8 en el
    # subproceso; ahora que corren en proceso, lo forzamos aquí.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if len(sys.argv) < 2:
        print("Uso: python run_pipeline.py <URL>")
        print("Ejemplo: python run_pipeline.py https://www.rappi.com.co")
        raise SystemExit(1)

    url = normalizar_url(sys.argv[1])
    print(f"\nPipeline Grupodot — URL: {url}")
    print(f"Dominio normalizado: {dominio_desde_url(url)}\n")

    try:
        resultado = ejecutar_pipeline(url)
    except PipelineError as e:
        print("\n" + "!" * 70)
        print(f"  ERROR EN FASE {e.fase} ({e.nombre_fase})")
        print(f"  Detalle: {e.detalle}")
        print("  Pipeline detenido.")
        print("!" * 70)
        raise SystemExit(1)

    analisis_claude.imprimir_analisis(resultado["analisis"])

    def _rel(ruta: str) -> str:
        return os.path.relpath(ruta, RAIZ)

    print("\n" + "=" * 70)
    print("  PIPELINE COMPLETADO")
    print("=" * 70)
    print(f"  URL analizada : {resultado['url']}")
    print("  Archivos generados:")
    print(f"    1. Diagnóstico  -> {_rel(resultado['rutas']['diagnostico'])}")
    print(f"    2. Análisis     -> {_rel(resultado['rutas']['analisis'])}")
    print(f"    3. Presentación -> {_rel(resultado['rutas']['presentacion'])}")
    print(f"  Tiempo total: {resultado['duracion_segundos']:.1f} s")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

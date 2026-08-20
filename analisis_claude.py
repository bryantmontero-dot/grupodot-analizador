"""
Análisis MarTech con Claude - Grupodot
Lee el diagnóstico técnico de analizador_web.py y genera análisis estratégico
con la Claude API (Anthropic). Migración de analisis_gemini.py.

Uso:
    python analisis_claude.py <ruta_diagnostico.json>
    python analisis_claude.py diagnosticos/diagnostico_www_rappi_com_co.json

Requiere:
    pip install anthropic python-dotenv

Configuración:
    Define ANTHROPIC_API_KEY en el archivo .env de la raíz del proyecto.

Autor: Equipo MarTech Grupodot
"""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from anthropic import Anthropic
from dotenv import load_dotenv


# ============================================================
# CONFIGURACIÓN
# ============================================================

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

MODELO = "claude-sonnet-4-6"

DIR_DIAGNOSTICOS = "diagnosticos"


# ============================================================
# PROMPT ESPECIALIZADO GRUPODOT
# ============================================================

PROMPT_SISTEMA = """Eres un consultor senior de MarTech en Grupodot, agencia líder en marketing digital y tecnología en Latinoamérica.

Tu trabajo es analizar diagnósticos técnicos de sitios web y producir un análisis estratégico accionable.

## Portafolio de servicios Grupodot que puedes recomendar:

Grupodot construye soluciones de MarTech, DataTech e IA Generativa sobre Google Cloud
Platform para empresas Mid-Market y Enterprise de Latinoamérica. Solo puedes recomendar
estos CUATRO servicios (usa el nombre exacto):

### 1. Plataforma Unificada de Publicidad y Analítica
Servicio administrado sobre Google Analytics 360 y Google Tag Manager 360. Incluye
implementación, auditorías, gobierno de datos, soporte, capacitación, Server Side Tagging,
Consent Mode, integración con BigQuery y Vertex AI, y dashboards en Looker Studio.
Objetivo: convertir Google Analytics en una plataforma empresarial de datos.

### 2. Creative IA
Generación automática de contenido con IA: imágenes, video, edición mediante IA, campañas
automatizadas, reutilización de activos y publicación automatizada.
Tecnologías: Vertex AI, Gemini, Veo, Cloud Storage, Cloud Run.

### 3. Nodus
Sistema de agentes inteligentes especializados en SEO, SEM, Contenidos y Visibilidad IA.
Automatiza tareas repetitivas de marketing.
Tecnologías: Gemini Enterprise, BigQuery, Vertex AI, Google Workspace APIs, Looker Studio.

### 4. Sentiment
Análisis de sentimientos. Hoy soporta YouTube; el roadmap incluye Instagram, TikTok,
LinkedIn y X.
Tecnologías: Vertex AI, BigQuery, Cloud Functions, Cloud Run.

## Reglas de análisis:

1. MADUREZ DIGITAL: Clasifica en uno de estos niveles según la evidencia técnica encontrada:
   - "Inexistente": Sin presencia digital o sitio en construcción, sin analytics ni SEO básico
   - "Básico": Sitio funcional con analytics mínimo (solo GTM o GA4 básico), SEO elemental
   - "Intermedio": Analytics configurado + algunos pixeles publicitarios + SEO con schema markup + alguna señal de personalización
   - "Avanzado": Stack completo de analytics + publicidad multi-canal + SEO/AEO con datos estructurados ricos + personalización/IA activa + CDP
   - "Líder": Todo lo anterior + server-side tagging + experimentación activa + stack headless + estrategia multi-mercado

2. SECTOR: Infiere el sector/industria a partir del título, URL y tecnologías detectadas.

3. OPORTUNIDADES: Identifica gaps concretos basándote en lo que FALTA en el diagnóstico técnico. Cada oportunidad debe ser específica y accionable.

4. SERVICIOS RECOMENDADOS: Mapea cada oportunidad a uno de los CUATRO servicios reales del portafolio Grupodot (usa el nombre exacto, sin inventar servicios nuevos). Prioriza por impacto. No es obligatorio recomendar los cuatro: incluye solo los que apliquen al caso.

## Formato de respuesta OBLIGATORIO:

Responde ÚNICAMENTE con un JSON válido (sin markdown, sin backticks, sin texto adicional) con esta estructura exacta:

{
  "madurez_digital": {
    "nivel": "Básico|Intermedio|Avanzado|Líder|Inexistente",
    "score": 0-100,
    "justificacion": "Explicación breve de por qué se asigna este nivel"
  },
  "sector": {
    "industria": "nombre del sector",
    "subsector": "nicho específico si se puede inferir"
  },
  "resumen_ejecutivo": "Párrafo de 3-4 oraciones con el diagnóstico general del sitio, escrito como si fuera para un CMO o director de marketing",
  "fortalezas": [
    {
      "area": "nombre del área",
      "detalle": "qué están haciendo bien y por qué importa"
    }
  ],
  "oportunidades": [
    {
      "area": "Analytics|SEO|GEO|AEO|Publicidad|Personalización|Stack Técnico",
      "hallazgo": "qué se detectó (o no se detectó)",
      "impacto": "Alto|Medio|Bajo",
      "recomendacion": "qué debería hacer el cliente"
    }
  ],
  "servicios_recomendados": [
    {
      "servicio": "Plataforma Unificada de Publicidad y Analítica|Creative IA|Nodus|Sentiment",
      "prioridad": "Inmediata|Corto plazo|Mediano plazo",
      "descripcion": "qué incluiría este servicio para este cliente específico",
      "oportunidades_que_resuelve": ["lista de áreas de oportunidad que cubre"]
    }
  ],
  "quick_wins": [
    "Acción concreta que se puede implementar en menos de 2 semanas"
  ]
}"""


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def analizar_con_claude(diagnostico: dict) -> dict:
    """Envía el diagnóstico técnico a Claude y devuelve el análisis estratégico."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt_usuario = (
        "Analiza el siguiente diagnóstico técnico de un sitio web y genera "
        "el análisis estratégico MarTech completo:\n\n"
        + json.dumps(diagnostico, ensure_ascii=False, indent=2)
    )

    # No usamos prefill de mensaje "assistant": claude-sonnet-4-6 (familia 4.6+)
    # devuelve 400 si la conversación termina en un turno del asistente. El
    # PROMPT_SISTEMA ya obliga a responder solo con JSON, así que parseamos la
    # respuesta completa.
    response = client.messages.create(
        model=MODELO,
        # 4096 truncaba el JSON en análisis grandes; 16000 da margen sin riesgo
        # de timeout en peticiones no-streaming.
        max_tokens=16000,
        temperature=0.3,
        system=PROMPT_SISTEMA,
        messages=[
            {"role": "user", "content": prompt_usuario},
        ],
    )

    texto = response.content[0].text.strip()

    # Por robustez, extraemos el objeto JSON entre la primera "{" y la última "}"
    # (descarta posibles backticks o texto suelto si el modelo se desvía).
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        texto = texto[inicio : fin + 1]

    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"Respuesta cruda de Claude:\n{texto[:500]}")
        raise RuntimeError(f"Claude no devolvió JSON válido: {e}")

    resultado["meta"] = {
        "url_analizada": diagnostico.get("url"),
        "fecha_diagnostico": diagnostico.get("fecha_analisis"),
        "modelo_ia": MODELO,
    }

    return resultado


# ============================================================
# PRESENTACIÓN EN CONSOLA
# ============================================================

def imprimir_analisis(analisis: dict) -> None:
    """Imprime el análisis estratégico de forma legible en consola."""
    url = analisis.get("meta", {}).get("url_analizada", "N/A")
    madurez = analisis.get("madurez_digital", {})
    sector = analisis.get("sector", {})

    print("\n" + "=" * 70)
    print("  ANALISIS ESTRATEGICO MARTECH - GRUPODOT")
    print(f"  {url}")
    print("=" * 70)

    print(f"\n  MADUREZ DIGITAL: {madurez.get('nivel', 'N/A')} ({madurez.get('score', 'N/A')}/100)")
    print(f"  SECTOR: {sector.get('industria', 'N/A')} - {sector.get('subsector', 'N/A')}")

    print("\n--- Resumen Ejecutivo ---")
    print(f"  {analisis.get('resumen_ejecutivo', 'N/A')}")

    fortalezas = analisis.get("fortalezas", [])
    if fortalezas:
        print(f"\n--- Fortalezas ({len(fortalezas)}) ---")
        for item in fortalezas:
            print(f"  [+] {item.get('area', '')}: {item.get('detalle', '')}")

    oportunidades = analisis.get("oportunidades", [])
    if oportunidades:
        print(f"\n--- Oportunidades ({len(oportunidades)}) ---")
        for o in oportunidades:
            impacto = o.get("impacto", "")
            marca = {"Alto": "!!!", "Medio": "!! ", "Bajo": "!  "}.get(impacto, "   ")
            print(f"  [{marca}] {o.get('area', '')}: {o.get('hallazgo', '')}")
            print(f"        -> {o.get('recomendacion', '')}")

    servicios = analisis.get("servicios_recomendados", [])
    if servicios:
        print(f"\n--- Servicios Recomendados ({len(servicios)}) ---")
        for s in servicios:
            print(f"  [{s.get('prioridad', '')}] {s.get('servicio', '')}")
            print(f"        {s.get('descripcion', '')}")

    quick_wins = analisis.get("quick_wins", [])
    if quick_wins:
        print("\n--- Quick Wins ---")
        for i, qw in enumerate(quick_wins, 1):
            print(f"  {i}. {qw}")

    print("\n" + "=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    if not ANTHROPIC_API_KEY:
        print("ERROR: Falta ANTHROPIC_API_KEY.")
        print("Define la clave en el archivo .env de la raíz del proyecto:")
        print("    ANTHROPIC_API_KEY=sk-ant-...")
        print("Obtén tu clave en: https://console.anthropic.com/settings/keys")
        raise SystemExit(1)

    if len(sys.argv) < 2:
        print("Uso: python analisis_claude.py <ruta_diagnostico.json>")
        print("Ejemplo: python analisis_claude.py diagnosticos/diagnostico_www_rappi_com_co.json")
        raise SystemExit(1)

    archivo_diagnostico = sys.argv[1]

    if not os.path.isfile(archivo_diagnostico):
        print(f"ERROR: No se encontró el archivo de diagnóstico: {archivo_diagnostico}")
        raise SystemExit(1)

    print(f"Cargando diagnostico: {archivo_diagnostico}")
    with open(archivo_diagnostico, "r", encoding="utf-8") as f:
        diagnostico = json.load(f)

    print(f"Enviando {diagnostico['url']} a Claude ({MODELO})...")
    analisis = analizar_con_claude(diagnostico)

    imprimir_analisis(analisis)

    # Guardar en la carpeta diagnosticos/, no en la raíz.
    Path(DIR_DIAGNOSTICOS).mkdir(exist_ok=True)
    dominio = urlparse(diagnostico["url"]).netloc.replace(".", "_")
    output_file = os.path.join(DIR_DIAGNOSTICOS, f"analisis_{dominio}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(analisis, f, ensure_ascii=False, indent=2)

    print(f"\nJSON guardado en: {output_file}")


if __name__ == "__main__":
    main()

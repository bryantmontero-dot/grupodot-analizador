"""
Analizador Web Grupodot - Semana 1
Detecta el stack MarTech de una URL y devuelve un diagnóstico técnico en JSON.

Uso:
    python analizador_web.py https://www.ejemplo.com

Autor: Equipo MarTech Grupodot
"""

import json
import re
import sys
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURACIÓN
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 15  # segundos


# ============================================================
# DETECTORES DE TAGS Y TECNOLOGÍAS MARTECH
# ============================================================

def detectar_analytics(html: str) -> dict:
    """Detecta herramientas de analytics en el HTML."""
    return {
        "google_analytics_4": bool(re.search(r"G-[A-Z0-9]{8,}", html)),
        "google_tag_manager": "googletagmanager.com/gtm.js" in html or "GTM-" in html,
        "universal_analytics_legacy": bool(re.search(r"UA-\d{4,}-\d+", html)),
        "google_ads_tag": "googletagmanager.com/gtag" in html or "AW-" in html,
        "hotjar": "static.hotjar.com" in html,
        "mixpanel": "mixpanel" in html.lower(),
        "amplitude": "amplitude.com" in html,
        "segment": "cdn.segment.com" in html,
    }


def detectar_publicidad(html: str) -> dict:
    """Detecta pixeles de plataformas publicitarias."""
    return {
        "meta_pixel": "connect.facebook.net" in html or "fbq(" in html,
        "tiktok_pixel": "analytics.tiktok.com" in html,
        "linkedin_insight": "snap.licdn.com" in html,
        "twitter_pixel": "static.ads-twitter.com" in html,
        "pinterest_tag": "s.pinimg.com/ct/" in html,
    }


def detectar_seo_geo_aeo(html: str, soup: BeautifulSoup) -> dict:
    """Detecta señales SEO, GEO (geotargeting) y AEO (Answer Engine Optimization)."""
    # Schema.org / structured data
    scripts_ld_json = soup.find_all("script", type="application/ld+json")
    tipos_schema = []
    for script in scripts_ld_json:
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, dict) and "@type" in data:
                tipos_schema.append(data["@type"])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "@type" in item:
                        tipos_schema.append(item["@type"])
        except (json.JSONDecodeError, TypeError):
            continue

    # Meta tags clave
    meta_description = soup.find("meta", attrs={"name": "description"})
    meta_og = soup.find("meta", attrs={"property": "og:title"})
    meta_twitter = soup.find("meta", attrs={"name": "twitter:card"})

    # Hreflang (geotargeting)
    hreflangs = [link.get("hreflang") for link in soup.find_all("link", hreflang=True)]

    # Canonical
    canonical = soup.find("link", rel="canonical")

    # Headings (estructura semántica)
    h1_count = len(soup.find_all("h1"))
    h2_count = len(soup.find_all("h2"))

    return {
        "schema_markup_presente": len(scripts_ld_json) > 0,
        "tipos_schema_detectados": list(set(tipos_schema)),
        "tiene_meta_description": meta_description is not None,
        "tiene_open_graph": meta_og is not None,
        "tiene_twitter_card": meta_twitter is not None,
        "idiomas_detectados_hreflang": hreflangs,
        "tiene_canonical": canonical is not None,
        "cantidad_h1": h1_count,
        "cantidad_h2": h2_count,
    }


def detectar_stack_tecnico(html: str, headers: dict) -> dict:
    """Detecta CMS, frameworks y tecnologías del sitio."""
    html_lower = html.lower()
    return {
        "wordpress": "wp-content" in html_lower or "wp-includes" in html_lower,
        "shopify": "cdn.shopify.com" in html_lower or "shopify" in headers.get("x-powered-by", "").lower(),
        "vtex": "vtex" in html_lower,
        "wix": "wix.com" in html_lower or "wixstatic" in html_lower,
        "react": "_next/static" in html or "react" in html_lower,
        "nextjs": "_next/static" in html,
        "cloudflare": "cloudflare" in headers.get("server", "").lower() or "cf-ray" in headers,
        "servidor": headers.get("server", "No detectado"),
    }


def detectar_personalizacion_ia(html: str) -> dict:
    """Detecta señales de personalización server-side o uso de IA."""
    return {
        "chatbot_detectado": any(
            x in html.lower() for x in ["intercom", "drift.com", "tawk.to", "zendesk", "hubspot"]
        ),
        "ab_testing": any(
            x in html.lower() for x in ["optimizely", "vwo.com", "google-optimize"]
        ),
        "cdp_detectado": any(
            x in html.lower() for x in ["segment.com", "tealium", "mparticle"]
        ),
    }


# ============================================================
# ORQUESTADOR PRINCIPAL
# ============================================================

def analizar_url(url: str) -> dict:
    """Ejecuta el análisis completo de una URL y devuelve un diagnóstico estructurado."""
    # Normalizar URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"\n🔍 Analizando: {url}\n")

    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as e:
        return {
            "url": url,
            "error": f"No se pudo acceder a la URL: {e}",
            "fecha_analisis": datetime.now().isoformat(),
        }

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    # Información básica
    title = soup.title.string.strip() if soup.title and soup.title.string else "Sin título"

    # Verificar robots.txt y sitemap
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    tiene_robots = _verificar_recurso(urljoin(base_url, "/robots.txt"))
    tiene_sitemap = _verificar_recurso(urljoin(base_url, "/sitemap.xml"))

    diagnostico = {
        "url": url,
        "url_final": response.url,
        "fecha_analisis": datetime.now().isoformat(),
        "info_basica": {
            "titulo": title,
            "status_code": response.status_code,
            "tamano_html_kb": round(len(html) / 1024, 2),
            "tiene_robots_txt": tiene_robots,
            "tiene_sitemap_xml": tiene_sitemap,
            "https": url.startswith("https://"),
        },
        "analytics": detectar_analytics(html),
        "publicidad": detectar_publicidad(html),
        "seo_geo_aeo": detectar_seo_geo_aeo(html, soup),
        "stack_tecnico": detectar_stack_tecnico(html, dict(response.headers)),
        "personalizacion_ia": detectar_personalizacion_ia(html),
    }

    return diagnostico


def _verificar_recurso(url: str) -> bool:
    """Verifica si un recurso (robots.txt, sitemap.xml) existe."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=5, allow_redirects=True)
        return r.status_code == 200
    except requests.RequestException:
        return False


# ============================================================
# PRESENTACIÓN LEGIBLE DEL DIAGNÓSTICO
# ============================================================

def imprimir_resumen(diagnostico: dict) -> None:
    """Imprime un resumen legible del diagnóstico en consola."""
    if "error" in diagnostico:
        print(f"❌ {diagnostico['error']}")
        return

    print("=" * 70)
    print(f"📊 DIAGNÓSTICO TÉCNICO — {diagnostico['info_basica']['titulo']}")
    print("=" * 70)

    def resumen_seccion(titulo: str, datos: dict) -> None:
        print(f"\n▸ {titulo}")
        for k, v in datos.items():
            icono = "✅" if v is True else "❌" if v is False else "ℹ️ "
            print(f"  {icono} {k}: {v}")

    resumen_seccion("INFO BÁSICA", diagnostico["info_basica"])
    resumen_seccion("ANALYTICS", diagnostico["analytics"])
    resumen_seccion("PUBLICIDAD", diagnostico["publicidad"])
    resumen_seccion("SEO / GEO / AEO", diagnostico["seo_geo_aeo"])
    resumen_seccion("STACK TÉCNICO", diagnostico["stack_tecnico"])
    resumen_seccion("PERSONALIZACIÓN / IA", diagnostico["personalizacion_ia"])

    print("\n" + "=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    if len(sys.argv) < 2:
        print("Uso: python analizador_web.py <URL>")
        print("Ejemplo: python analizador_web.py https://www.rappi.com.co")
        sys.exit(1)

    url = sys.argv[1]
    diagnostico = analizar_url(url)

    # Mostrar resumen en consola
    imprimir_resumen(diagnostico)

    # Guardar JSON para las siguientes semanas
    output_file = f"diagnostico_{urlparse(url).netloc.replace('.', '_')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(diagnostico, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Diagnóstico guardado en: {output_file}\n")


if __name__ == "__main__":
    main()

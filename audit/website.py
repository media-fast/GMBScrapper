"""Audit SEO d'un site web (technique + on-page) sans API externe.

Utilise httpx + BeautifulSoup pour récupérer la page d'accueil et analyser :
- Technique : HTTPS, temps de réponse, robots.txt, sitemap.xml
- On-page : title, meta description, H1, viewport, lang, canonical, alt images
- Sémantique : Schema.org JSON-LD (LocalBusiness)
- Contenu : nombre de mots
"""

import json
import re
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _finding(severity: str, title: str, detail: str = "", recommendation: str = "") -> dict:
    return {
        "severity": severity,  # "ok" | "warning" | "critical"
        "title": title,
        "detail": detail,
        "recommendation": recommendation,
    }


def _check_url(url: str, timeout: float = 5.0) -> bool:
    """Vérifie si une URL retourne 200 (utilisé pour robots.txt et sitemap.xml)."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True,
                          headers={"User-Agent": USER_AGENT}) as c:
            r = c.get(url)
        return r.status_code == 200 and len(r.text) > 0
    except Exception:
        return False


def _parse_schema_types(soup: BeautifulSoup) -> list[str]:
    types: list[str] = []
    for s in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (s.string or s.get_text() or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if isinstance(t, list):
                types.extend(str(x) for x in t)
            elif t:
                types.append(str(t))
    return types


def audit_website(url: Optional[str], timeout: float = 12.0) -> dict:
    """Audit SEO complet d'un site web. Retourne un dict avec score + findings."""
    findings: list[dict] = []
    metrics: dict = {}

    if not url or not url.strip():
        findings.append(_finding(
            "critical", "Aucun site web identifié",
            "L'entreprise n'a pas de site web référencé sur Google Maps.",
            "Création d'un site vitrine optimisé SEO est l'opportunité commerciale n°1.",
        ))
        return {"ok": False, "url": None, "score": 0, "findings": findings, "metrics": metrics}

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # 1) Récupération de la page
    t0 = time.time()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True,
                          headers={"User-Agent": USER_AGENT,
                                   "Accept-Language": "fr-BE,fr;q=0.9"}) as client:
            r = client.get(url)
    except Exception as e:
        findings.append(_finding(
            "critical", "Site web inaccessible",
            f"Impossible d'accéder au site : {e}",
            "Vérifier l'hébergement, le DNS et le certificat SSL.",
        ))
        return {"ok": False, "url": url, "score": 0, "findings": findings, "metrics": metrics}

    dt_ms = int((time.time() - t0) * 1000)
    metrics["response_time_ms"] = dt_ms
    metrics["status_code"] = r.status_code
    metrics["final_url"] = str(r.url)
    metrics["page_size_kb"] = round(len(r.content) / 1024, 1)

    if r.status_code >= 400:
        findings.append(_finding(
            "critical", f"Erreur HTTP {r.status_code}",
            f"Le site renvoie un statut {r.status_code} sur la page d'accueil.",
            "Diagnostiquer le problème technique (hébergement, configuration).",
        ))
        return {"ok": False, "url": url, "score": 0, "findings": findings, "metrics": metrics}

    # 2) HTTPS
    is_https = metrics["final_url"].startswith("https://")
    metrics["https"] = is_https
    if not is_https:
        findings.append(_finding(
            "critical", "Pas de HTTPS",
            "Le site n'utilise pas HTTPS — Google pénalise et les navigateurs affichent un avertissement.",
            "Activer un certificat SSL (Let's Encrypt est gratuit).",
        ))
    else:
        findings.append(_finding("ok", "HTTPS actif", "Connexion sécurisée."))

    # 3) Temps de réponse
    if dt_ms > 3000:
        findings.append(_finding(
            "critical", f"Temps de réponse lent ({dt_ms} ms)",
            "Le site répond en plus de 3 secondes — gros impact sur le SEO et la conversion.",
            "Optimiser l'hébergement, activer la mise en cache, utiliser un CDN.",
        ))
    elif dt_ms > 1500:
        findings.append(_finding(
            "warning", f"Temps de réponse moyen ({dt_ms} ms)",
            "Recommandé : moins de 1,5 s pour la page d'accueil.",
            "Audit performance + optimisation images/scripts.",
        ))
    else:
        findings.append(_finding("ok", f"Temps de réponse rapide ({dt_ms} ms)"))

    soup = BeautifulSoup(r.text, "html.parser")

    # 4) Balise title
    title_el = soup.find("title")
    title_text = (title_el.get_text() if title_el else "").strip()
    metrics["title"] = title_text
    metrics["title_length"] = len(title_text)
    if not title_text:
        findings.append(_finding(
            "critical", "Pas de balise <title>",
            "La balise <title> est absente ou vide — c'est l'élément SEO le plus important.",
            "Ajouter une balise title de 50-60 caractères : métier + ville + nom.",
        ))
    elif len(title_text) < 25:
        findings.append(_finding(
            "warning", f"Title trop court ({len(title_text)} caractères)",
            f"« {title_text} »",
            "Allonger à 50-60 caractères en incluant les mots-clés métier + ville.",
        ))
    elif len(title_text) > 65:
        findings.append(_finding(
            "warning", f"Title trop long ({len(title_text)} caractères)",
            "Sera tronqué par Google dans les résultats de recherche.",
            "Raccourcir à 55-60 caractères max.",
        ))
    else:
        findings.append(_finding("ok", f"Title correct ({len(title_text)} caractères)",
                                 f"« {title_text} »"))

    # 5) Meta description
    desc_el = soup.find("meta", attrs={"name": re.compile(r"^description$", re.IGNORECASE)})
    desc_text = (desc_el.get("content") if desc_el else "" or "").strip()
    metrics["meta_description"] = desc_text
    metrics["meta_description_length"] = len(desc_text)
    if not desc_text:
        findings.append(_finding(
            "critical", "Pas de meta description",
            "Aucune meta description — Google génère un extrait au hasard, mauvais pour le taux de clic.",
            "Ajouter une meta description de 120-160 caractères avec un appel à l'action.",
        ))
    elif len(desc_text) < 70:
        findings.append(_finding(
            "warning", f"Meta description trop courte ({len(desc_text)} caractères)",
            recommendation="Allonger à 120-160 caractères.",
        ))
    elif len(desc_text) > 170:
        findings.append(_finding(
            "warning", f"Meta description trop longue ({len(desc_text)} caractères)",
            "Sera tronquée dans les résultats.",
            "Raccourcir à 150-160 caractères.",
        ))
    else:
        findings.append(_finding("ok", f"Meta description correcte ({len(desc_text)} caractères)"))

    # 6) H1
    h1s = soup.find_all("h1")
    metrics["h1_count"] = len(h1s)
    if not h1s:
        findings.append(_finding(
            "critical", "Aucune balise H1",
            "Pas de titre principal H1 — Google ne sait pas quel est le sujet de la page.",
            "Ajouter une seule H1 reprenant les mots-clés principaux + ville.",
        ))
    elif len(h1s) > 1:
        findings.append(_finding(
            "warning", f"{len(h1s)} balises H1 sur la page",
            "Plusieurs H1 dilue le signal SEO (recommandé : 1 seule).",
            "Convertir les H1 secondaires en H2.",
        ))
    else:
        h1_text = h1s[0].get_text(strip=True)[:120]
        findings.append(_finding("ok", "H1 unique présente", f"« {h1_text} »"))

    # 7) Structure de titres (H2, H3)
    metrics["h2_count"] = len(soup.find_all("h2"))
    metrics["h3_count"] = len(soup.find_all("h3"))
    if metrics["h2_count"] == 0:
        findings.append(_finding(
            "warning", "Pas de balises H2",
            "Page sans sous-titres — structure pauvre pour le SEO et la lisibilité.",
            "Structurer le contenu en sections avec des H2.",
        ))

    # 8) Viewport (mobile-friendly)
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.IGNORECASE)})
    if not viewport:
        findings.append(_finding(
            "critical", "Site non responsive (pas de meta viewport)",
            "Le site n'est pas optimisé pour mobile — pénalité Google Mobile-First Index.",
            "Ajouter <meta name='viewport' content='width=device-width, initial-scale=1'>.",
        ))
    else:
        findings.append(_finding("ok", "Site responsive (meta viewport présent)"))

    # 9) Lang
    html_el = soup.find("html")
    lang = html_el.get("lang") if html_el else None
    metrics["lang"] = lang
    if not lang:
        findings.append(_finding(
            "warning", "Attribut lang manquant",
            "L'attribut lang sur <html> n'est pas défini.",
            "Ajouter lang='fr-BE' sur la balise <html>.",
        ))

    # 10) Canonical URL
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if not canonical:
        findings.append(_finding(
            "warning", "Pas de balise canonical",
            "URL canonique non définie — risque de duplicate content.",
            "Ajouter <link rel='canonical' href='...'>.",
        ))
    else:
        findings.append(_finding("ok", "Balise canonical présente"))

    # 11) Images alt
    imgs = soup.find_all("img")
    imgs_no_alt = [i for i in imgs if not (i.get("alt") or "").strip()]
    metrics["images_total"] = len(imgs)
    metrics["images_without_alt"] = len(imgs_no_alt)
    if imgs:
        ratio = len(imgs_no_alt) / len(imgs)
        if ratio > 0.5:
            findings.append(_finding(
                "warning", f"{len(imgs_no_alt)}/{len(imgs)} images sans attribut alt",
                "Mauvais pour le SEO et l'accessibilité.",
                "Ajouter un texte alt descriptif sur chaque image.",
            ))
        elif ratio > 0:
            findings.append(_finding(
                "ok", f"{len(imgs) - len(imgs_no_alt)}/{len(imgs)} images avec alt",
                f"{len(imgs_no_alt)} images sans alt restent à corriger.",
            ))
        else:
            findings.append(_finding("ok", f"Toutes les images ({len(imgs)}) ont un attribut alt"))

    # 12) Schema.org
    schema_types = _parse_schema_types(soup)
    metrics["schema_types"] = schema_types
    business_schemas = {"LocalBusiness", "Organization", "Store", "ProfessionalService",
                       "Optician", "Restaurant", "Dentist", "AutoRepair"}
    has_business = any(t in business_schemas or "Business" in t or "Service" in t
                       for t in schema_types)
    if not schema_types:
        findings.append(_finding(
            "warning", "Pas de balisage Schema.org",
            "Aucune donnée structurée détectée (JSON-LD).",
            "Ajouter un schema LocalBusiness pour booster le SEO local.",
        ))
    elif not has_business:
        findings.append(_finding(
            "warning", "Schema.org présent mais pas LocalBusiness",
            f"Types détectés : {', '.join(schema_types[:5])}",
            "Ajouter un schema LocalBusiness avec nom, adresse, téléphone, horaires.",
        ))
    else:
        findings.append(_finding(
            "ok", "Schema.org LocalBusiness détecté",
            f"Types : {', '.join(schema_types[:5])}",
        ))

    # 13) robots.txt
    parsed = urlparse(metrics["final_url"])
    root = f"{parsed.scheme}://{parsed.netloc}"
    if _check_url(urljoin(root, "/robots.txt")):
        findings.append(_finding("ok", "robots.txt présent"))
    else:
        findings.append(_finding(
            "warning", "Pas de robots.txt",
            recommendation="Créer un robots.txt à la racine pour piloter le crawl.",
        ))

    # 14) sitemap.xml
    if _check_url(urljoin(root, "/sitemap.xml")):
        findings.append(_finding("ok", "sitemap.xml présent"))
    else:
        findings.append(_finding(
            "warning", "Pas de sitemap.xml",
            recommendation="Générer un sitemap.xml et le déclarer dans Google Search Console.",
        ))

    # 15) Word count
    body_text = soup.get_text(separator=" ", strip=True)
    word_count = len(body_text.split())
    metrics["word_count"] = word_count
    if word_count < 250:
        findings.append(_finding(
            "warning", f"Page peu textuelle ({word_count} mots)",
            "Une homepage avec moins de 250 mots a peu de chance de bien ranker.",
            "Étoffer le contenu (services, zones d'intervention, FAQ).",
        ))
    elif word_count > 2500:
        findings.append(_finding(
            "ok", f"Contenu riche ({word_count} mots)",
            "Beaucoup de texte — vérifier qu'il reste lisible.",
        ))
    else:
        findings.append(_finding("ok", f"Volume de texte correct ({word_count} mots)"))

    # 16) Open Graph
    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_image = soup.find("meta", attrs={"property": "og:image"})
    if not og_title or not og_image:
        findings.append(_finding(
            "warning", "Open Graph incomplet",
            "Tags og:title et/ou og:image manquants — partages sociaux peu attrayants.",
            "Ajouter og:title, og:description, og:image.",
        ))
    else:
        findings.append(_finding("ok", "Open Graph présent"))

    # Score (100 - pénalités)
    score = 100
    for f in findings:
        if f["severity"] == "critical":
            score -= 12
        elif f["severity"] == "warning":
            score -= 4
    score = max(0, score)

    return {
        "ok": True,
        "url": url,
        "score": score,
        "findings": findings,
        "metrics": metrics,
    }

"""Génération d'un rapport SEO/GEO via IA suivant la structure stricte Media Fast.

Le rapport produit suit EXACTEMENT le format demandé :
- POINTS FORTS (max 3 puces)
- POINTS FAIBLES (max 3 puces) — l'audit doit accentuer les points perfectibles
  (80 % manques, 20 % positifs)
- PRÉSENCE LOCALE — DIAGNOSTIC
- PAGES LOCALES À CRÉER (tableau service × commune)
- TOP 10 MOTS-CLÉS LONGUE TRAÎNE
- PLAN D'ACTION (max 5 actions avec emojis colorés)

Utilise les mêmes providers que ai_briefing : OpenAI prioritaire, Anthropic
fallback. Aucune clé configurée → on retourne une erreur exploitable côté UI.
"""

import os
from typing import Optional

import httpx


# ============================================================================
# SYSTEM PROMPT — Format strict Media Fast (exact tel que demandé)
# ============================================================================

SYSTEM_PROMPT = """Tu es un expert SEO/GEO de l'agence Media Fast. Tu produis des
rapports d'audit selon une structure stricte et invariable.

L'audit du site accentue toujours les points perfectibles : 80 % manques,
20 % positifs. Sois critique mais constructif.

Le rapport suit TOUJOURS cette structure. Aucune section supplémentaire.
Aucun développement long.

Commence par :
**Audit SEO & GEO — [Nom du site] — Réalisé par Media Fast**

---

### POINTS FORTS (max 3 puces)
- Une ligne par point. Factuel, court.

### POINTS FAIBLES (max 3 puces)
- Une ligne par point. Ce qui pénalise le site aujourd'hui.

### PRÉSENCE LOCALE — DIAGNOSTIC
Répondre en 3 à 5 lignes maximum :
- Le site a-t-il des pages locales ? (oui / non / partiellement)
- Les communes du rayon cible sont-elles couvertes ?
- Le NAP (nom, adresse, téléphone) est-il visible et cohérent ?
- Y a-t-il des données structurées LocalBusiness ? (oui / non / à ajouter)

### PAGES LOCALES À CRÉER (règle : 1 page = 1 service + 1 commune)
Tableau uniquement, sans commentaires :

| Page à créer | Mot-clé cible | Commune |
|---|---|---|
| /service-commune | service + commune | Commune |

Proposer entre 5 et 10 pages selon le rayon fourni. Communes = celles du
rayon géographique indiqué.

### TOP 10 MOTS-CLÉS LONGUE TRAÎNE
Liste numérotée, une ligne par mot-clé, avec volume estimé
(faible / moyen / fort) en Belgique francophone. Aucun commentaire
supplémentaire.

Top 10 des mots clés puissants les plus souvent tapés dans la barre de
recherche Google en rapport avec son activité. Si le professionnel propose
un service de niche, n'indique pas de mot clé niché mais uniquement ceux
souvent tapés dans Google.

### PLAN D'ACTION (max 5 actions)
Format strict :
🔴 1. [Action courte] — Impact : Fort
🟠 2. [Action courte] — Impact : Fort
🟡 3. [Action courte] — Impact : Moyen
🟢 4. [Action courte] — Impact : Moyen
🔵 5. [Action courte] — Impact : Faible

---

Terminer par :
*Rapport réalisé par Media Fast — contact@media-fast.be*

---

## RÈGLES ABSOLUES

- Rapport court : aucune introduction, aucune conclusion rédigée, aucun
  paragraphe explicatif
- Langue : français uniquement
- Ne jamais générer de code JSON-LD ou Schema.org : signaler uniquement
  ce qui manque
- Si une donnée est invérifiable : écrire « Non détecté »
- Tous les sites sont basés en Belgique
- Si le site est en néerlandais : analyser en NL, rédiger le rapport en
  français"""


# ============================================================================
# Provider detection (réutilise même logique qu'ai_briefing)
# ============================================================================

def _provider() -> Optional[str]:
    forced = os.environ.get("AI_BRIEFING_PROVIDER", "").strip().lower()
    if forced in ("openai", "anthropic"):
        if forced == "openai" and os.environ.get("OPENAI_API_KEY"):
            return "openai"
        if forced == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def is_configured() -> bool:
    return _provider() is not None


# ============================================================================
# Prompt builder (données entreprise + audit technique → user prompt)
# ============================================================================

def _build_user_prompt(business: dict, web_audit: dict, gmb_audit: dict) -> str:
    """Construit le user prompt en consolidant les données business + audit."""
    name = (business.get("name") or "—").strip()
    website = (business.get("website") or "Non détecté").strip()
    city = (business.get("city") or business.get("locality") or "—").strip()
    postal = (business.get("postal_code") or "").strip()
    category = (business.get("category") or "—").strip()
    address = (business.get("address") or "Non détecté").strip()
    phone = (business.get("phone") or "Non détecté").strip()

    # Communes du rayon (15 km) pour les pages locales à créer
    radius_communes: list[str] = []
    try:
        from data.geo import communes_within_radius
        rs = communes_within_radius(city, 15)
        radius_communes = [c for c, _ in rs[:15]]
    except Exception:
        pass
    if not radius_communes:
        radius_communes = [city] if city != "—" else []

    # Findings techniques du site (forme concise)
    metrics = (web_audit or {}).get("metrics", {}) or {}
    findings = (web_audit or {}).get("findings", []) or []
    critical = [f for f in findings if f.get("severity") == "critical"]
    warnings = [f for f in findings if f.get("severity") == "warning"]
    oks = [f for f in findings if f.get("severity") == "ok"]

    def _bullet_list(items, attr="title", limit=10):
        if not items:
            return "— Aucun"
        return "\n".join(f"- {f.get(attr, '')}" for f in items[:limit])

    # GMB metrics (rating, reviews)
    rating = business.get("rating") or "—"
    reviews = business.get("reviews_count") or 0

    return f"""Analyse le site web suivant et génère le rapport d'audit SEO/GEO
selon le format strict défini.

═══ ENTREPRISE ═══
- Nom : {name}
- Site web : {website}
- Ville : {city}{f' ({postal})' if postal else ''}
- Catégorie : {category}
- Adresse : {address}
- Téléphone : {phone}
- Note Google : {rating}/5 ({reviews} avis)

═══ COMMUNES DU RAYON (15 km autour de {city}) ═══
{', '.join(radius_communes) if radius_communes else 'Non détecté'}

Utilise ces communes pour proposer les PAGES LOCALES À CRÉER (1 page =
1 service de l'entreprise × 1 commune du rayon).

═══ DONNÉES TECHNIQUES DU SITE (relevées automatiquement) ═══
- HTTPS : {'oui' if metrics.get('https') else 'NON — pénalisant'}
- Temps de réponse : {metrics.get('response_time_ms', 'Non détecté')} ms
- Title : « {metrics.get('title', 'Non détecté')[:80]} » ({metrics.get('title_length', 0)} car.)
- Meta description : {metrics.get('meta_description_length', 0)} caractères
- Balises H1 : {metrics.get('h1_count', 0)}
- Balises H2 : {metrics.get('h2_count', 0)}
- Mots dans la page : {metrics.get('word_count', 0)}
- Schema.org détecté : {', '.join(metrics.get('schema_types', [])) or 'AUCUN'}
- Lang attribute : {metrics.get('lang') or 'Non détecté'}
- Images sans alt : {metrics.get('images_without_alt', 0)}/{metrics.get('images_total', 0)}

═══ POINTS CRITIQUES TECHNIQUES ═══
{_bullet_list(critical, limit=8)}

═══ POINTS À AMÉLIORER ═══
{_bullet_list(warnings, limit=8)}

═══ POINTS POSITIFS DÉTECTÉS ═══
{_bullet_list(oks, limit=6)}

═══ INSTRUCTION ═══
Génère MAINTENANT le rapport SELON LE FORMAT STRICT (POINTS FORTS / POINTS
FAIBLES / PRÉSENCE LOCALE / PAGES LOCALES table / TOP 10 MOTS-CLÉS /
PLAN D'ACTION). Réponse en markdown pur, aucun bloc de code, aucune
introduction, aucune conclusion en dehors du format imposé."""


# ============================================================================
# Provider calls
# ============================================================================

def _call_openai(user_prompt: str) -> dict:
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2200,
                },
            )
        if r.status_code != 200:
            return {"ok": False, "report": "",
                    "message": f"OpenAI {r.status_code} : {r.text[:240]}"}
        content = r.json()["choices"][0]["message"]["content"]
        return {"ok": True, "report": content.strip(),
                "message": f"Rapport généré ({model})", "provider": "openai"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "report": "", "message": f"Erreur OpenAI : {e}"}


def _call_anthropic(user_prompt: str) -> dict:
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 2200,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.3,
                },
            )
        if r.status_code != 200:
            return {"ok": False, "report": "",
                    "message": f"Anthropic {r.status_code} : {r.text[:240]}"}
        content = r.json()["content"][0]["text"]
        return {"ok": True, "report": content.strip(),
                "message": f"Rapport généré ({model})", "provider": "anthropic"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "report": "", "message": f"Erreur Anthropic : {e}"}


# ============================================================================
# Public API
# ============================================================================

def generate_seo_report(business: dict, web_audit: dict, gmb_audit: dict) -> dict:
    """Génère le rapport SEO/GEO structuré pour la fiche entreprise.

    Returns:
        {
            "ok": bool,
            "report": str,            # markdown du rapport (vide si ok=False)
            "message": str,
            "provider": str | None,   # "openai" / "anthropic" / None
        }
    """
    p = _provider()
    if not p:
        return {
            "ok": False, "report": "",
            "message": "Aucune clé IA configurée (OPENAI_API_KEY ou "
                       "ANTHROPIC_API_KEY). Rapport SEO non généré.",
            "provider": None,
        }

    user_prompt = _build_user_prompt(business, web_audit, gmb_audit)
    result = _call_openai(user_prompt) if p == "openai" else _call_anthropic(user_prompt)
    result["provider"] = p
    return result

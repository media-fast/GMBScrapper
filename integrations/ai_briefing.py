"""Briefing pré-appel IA pour commerciaux d'agence SEO/GEO/visibilité.

Supporte deux providers :
  - OpenAI       : OPENAI_API_KEY (modèle par défaut : gpt-4o-mini)
  - Anthropic    : ANTHROPIC_API_KEY (modèle par défaut : claude-haiku-4-5-20251001)

Si les deux clés sont définies, OpenAI est prioritaire (gpt-4o-mini est ~2x moins cher
et un peu plus rapide pour cette tâche). Pour forcer Anthropic, on peut définir :
  AI_BRIEFING_PROVIDER=anthropic
"""

import json
import os
from typing import Optional

import httpx


SYSTEM_PROMPT = """Tu es l'assistant d'un commercial d'une agence web spécialisée dans :
- Référencement SEO (audit, stratégie de mots-clés, optimisation on-page, netlinking)
- Référencement local / GEO (Google Business Profile, citations locales, avis)
- Création et refonte de sites web optimisés SEO
- Stratégie de visibilité globale (réseaux sociaux, contenu, presse en ligne)
- Suivi de positionnement et reporting

Le commercial appelle des entreprises B2B en Belgique pour leur proposer ces services.

Ta mission : générer un briefing pré-appel court, factuel et actionnable à partir des données fournies.

Règles strictes :
- N'INVENTE AUCUN chiffre, date, dirigeant, technologie ou fait qui n'est pas explicitement dans les données
- Si une donnée est absente, ne fais aucune spéculation à son sujet
- Identifie les VRAIES opportunités SEO/GEO/visibilité depuis les données :
    * Pas de site web → opportunité majeure (création + GBP)
    * Note Google faible ou peu d'avis → travail réputation locale
    * Site web mais activité offline forte (commerce local) → optimisation GEO
    * Ancienneté + bonne note → autorité locale à exploiter en SEO
    * Effectif important → potentiel de budget marketing
- Le ton du briefing est factuel et concis ; l'opener est conversationnel et naturel
- Ne jamais nommer un concurrent réel ni inventer une référence cliente
- Le résultat est en français de Belgique, sans anglicismes inutiles

Tu dois répondre UNIQUEMENT par un objet JSON valide, sans markdown ni explication."""


USER_PROMPT_TEMPLATE = """Génère un briefing pré-appel pour cette entreprise.

DONNÉES ENTREPRISE :
- Nom : {name}
- Catégorie : {category}
- Localité : {locality} ({postal_code})
- Adresse : {address}
- Téléphone : {phone}
- Site web : {website}
- Note Google : {rating} / 5  ({reviews_count} avis)
- Année de création : {creation_date}
- Forme juridique : {legal_form}
- Dirigeant(s) : {managers}
- N° TVA : {vat_number}
- Activités (codes NACE) : {nace_activities}
- Chiffre d'affaires : {nbb_revenue}
- Effectif : {nbb_employees}

Réponds par ce JSON exact :
{{
  "synthesis": "Une phrase de 15 à 25 mots résumant l'entreprise et son profil web/visibilité actuel.",
  "opportunities": [
    "Opportunité SEO/GEO/visibilité n°1 (1 phrase, factuelle, ancrée sur les données).",
    "Opportunité n°2 (1 phrase).",
    "Opportunité n°3 (1 phrase)."
  ],
  "talking_points": [
    "Accroche commerciale n°1 (1 phrase, lien direct avec nos services).",
    "Accroche n°2 (1 phrase).",
    "Accroche n°3 (1 phrase)."
  ],
  "opener": "Phrase d'ouverture téléphonique naturelle, contextualisée à cette entreprise, 25-35 mots."
}}"""


# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

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


def provider_label() -> str:
    p = _provider()
    if p == "openai":
        return f"OpenAI ({os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')})"
    if p == "anthropic":
        return f"Anthropic ({os.environ.get('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')})"
    return "non configuré"


# ---------------------------------------------------------------------------
# Business data normalization
# ---------------------------------------------------------------------------

def _safe(value, default: str = "—") -> str:
    if value in (None, "", 0, "0"):
        return default
    return str(value).strip()


def _build_prompt(business: dict) -> str:
    return USER_PROMPT_TEMPLATE.format(
        name=_safe(business.get("name")),
        category=_safe(business.get("category")),
        locality=_safe(business.get("locality") or business.get("city")),
        postal_code=_safe(business.get("postal_code")),
        address=_safe(business.get("address")),
        phone=_safe(business.get("phone")),
        website=_safe(business.get("website"), "PAS DE SITE WEB IDENTIFIÉ"),
        rating=_safe(business.get("rating")),
        reviews_count=_safe(business.get("reviews_count"), "0"),
        creation_date=_safe(business.get("creation_date")),
        legal_form=_safe(business.get("legal_form")),
        managers=_safe(business.get("managers")),
        vat_number=_safe(business.get("vat_number")),
        nace_activities=_safe(business.get("nace_activities")),
        nbb_revenue=_safe(business.get("nbb_revenue")),
        nbb_employees=_safe(business.get("nbb_employees")),
    )


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def _call_openai(user_prompt: str) -> dict:
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        with httpx.Client(timeout=40.0) as client:
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
                    "response_format": {"type": "json_object"},
                    "temperature": 0.55,
                    "max_tokens": 900,
                },
            )
        if r.status_code != 200:
            return {"ok": False, "briefing": None,
                    "message": f"OpenAI {r.status_code}: {r.text[:200]}"}
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return {"ok": True, "briefing": json.loads(content),
                "message": f"Briefing généré ({model})", "provider": "openai"}
    except json.JSONDecodeError as e:
        return {"ok": False, "briefing": None,
                "message": f"OpenAI a renvoyé du JSON invalide : {e}"}
    except Exception as e:
        return {"ok": False, "briefing": None, "message": f"Erreur OpenAI : {e}"}


def _strip_md_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _call_anthropic(user_prompt: str) -> dict:
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    try:
        with httpx.Client(timeout=40.0) as client:
            r = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 900,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.55,
                },
            )
        if r.status_code != 200:
            return {"ok": False, "briefing": None,
                    "message": f"Anthropic {r.status_code}: {r.text[:200]}"}
        data = r.json()
        content = data["content"][0]["text"]
        content = _strip_md_fences(content)
        return {"ok": True, "briefing": json.loads(content),
                "message": f"Briefing généré ({model})", "provider": "anthropic"}
    except json.JSONDecodeError as e:
        return {"ok": False, "briefing": None,
                "message": f"Anthropic a renvoyé du JSON invalide : {e}"}
    except Exception as e:
        return {"ok": False, "briefing": None, "message": f"Erreur Anthropic : {e}"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_briefing(business: dict) -> dict:
    """Génère un briefing pré-appel pour le commercial.

    Returns: {"ok": bool, "briefing": dict | None, "message": str, "provider": str}
        briefing = {"synthesis", "opportunities", "talking_points", "opener"}
    """
    p = _provider()
    if not p:
        return {"ok": False, "briefing": None,
                "message": "Aucune clé IA configurée (OPENAI_API_KEY ou ANTHROPIC_API_KEY).",
                "provider": None}
    user_prompt = _build_prompt(business)
    if p == "openai":
        return _call_openai(user_prompt)
    return _call_anthropic(user_prompt)

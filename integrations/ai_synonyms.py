"""Suggestion IA de variantes pour les métiers personnalisés.

Quand l'utilisateur tape un métier custom (ex. "magasin de vélos électriques")
non présent dans le dict METIER_SYNONYMS statique, on appelle une IA
(OpenAI ou Anthropic) pour proposer 3-6 variantes/synonymes plausibles à
chercher sur Google Maps.

L'IA est briefée pour rester strictement dans le registre commercial
(noms de catégories de business existant réellement sur GMB), en français
de Belgique, sans inventer de termes farfelus.

Mêmes providers que ai_briefing : OpenAI prioritaire, Anthropic fallback.
"""

import json
import os
from typing import Optional

import httpx


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Tu es un expert en marketing local et en référencement Google Maps en Belgique.

Ton rôle : proposer des SYNONYMES ou VARIANTES de requête Google Maps pour un métier donné,
afin d'élargir le scope d'un scraping commercial B2B (prospection).

RÈGLES STRICTES :
- Tes variantes doivent correspondre à des CATÉGORIES réelles qu'un utilisateur taperait
  sur Google Maps en Belgique (français).
- N'invente JAMAIS de termes : reste dans le vocabulaire commercial courant.
- Évite les redondances triviales (pluriel/singulier, féminin/masculin).
- Inclus 1-2 termes plus génériques (catégorie large) ET 1-2 termes plus spécifiques si pertinent.
- Maximum 6 variantes au total, le métier d'origine inclus.
- Reste en français de Belgique (pas d'anglicismes inutiles, mais accepte ceux d'usage : "fitness", "coworking").
- Si le métier est déjà très spécifique (ex. "vendeur de pétanque artisanale"), il vaut mieux 2-3 variantes pertinentes que 6 forcées.

Tu réponds UNIQUEMENT par un objet JSON valide, sans markdown ni explication.

Format :
{
  "variants": ["métier d'origine", "variante 1", "variante 2", ...]
}"""


USER_PROMPT_TEMPLATE = (
    "Métier à étendre : « {metier} »\n\n"
    "Propose 3 à 6 variantes Google Maps pour ce métier, "
    "en commençant par le métier d'origine."
)


# ---------------------------------------------------------------------------
# Provider detection (réutilise la même logique que ai_briefing)
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
# Provider calls
# ---------------------------------------------------------------------------

def _strip_md_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _call_openai(user_prompt: str) -> dict:
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        with httpx.Client(timeout=20.0) as client:
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
                    "temperature": 0.4,
                    "max_tokens": 250,
                },
            )
        if r.status_code != 200:
            return {"ok": False, "variants": [], "message": f"OpenAI {r.status_code}: {r.text[:200]}"}
        content = r.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
        return {"ok": True, "variants": payload.get("variants", []), "message": f"Variantes générées ({model})"}
    except json.JSONDecodeError as e:
        return {"ok": False, "variants": [], "message": f"OpenAI JSON invalide : {e}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "variants": [], "message": f"Erreur OpenAI : {e}"}


def _call_anthropic(user_prompt: str) -> dict:
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 250,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.4,
                },
            )
        if r.status_code != 200:
            return {"ok": False, "variants": [], "message": f"Anthropic {r.status_code}: {r.text[:200]}"}
        content = _strip_md_fences(r.json()["content"][0]["text"])
        payload = json.loads(content)
        return {"ok": True, "variants": payload.get("variants", []), "message": f"Variantes générées ({model})"}
    except json.JSONDecodeError as e:
        return {"ok": False, "variants": [], "message": f"Anthropic JSON invalide : {e}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "variants": [], "message": f"Erreur Anthropic : {e}"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest_variants(metier: str) -> dict:
    """Propose des variantes Google Maps pour un métier custom.

    Returns:
        {
            "ok": bool,
            "variants": list[str],   # premier = métier d'origine
            "message": str,
            "provider": str | None,
        }
    """
    metier = (metier or "").strip()
    if not metier:
        return {"ok": False, "variants": [], "message": "Métier vide.", "provider": None}

    p = _provider()
    if not p:
        return {
            "ok": False, "variants": [],
            "message": "Aucune clé IA configurée (OPENAI_API_KEY ou ANTHROPIC_API_KEY).",
            "provider": None,
        }

    user_prompt = USER_PROMPT_TEMPLATE.format(metier=metier)
    result = _call_openai(user_prompt) if p == "openai" else _call_anthropic(user_prompt)
    result["provider"] = p

    # Sanity check : on ne garde que des strings, dédup case-insensitive,
    # et on garantit que le métier d'origine est inclus en première position.
    raw = result.get("variants", [])
    cleaned: list[str] = []
    seen_lower: set[str] = set()
    for v in raw:
        if not isinstance(v, str):
            continue
        v_clean = v.strip()
        if not v_clean:
            continue
        low = v_clean.lower()
        if low in seen_lower:
            continue
        seen_lower.add(low)
        cleaned.append(v_clean)

    # Force le métier d'origine en première position (s'il n'y est pas)
    if metier.lower() not in seen_lower:
        cleaned.insert(0, metier)
    elif cleaned and cleaned[0].lower() != metier.lower():
        # Le déplacer en tête s'il n'y est pas déjà
        cleaned = [v for v in cleaned if v.lower() != metier.lower()]
        cleaned.insert(0, metier)

    result["variants"] = cleaned[:6]
    return result

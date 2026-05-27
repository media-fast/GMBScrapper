"""Rapport crédit IA approfondi (Phase 2).

Génère un verdict argumenté de solvabilité d'une entreprise belge en
appelant un LLM (OpenAI ou Anthropic) avec :
  - Les métadonnées entreprise (nom, BCE, statut, ancienneté, dirigeants)
  - Les données BNB structurées du dernier dépôt (codes 10/15, 17/49, 9904,
    70, etc.) si disponibles via l'API CBSO `accountingData`
  - Le score heuristique déjà calculé (Phase 1) pour contextualiser

Le LLM produit un rapport markdown structuré (verdict + ratios + plafond
crédit conseillé + recommandations).

Aucune clé API → on retourne une erreur exploitable côté UI. Si la clé
NBB_API_KEY n'est pas définie ou si l'endpoint accountingData ne renvoie
rien, on tombe en mode dégradé (analyse basée uniquement sur les
métadonnées + heuristique — moins précis mais utilisable).
"""

import json
import os
import uuid
from typing import Optional

import httpx


# ============================================================================
# SYSTEM PROMPT — méthodologie credit-analysis-belgium-b2b
# ============================================================================
# Format structuré inspiré de la skill Anthropic credit-analysis-belgium-b2b,
# adapté pour les PME/TPE belges. Verdict baromètre rouge/orange/jaune/vert
# + analyse chiffrée + plafond crédit + recommandation paiement.

SYSTEM_PROMPT = """Tu es analyste crédit B2B chez Media Fast, spécialisé
dans l'évaluation de la solvabilité des TPE/PME belges à partir de leurs
comptes annuels déposés à la BNB (Banque Nationale de Belgique).

Tu produis un rapport COURT et STRUCTURÉ qui aide un commercial à décider
s'il peut accorder un crédit / un paiement différé à un prospect.

## STRUCTURE STRICTE DU RAPPORT (toujours dans cet ordre)

Commence par :
**Analyse crédit — [Nom de l'entreprise] — Réalisé par Media Fast**

---

### VERDICT
Une ligne unique avec la couleur baromètre + libellé :
🔴 **MAUVAIS PAYEUR** / 🟠 **À RISQUE** / 🟡 **À SURVEILLER** /
🟢 **BON PAYEUR** / ⚪ **DONNÉES INSUFFISANTES**

Puis une phrase de 1-2 lignes qui résume le pourquoi du verdict.

### RATIOS CLÉS
Tableau markdown des ratios disponibles :

| Ratio | Valeur | Lecture |
|---|---|---|
| Solvabilité (capitaux propres / total bilan) | XX % | Bonne / Limite / Faible |
| Liquidité (actif circulant / dettes CT) | X.XX | Bonne / Limite / Faible |
| Résultat exercice | XXX K€ | Bénéfice / Perte |
| Évolution résultat (3 ans) | ↑ / ↓ / = | Tendance |

Si une donnée est absente : écrire « Non disponible » dans la colonne Valeur.

### SIGNAUX D'ALERTE
Liste à puces (max 4) des signaux concrets observés :
- Capitaux propres négatifs / faibles
- Dépôts en retard à la BNB
- Pertes répétées sur plusieurs exercices
- Statut BCE en cessation / faillite / liquidation
- Délai de paiement fournisseurs anormalement long

Si aucun signal d'alerte significatif : écrire « Aucun signal d'alerte
critique identifié. »

### RECOMMANDATION COMMERCIALE
3 lignes maximum :
- **Plafond crédit conseillé** : XXX € (ou « 0 € — prépaiement obligatoire »)
- **Délai paiement conseillé** : Comptant / 30 jours / 45 jours / 60 jours
- **Action** : 1 phrase concrète (ex : « Demander un acompte de 50 % »)

---

Terminer par :
*Rapport crédit Media Fast — contact@media-fast.be — Analyse heuristique,
ne remplace pas une étude crédit professionnelle.*

---

## RÈGLES ABSOLUES

- Rapport court : aucun paragraphe rédigé, aucune intro, aucune conclusion
  en dehors du format imposé
- Langue : français uniquement
- Si un ratio chiffré est invérifiable : écrire « Non disponible » dans
  la colonne Valeur du tableau RATIOS CLÉS — c'est OK, on ne pénalise PAS
  l'entreprise pour ça
- ⚠ Le verdict ⚪ DONNÉES INSUFFISANTES est RÉSERVÉ aux cas où on n'a
  STRICTEMENT AUCUNE info exploitable (ni dépôts BNB, ni statut, ni âge).
  Si on a juste les MÉTADONNÉES des dépôts (année, date, nombre, modèle)
  sans les ratios chiffrés, c'est suffisant pour conclure :
    * Dépôts récents + réguliers (≥3 dépôts, dernier <18 mois) → 🟢 BON
      PAYEUR (« filing discipline » = bon indicateur de fiabilité, même
      sans voir les ratios)
    * Dépôts à jour mais peu nombreux ou jeune entreprise → 🟡 À
      SURVEILLER
    * Dépôts en retard (>24 mois) ou aucun → 🟠 À RISQUE
    * Statut cessé / faillite → 🔴 MAUVAIS PAYEUR
- Quand les ratios sont absents, justifie le verdict dans la phrase de
  résumé en t'appuyant sur la régularité des dépôts (ex : « 42 dépôts
  successifs, dernier exercice 2024 déposé en juillet 2025 → discipline
  administrative forte »)
- Sois CONSERVATEUR : en cas de doute, durcis le verdict (mieux vaut
  rater une affaire qu'un impayé)
- Tous les montants en EUR, formatés FR (espace insécable comme séparateur
  de milliers)
- Aucune mention de l'IA / GPT / Claude / Anthropic / OpenAI dans le rapport
"""


# ============================================================================
# Provider detection (réutilise la même logique qu'ai_seo_report)
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
# Fetch des données comptables BNB (best effort)
# ============================================================================

NBB_API_BASE = "https://ws.cbso.nbb.be/authentic/legalEntity/"

# Codes BNB usuels pour un mini-bilan (modèle abrégé)
# https://www.nbb.be → schéma comptable belge
RUBRIC_CODES = {
    "10/15": "capitaux_propres",       # Total capitaux propres
    "17/49": "dettes_totales",         # Total dettes
    "29/58": "actif_circulant",        # Actif circulant
    "42/48": "dettes_ct",              # Dettes court terme
    "20/58": "total_actif",            # Total bilan (actif)
    "9901": "resultat_exploitation",
    "9904": "resultat_exercice",
    "70":   "chiffre_affaires",
    "62":   "remunerations",
    "9087": "effectif_moyen",
}


def _fetch_accounting_data(bce: str, reference: str,
                           api_key: Optional[str] = None) -> dict:
    """Récupère les données comptables structurées d'un dépôt BNB.

    Renvoie un dict {code: valeur_float} (ex: {"10/15": 125000.0, ...}).
    Renvoie {} si l'API ne répond pas ou si la clé est absente.
    Best effort : on essaie l'endpoint /accountingData et on parse
    défensivement (l'API CBSO peut retourner du XBRL ou du JSON selon
    le modèle de dépôt).
    """
    key = api_key or os.environ.get("NBB_API_KEY")
    if not key or not bce or not reference:
        return {}

    bce_clean = "".join(c for c in bce if c.isdigit())
    if len(bce_clean) != 10:
        return {}

    headers = {
        "X-Request-Id": str(uuid.uuid4()),
        "NBB-CBSO-Subscription-Key": key,
        "Accept": "application/json",
    }
    url = f"{NBB_API_BASE}{bce_clean}/references/{reference}/accountingData"
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url, headers=headers)
            if r.status_code != 200:
                return {}
            payload = r.json()
    except Exception:
        return {}

    # Parsing défensif : l'API renvoie souvent une liste de rubriques avec
    # `Code` + `Value` (ou `Amount`). On ne fait pas confiance au schéma
    # exact et on tape large.
    result: dict[str, float] = {}
    items = payload if isinstance(payload, list) else (
        payload.get("Rubrics") or payload.get("rubrics") or
        payload.get("AccountingData") or []
    )
    if not isinstance(items, list):
        return {}
    for it in items:
        if not isinstance(it, dict):
            continue
        code = str(it.get("Code") or it.get("code") or
                   it.get("RubricCode") or "").strip()
        val = it.get("Value") or it.get("Amount") or it.get("amount")
        if not code or val is None:
            continue
        try:
            result[code] = float(val)
        except (ValueError, TypeError):
            continue
    return result


# ============================================================================
# Builder du user prompt
# ============================================================================

def _fmt_eur(v: Optional[float]) -> str:
    if v is None:
        return "Non disponible"
    try:
        # Format FR : espace insécable comme séparateur de milliers
        return f"{int(v):,} €".replace(",", " ")
    except (ValueError, TypeError):
        return "Non disponible"


def _ratio_pct(num: Optional[float], denom: Optional[float]) -> str:
    if not num or not denom or denom == 0:
        return "Non disponible"
    try:
        return f"{(num / denom) * 100:.1f} %"
    except (ZeroDivisionError, TypeError):
        return "Non disponible"


def _ratio_div(num: Optional[float], denom: Optional[float]) -> str:
    if not num or not denom or denom == 0:
        return "Non disponible"
    try:
        return f"{num / denom:.2f}"
    except (ZeroDivisionError, TypeError):
        return "Non disponible"


def _build_user_prompt(business: dict, nbb_meta: dict,
                       accounting: dict, heuristic: dict) -> str:
    """Construit le user prompt avec toutes les données disponibles."""
    name = (business.get("name") or "—").strip()
    bce = (business.get("bce_number") or "—").strip()
    status = (business.get("bce_status") or "Non détecté").strip()
    legal_form = (business.get("legal_form") or "—").strip()
    creation = (business.get("creation_date") or "Non détectée").strip()
    capital = (business.get("capital") or "Non détecté").strip()
    managers = (business.get("managers") or "Non détecté").strip()
    nace = (business.get("nace_activities") or "—").strip()
    city = (business.get("city") or business.get("locality") or "—").strip()

    # Données BNB extraites
    capitaux = accounting.get("10/15")
    dettes = accounting.get("17/49")
    actif_circ = accounting.get("29/58")
    dettes_ct = accounting.get("42/48")
    total_actif = accounting.get("20/58")
    resultat = accounting.get("9904")
    ca = accounting.get("70")
    effectif = accounting.get("9087")

    # Pré-calculs ratios
    solvabilite = _ratio_pct(capitaux, total_actif)
    liquidite = _ratio_div(actif_circ, dettes_ct)

    # Heuristique Phase 1
    h_color = heuristic.get("color", "gray")
    h_label = heuristic.get("label", "Données insuffisantes")
    h_reasons = heuristic.get("reasons", []) or []
    h_reasons_md = "\n".join(f"- {r}" for r in h_reasons) or "- (aucune)"

    return f"""Analyse la solvabilité de cette entreprise belge et génère
le rapport SELON LE FORMAT STRICT.

═══ ENTREPRISE ═══
- Nom : {name}
- BCE : {bce}
- Statut : {status}
- Forme juridique : {legal_form}
- Création : {creation}
- Capital social : {capital}
- Dirigeants : {managers[:160]}
- NACE : {nace[:120]}
- Localité : {city}

═══ DONNÉES BNB (dernier dépôt) ═══
- Exercice : {nbb_meta.get("year") or "Non disponible"}
- Date de dépôt : {nbb_meta.get("deposit_date") or "Non disponible"}
- Modèle : {nbb_meta.get("model_type") or "Non détecté"}
- Nombre total de dépôts : {nbb_meta.get("deposits_count", 0)}

═══ DONNÉES COMPTABLES EXTRAITES ═══
- Total actif (bilan) [code 20/58] : {_fmt_eur(total_actif)}
- Capitaux propres [code 10/15] : {_fmt_eur(capitaux)}
- Dettes totales [code 17/49] : {_fmt_eur(dettes)}
- Dettes à court terme [code 42/48] : {_fmt_eur(dettes_ct)}
- Actif circulant [code 29/58] : {_fmt_eur(actif_circ)}
- Chiffre d'affaires [code 70] : {_fmt_eur(ca)}
- Résultat de l'exercice [code 9904] : {_fmt_eur(resultat)}
- Effectif moyen [code 9087] : {int(effectif) if effectif else "Non disponible"}

═══ RATIOS PRÉ-CALCULÉS ═══
- Solvabilité = capitaux / total actif : {solvabilite}
- Liquidité = actif circulant / dettes CT : {liquidite}

═══ SCORE HEURISTIQUE PHASE 1 (à recouper) ═══
Couleur : {h_color.upper()} — {h_label}
Raisons :
{h_reasons_md}

═══ INSTRUCTION ═══
Génère MAINTENANT le rapport SELON LE FORMAT STRICT (VERDICT / RATIOS
CLÉS table / SIGNAUX D'ALERTE / RECOMMANDATION COMMERCIALE).
Si les données comptables sont absentes, retombe sur l'heuristique pour
le verdict. Réponse en markdown pur, aucun bloc de code."""


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
                    "temperature": 0.2,
                    "max_tokens": 1800,
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
                    "max_tokens": 1800,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_prompt}],
                    "temperature": 0.2,
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
# API publique
# ============================================================================

def generate_credit_report(business: dict) -> dict:
    """Génère le rapport crédit IA approfondi.

    Args:
        business: dict avec au minimum bce_number, name, et idéalement
                  bce_status, creation_date, credit_color/score/reasons
                  (champs déjà persistés par Phase 1).

    Returns:
        {
            "ok": bool,
            "report": str,            # markdown du rapport (vide si ok=False)
            "message": str,
            "provider": str | None,   # "openai" / "anthropic" / None
            "accounting_codes_count": int,  # nb de codes BNB extraits
        }
    """
    p = _provider()
    if not p:
        return {
            "ok": False, "report": "",
            "message": "Aucune clé IA configurée (OPENAI_API_KEY ou "
                       "ANTHROPIC_API_KEY). Rapport crédit non généré.",
            "provider": None,
            "accounting_codes_count": 0,
        }

    # 1. Métadonnées BNB :
    #    a) D'abord depuis le business dict (déjà persistées en DB par
    #       le scrape ou le backfill Playwright — pas de re-fetch coûteux)
    #    b) Si manquantes, on appelle fetch_nbb_financials avec
    #       allow_scraping=True → tape l'API CBSO (si NBB_API_KEY) ou
    #       le scraper Playwright en fallback (~3-5 s)
    bce = business.get("bce_number") or ""
    nbb_meta = {
        "year": business.get("nbb_year"),
        "deposit_date": business.get("nbb_deposit_date"),
        "model_type": business.get("nbb_model_type"),
        "deposits_count": int(business.get("nbb_deposits_count") or 0),
    }
    # Si on n'a RIEN en DB mais qu'on a un BCE → fetch live (lent)
    if bce and not nbb_meta["year"] and not nbb_meta["deposit_date"]:
        from .nbb import fetch_nbb_financials
        nbb = fetch_nbb_financials(bce, allow_scraping=True)
        if nbb and nbb.available:
            nbb_meta = {
                "year": nbb.year or nbb_meta["year"],
                "deposit_date": nbb.deposit_date,
                "model_type": nbb.model_type,
                "deposits_count": nbb.deposits_count,
            }

    # 2. Fetch données comptables structurées (best effort)
    accounting: dict = {}
    # TODO Phase 2.1 : enrichir NbbData avec reference_number pour pouvoir
    # appeler /accountingData/{reference} et extraire les codes 10/15,
    # 17/49, 9904, 70. Pour l'instant l'IA travaille sur les métadonnées
    # (year/deposit_date/model_type/count) qui suffisent à donner un
    # verdict utile sur la fiabilité du déposant.

    # 3. Reconstitue le score heuristique depuis le business dict
    try:
        h_reasons = json.loads(business.get("credit_reasons") or "[]")
    except Exception:
        h_reasons = []
    heuristic = {
        "color": business.get("credit_color") or "gray",
        "label": business.get("credit_label") or "Données insuffisantes",
        "reasons": h_reasons if isinstance(h_reasons, list) else [],
    }

    # 4. Construit le prompt + appel IA
    user_prompt = _build_user_prompt(business, nbb_meta, accounting, heuristic)
    result = (_call_openai(user_prompt) if p == "openai"
              else _call_anthropic(user_prompt))
    result["provider"] = p
    result["accounting_codes_count"] = len(accounting)
    return result

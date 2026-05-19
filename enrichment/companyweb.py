"""Enrichissement solvabilité / expérience de paiement via CompanyWeb.

CompanyWeb (https://www.companyweb.be) est un service de renseignement
commercial PAYANT. Le score de solvabilité et l'expérience de paiement sont
derrière abonnement.

Ce module fournit :
  1. Un lien direct vers la fiche CompanyWeb de l'entreprise (toujours dispo).
  2. Un emplacement pour l'enrichissement automatique : si tu as un abonnement
     CompanyWeb, renseigne COMPANYWEB_API_KEY (ou identifiants) et complète
     fetch_companyweb_score() avec l'appel API fourni par CompanyWeb.
"""

import os
import re
from dataclasses import dataclass
from typing import Optional


COMPANYWEB_BASE = "https://www.companyweb.be/fr/"


@dataclass
class CompanyWebData:
    profile_url: str
    score: Optional[str] = None
    payment_experience: Optional[str] = None
    available: bool = False


def _digits(bce: str) -> str:
    return re.sub(r"\D", "", bce or "")


def companyweb_url(bce: str) -> str:
    """Lien vers la fiche CompanyWeb (consultation nécessite un compte)."""
    d = _digits(bce)
    return COMPANYWEB_BASE + d if len(d) == 10 else COMPANYWEB_BASE


def fetch_companyweb_score(bce: str) -> CompanyWebData:
    d = _digits(bce)
    data = CompanyWebData(profile_url=companyweb_url(bce))
    if len(d) != 10:
        return data

    api_key = os.environ.get("COMPANYWEB_API_KEY")
    if not api_key:
        # Pas d'abonnement configuré : on ne fournit que le lien.
        return data

    # ------------------------------------------------------------------
    # EMPLACEMENT INTÉGRATION COMPANYWEB
    # Quand tu auras un abonnement CompanyWeb, implémente ici l'appel à
    # leur API (ils fournissent la doc avec l'abonnement). Exemple type :
    #
    #   import httpx
    #   with httpx.Client(timeout=15) as c:
    #       r = c.get(f"https://api.companyweb.be/v1/company/{d}",
    #                 headers={"Authorization": f"Bearer {api_key}"})
    #       j = r.json()
    #       data.score = j.get("solvencyScore")
    #       data.payment_experience = j.get("paymentBehaviour")
    #       data.available = True
    # ------------------------------------------------------------------
    return data

"""Enrichissement financier via la Banque Nationale de Belgique (BNB / NBB).

Deux niveaux :
  1. Lien de consultation publique (toujours disponible, gratuit, sans clé) :
     les comptes annuels déposés sont consultables sur consult.cbso.nbb.be.
  2. API "Authentic Data" (gratuite mais nécessite une clé) : si la variable
     d'environnement NBB_API_KEY est définie, on récupère les données chiffrées.
     Inscription gratuite : https://developer.cbso.nbb.be
"""

import os
import re
import uuid
from dataclasses import dataclass
from typing import Optional

import httpx


CONSULT_BASE = "https://consult.cbso.nbb.be/consult-enterprise/"
API_BASE = "https://ws.cbso.nbb.be/authentic/legalEntity/"


@dataclass
class NbbData:
    consult_url: str
    year: Optional[str] = None
    revenue: Optional[str] = None
    equity: Optional[str] = None
    employees: Optional[str] = None
    available: bool = False


def _digits(bce: str) -> str:
    return re.sub(r"\D", "", bce or "")


def nbb_consult_url(bce: str) -> str:
    """URL publique de consultation des comptes annuels (sans authentification)."""
    d = _digits(bce)
    return CONSULT_BASE + d if len(d) == 10 else CONSULT_BASE


def fetch_nbb_financials(bce: str, api_key: Optional[str] = None) -> NbbData:
    d = _digits(bce)
    data = NbbData(consult_url=nbb_consult_url(bce))
    if len(d) != 10:
        return data

    key = api_key or os.environ.get("NBB_API_KEY")
    if not key:
        return data

    headers = {
        "X-Request-Id": str(uuid.uuid4()),
        "NBB-CBSO-Subscription-Key": key,
        "Accept": "application/json",
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{API_BASE}{d}/references", headers=headers)
            if r.status_code != 200:
                return data
            payload = r.json()
            deposits = payload if isinstance(payload, list) else payload.get("references", [])
            if not deposits:
                return data
            latest = deposits[0]
            data.year = str(latest.get("ExerciseDates", {}).get("endDate", ""))[:4] or None
            data.available = True
    except Exception:
        return data

    return data

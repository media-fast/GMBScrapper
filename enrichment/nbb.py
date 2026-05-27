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
    # Métadonnées du dernier dépôt (utiles pour le scoring crédit)
    deposit_date: Optional[str] = None      # YYYY-MM-DD du dernier dépôt
    model_type: Optional[str] = None        # FULL / ABBREVIATED / MICRO
    deposits_count: int = 0                 # nombre total de dépôts trouvés


def _digits(bce: str) -> str:
    return re.sub(r"\D", "", bce or "")


def nbb_consult_url(bce: str) -> str:
    """URL publique de consultation des comptes annuels (sans authentification)."""
    d = _digits(bce)
    return CONSULT_BASE + d if len(d) == 10 else CONSULT_BASE


def fetch_nbb_financials(bce: str, api_key: Optional[str] = None) -> NbbData:
    """Récupère les métadonnées du dernier dépôt BNB pour une entreprise.

    Renvoie systématiquement le `consult_url` (lien public, sans clé). Si une
    `NBB_API_KEY` est configurée, on tape l'API CBSO `/references` pour
    récupérer la liste des dépôts et on extrait du dernier :
      - l'année d'exercice (`year`)
      - la date de dépôt (`deposit_date`, format YYYY-MM-DD)
      - le type de modèle (FULL/ABBREVIATED/MICRO)
      - le nombre total de dépôts (utile pour évaluer la régularité)

    Ces champs alimentent ensuite le scoring crédit heuristique
    (`enrichment/credit_score.py`).
    """
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
            # Trie par date de dépôt décroissante au cas où l'API ne le ferait
            # pas (la CBSO renvoie en principe le plus récent en premier,
            # mais on sécurise pour éviter de scorer sur un vieux dépôt).
            def _ddate(dep: dict) -> str:
                return str(dep.get("DepositDate") or
                           dep.get("ExerciseDates", {}).get("endDate") or "")
            deposits_sorted = sorted(deposits, key=_ddate, reverse=True)
            latest = deposits_sorted[0]
            ex_end = str(latest.get("ExerciseDates", {}).get("endDate", ""))
            data.year = ex_end[:4] or None
            data.deposit_date = (str(latest.get("DepositDate") or "")[:10]
                                 or (ex_end[:10] if ex_end else None))
            data.model_type = (latest.get("ModelType")
                               or latest.get("DepositType") or None)
            data.deposits_count = len(deposits)
            data.available = True
    except Exception:
        return data

    return data

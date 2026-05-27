"""Scoring crédit heuristique d'une entreprise belge (Phase 1).

Verdict baromètre 5 couleurs basé sur des signaux DISPONIBLES SANS parsing
XBRL/PDF :
  - Statut BCE (cessé/actif/liquidation/faillite)
  - Ancienneté (creation_date BCE)
  - Régularité des dépôts BNB (date du dernier dépôt + nombre total)

Limites assumées de cette heuristique :
  - Ne dit RIEN sur les ratios financiers (capitaux propres, dettes, etc.) —
    c'est la Phase 2 (rapport IA via skill credit-analysis-belgium-b2b qui,
    elle, télécharge et parse le XBRL).
  - Une entreprise "verte" ici peut très bien être en difficulté ; "verte"
    veut juste dire "à jour de ses obligations légales".
  - Signal fort de défaut : dépôts en retard >24 mois ou statut cessé.

Couleurs :
  🔴 red    — Mauvais payeur (statut cessé/faillite/liquidation)
  🟠 orange — À risque (aucun dépôt ou dépôts très en retard)
  🟡 yellow — À surveiller (dépôts un peu en retard)
  🟢 green  — Bon payeur (à jour de ses dépôts)
  ⚪ gray   — Données insuffisantes (entreprise jeune ou pas d'info)
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import List, Optional

from .nbb import NbbData


# ============================================================================
# Constantes
# ============================================================================

COLOR_LABELS = {
    "red": "Mauvais payeur",
    "orange": "À risque",
    "yellow": "À surveiller",
    "green": "Bon payeur",
    "gray": "Données insuffisantes",
}

# Score numérique indicatif (0-100) — utile pour trier la grille de résultats
COLOR_SCORES = {
    "red": 15,
    "orange": 35,
    "yellow": 60,
    "green": 85,
    "gray": 50,
}

# Mots-clés statut BCE qui indiquent une entreprise NON active
_INACTIVE_STATUS_KEYWORDS = (
    "cess", "inactif", "radié", "radie", "radiée", "radiee",
    "liquidation", "faillite", "dissolu", "dissout",
)


# ============================================================================
# Modèle de résultat
# ============================================================================

@dataclass
class CreditScore:
    color: str                                # "red"/"orange"/"yellow"/"green"/"gray"
    score: int                                # 0-100 (plus haut = mieux)
    label: str                                # libellé FR humain
    reasons: List[str] = field(default_factory=list)
    computed_at: str = ""                     # ISO timestamp

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# Helpers privés
# ============================================================================

# Mois français → numéro (pour le format BCE « 29 octobre 2009 »)
_FR_MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "decembre": 12,
}


def _parse_date(s: Optional[str]) -> Optional[date]:
    """Parse une date dans divers formats :
      - ISO  : 2009-10-29, 2009-10-29T12:00:00
      - EU   : 29-10-2009, 29/10/2009
      - FR   : 29 octobre 2009 (format BCE)
      - YYYY : 2009 (année seule → 1er janvier)
    """
    if not s:
        return None
    s = str(s).strip()

    # Tentative format français textuel ("29 octobre 2009")
    parts = s.lower().split()
    if len(parts) == 3 and parts[1] in _FR_MONTHS:
        try:
            return date(int(parts[2]), _FR_MONTHS[parts[1]], int(parts[0]))
        except (ValueError, TypeError):
            pass

    # Formats classiques par strptime
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d-%m-%Y", "%d/%m/%Y", "%Y"):
        try:
            return datetime.strptime(s[:len(fmt) + 2], fmt).date()
        except ValueError:
            continue
    return None


def _months_since(d: Optional[date], ref: Optional[date] = None) -> Optional[int]:
    if not d:
        return None
    today = ref or date.today()
    return (today.year - d.year) * 12 + (today.month - d.month)


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _verdict(color: str, reasons: List[str]) -> CreditScore:
    return CreditScore(
        color=color,
        score=COLOR_SCORES[color],
        label=COLOR_LABELS[color],
        reasons=reasons,
        computed_at=_now_iso(),
    )


# ============================================================================
# API publique
# ============================================================================

def compute_credit_score(
    bce_status: Optional[str] = None,
    creation_date: Optional[str] = None,
    nbb_data: Optional[NbbData] = None,
    today: Optional[date] = None,
) -> CreditScore:
    """Calcule le verdict crédit heuristique.

    Args:
        bce_status: statut BCE textuel (ex: "Active", "Cessation d'activité")
        creation_date: date de création de l'entreprise (str divers formats)
        nbb_data: métadonnées BNB du dernier dépôt (peut être None)
        today: pour injecter une date fixe dans les tests

    Returns:
        CreditScore avec color/score/label/reasons.
    """
    # ── 0. Aucune donnée disponible → GRIS direct ──
    # Évite la dérive vers ORANGE quand on n'a vraiment rien à évaluer
    # (ex : fiche sans BCE, sans creation_date, sans dépôt BNB).
    if not bce_status and not creation_date and not nbb_data:
        return _verdict("gray", [
            "Aucune donnée légale ou financière disponible",
            "Impossible d'évaluer le risque crédit sans BCE",
        ])

    # ── 1. Statut BCE : si cessé / faillite / liquidation → ROUGE immédiat ──
    if bce_status:
        status_norm = bce_status.lower()
        if any(kw in status_norm for kw in _INACTIVE_STATUS_KEYWORDS):
            return _verdict("red", [
                f"Entreprise non active : {bce_status.strip()}",
                "Risque élevé de non-paiement — déconseillé d'engager des frais",
            ])

    # ── 2. Calcul de l'ancienneté ──
    today = today or date.today()
    creation = _parse_date(creation_date)
    age_months = _months_since(creation, today) if creation else None

    # ── 3. Extraction des données BNB ──
    deposit_date = _parse_date(nbb_data.deposit_date) if nbb_data else None
    nbb_year = nbb_data.year if nbb_data else None
    deposits_count = nbb_data.deposits_count if nbb_data else 0

    # Si on n'a que l'année du dernier exercice (pas la date de dépôt
    # exacte), on approxime : dépôt légal ~7 mois après clôture exercice.
    if not deposit_date and nbb_year:
        try:
            y = int(nbb_year)
            deposit_date = date(y + 1, 7, 1)
        except (ValueError, TypeError):
            pass
    months_since_deposit = _months_since(deposit_date, today)

    # ── 4. Cas : entreprise trop jeune pour évaluer (<18 mois) ──
    if age_months is not None and age_months < 18:
        return _verdict("gray", [
            f"Entreprise jeune (créée il y a {age_months} mois) — pas assez "
            "de recul pour évaluer la régularité des dépôts",
        ])

    # ── 5. Cas : aucun dépôt BNB connu ──
    if months_since_deposit is None:
        # Si l'entreprise a plus de 24 mois et n'a JAMAIS déposé → orange
        # (obligation légale en Belgique pour la plupart des sociétés)
        if age_months is not None and age_months >= 24:
            reasons = [
                "Aucun dépôt de comptes annuels trouvé à la BNB",
                f"Entreprise créée il y a {age_months // 12} an(s) — les "
                "dépôts auraient dû être faits",
                "Manque de transparence financière — signal de prudence",
            ]
            return _verdict("orange", reasons)
        # Âge inconnu ou pas assez de recul → gris (on ne sait pas si
        # l'absence de dépôt est anormale)
        return _verdict("gray", ["Pas de données financières BNB disponibles"])

    # ── 6. Dépôts en retard ──
    if months_since_deposit > 24:
        return _verdict("orange", [
            f"Dernier dépôt BNB il y a {months_since_deposit} mois — retard "
            "significatif (>2 ans)",
            "Souvent corrélé à des difficultés financières ou un abandon de "
            "l'activité administrative",
        ])

    if months_since_deposit > 18:
        return _verdict("yellow", [
            f"Dernier dépôt BNB il y a {months_since_deposit} mois — léger "
            "retard (à surveiller)",
        ])

    # ── 7. Dépôts à jour → VERT ──
    reasons = [f"Dépôts BNB à jour — dernier exercice : {nbb_year or '—'}"]
    if deposits_count >= 5:
        reasons.append(f"Historique régulier : {deposits_count} dépôts déposés")
    if age_months is not None and age_months >= 60:
        reasons.append(f"Entreprise établie depuis {age_months // 12} ans")
    return _verdict("green", reasons)

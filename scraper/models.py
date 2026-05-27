from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Business:
    name: str
    query: str = ""
    city: str = ""

    # Position dans le classement Google Maps (1 = premier résultat)
    google_rank: Optional[int] = None

    address: Optional[str] = None
    postal_code: Optional[str] = None
    locality: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    hours: Optional[str] = None
    gmaps_url: Optional[str] = None
    plus_code: Optional[str] = None

    # Identité légale (BCE / TVA)
    vat_number: Optional[str] = None
    bce_number: Optional[str] = None
    legal_form: Optional[str] = None
    bce_status: Optional[str] = None
    bce_match_score: Optional[int] = None
    bce_match_warning: Optional[str] = None

    # Enrichissement fiche détail BCE
    managers: Optional[str] = None
    creation_date: Optional[str] = None
    capital: Optional[str] = None
    establishments_count: Optional[int] = None
    nace_activities: Optional[str] = None

    # Données financières (BNB) et solvabilité (CompanyWeb)
    nbb_url: Optional[str] = None
    nbb_year: Optional[str] = None
    nbb_revenue: Optional[str] = None
    nbb_equity: Optional[str] = None
    nbb_employees: Optional[str] = None
    # Métadonnées dépôt BNB (alimentent le rapport crédit IA)
    nbb_deposit_date: Optional[str] = None    # YYYY-MM-DD
    nbb_model_type: Optional[str] = None      # FULL / ABBREVIATED / MICRO
    nbb_deposits_count: Optional[int] = None
    companyweb_url: Optional[str] = None
    companyweb_score: Optional[str] = None

    # Scoring crédit heuristique (enrichment/credit_score.py)
    credit_color: Optional[str] = None        # red/orange/yellow/green/gray
    credit_score: Optional[int] = None        # 0-100
    credit_label: Optional[str] = None        # libellé FR
    credit_reasons: Optional[str] = None      # JSON-encoded list[str]
    credit_computed_at: Optional[str] = None  # timestamp

    # Historique / déduplication
    already_seen: bool = False
    first_seen: Optional[str] = None

    @property
    def is_top_ranked(self) -> bool:
        return self.google_rank is not None and self.google_rank <= 2

    def to_dict(self) -> dict:
        return asdict(self)

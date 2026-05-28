"""Schémas Pydantic pour les réponses API.

On ne mappe QUE les champs utiles au frontend POC (pas tout le dataclass
Business). Les noms snake_case sont conservés pour cohérence avec la DB.
"""

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Searches (scrapes historisés)
# ============================================================================

class SearchSummary(BaseModel):
    """Méta-données d'un scrape pour la dropdown selecteur."""
    id: int
    query: str
    cities: Optional[str] = None
    ran_at: str
    total: int = 0
    new_count: int = 0


# ============================================================================
# Businesses
# ============================================================================

class BusinessSummary(BaseModel):
    """Vue grille de résultats — champs minimum pour la card."""
    dedup_key: str
    name: str
    bce_number: Optional[str] = None
    vat_number: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    postal_code: Optional[str] = None
    category: Optional[str] = None
    managers: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    google_rank: Optional[int] = None
    call_status: Optional[str] = "À appeler"

    # Santé financière (Phase 1 credit score)
    credit_color: Optional[str] = Field(
        None, description="red / orange / yellow / green / gray"
    )
    credit_label: Optional[str] = None
    credit_reasons: Optional[str] = Field(
        None, description="JSON-encoded list[str]"
    )


class BusinessDetail(BusinessSummary):
    """Vue page détail — ajoute les champs riches."""
    legal_form: Optional[str] = None
    bce_status: Optional[str] = None
    creation_date: Optional[str] = None
    capital: Optional[str] = None
    nace_activities: Optional[str] = None
    gmaps_url: Optional[str] = None
    nbb_url: Optional[str] = None
    nbb_year: Optional[str] = None
    nbb_deposit_date: Optional[str] = None
    nbb_model_type: Optional[str] = None
    nbb_deposits_count: Optional[int] = None
    credit_score: Optional[int] = None
    credit_computed_at: Optional[str] = None
    has_seo_audit: bool = False
    has_credit_ai_report: bool = False


class SearchBusinessesResponse(BaseModel):
    """Réponse de GET /searches/{id}/businesses :
    fiches + compteurs pour les filtres."""
    items: list[BusinessSummary]
    total: int
    # Counts par credit_color pour alimenter les pills côté front
    credit_counts: dict[str, int] = Field(default_factory=dict)


# ============================================================================
# Campagne d'appels
# ============================================================================

class CampaignBusiness(BusinessSummary):
    """Fiche dans le contexte campagne — avec call_notes / callback_date."""
    call_notes: Optional[str] = None
    last_call_at: Optional[str] = None
    callback_date: Optional[str] = None


class CampaignResponse(BaseModel):
    """Liste filtrée par statut + compteurs par statut."""
    items: list[CampaignBusiness]
    total: int
    status_counts: dict[str, int] = Field(default_factory=dict)


# ============================================================================
# Historique global (toutes fiches connues)
# ============================================================================

class HistoryStats(BaseModel):
    total_searches: int
    total_businesses: int
    total_called: int


class HistoryResponse(BaseModel):
    stats: HistoryStats
    searches: list[SearchSummary]


# ============================================================================
# Scrape (lancement + progress)
# ============================================================================

class ScrapeStartRequest(BaseModel):
    """Payload de POST /api/scrapes."""
    metiers: list[str] = Field(
        ..., min_length=1, description="Liste de métiers (« opticien », etc.)"
    )
    cities: list[str] = Field(
        ..., min_length=1, description="Liste de communes (« Waterloo », etc.)"
    )
    max_per_city: int = Field(30, ge=1, le=500)
    headless: bool = True
    strict_city: bool = True
    require_phone: bool = False
    do_vat: bool = True
    do_bce: bool = True
    do_fin: bool = True
    do_credit_scoring: bool = False
    workers: int = Field(6, ge=1, le=12)


class ScrapeStartResponse(BaseModel):
    """Réponse au POST : l'ID utilisé pour le polling de progress."""
    scrape_id: str


class ScrapeProgress(BaseModel):
    """Snapshot de l'état d'un scrape (renvoyé par GET /progress)."""
    scrape_id: str
    active: bool
    phase: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    cities_total: int = 0
    variants_total: int = 0
    prospects_brut: int = 0
    result_count: int = 0
    vat_enriched: int = 0
    google_blocked: bool = False
    error: Optional[str] = None
    log_tail: list[str] = Field(default_factory=list)
    losses: dict[str, int] = Field(default_factory=dict)
    # ID du `search` créé en DB une fois le scrape terminé → permet au
    # front de jump dans le tab Résultats sur la nouvelle recherche.
    result_search_id: Optional[int] = None

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

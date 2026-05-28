"""Application FastAPI principale.

Endpoints exposés :
    GET  /api/health                            -> ping
    GET  /api/searches                          -> liste des scrapes
    GET  /api/searches/{search_id}/businesses   -> fiches d'un scrape
    GET  /api/businesses/{dedup_key}            -> détail d'une fiche

Réutilise tel quel les fonctions de `storage.history`. Pas de duplication
de logique : le frontend POC va chercher exactement les mêmes données que
l'UI Streamlit, juste via HTTP/JSON au lieu d'imports Python directs.

CORS ouvert pour localhost:5173 (Vite dev server) — à durcir en prod.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from storage.history import (
    campaign_stats,
    get_campaign_businesses,
    get_known_businesses,
    get_search_businesses,
    history_stats,
    list_searches,
)

from .schemas import (
    BusinessDetail,
    BusinessSummary,
    CampaignBusiness,
    CampaignResponse,
    HistoryResponse,
    HistoryStats,
    SearchBusinessesResponse,
    SearchSummary,
)

app = FastAPI(
    title="ScrapperGMB API",
    description=(
        "POC backend FastAPI pour le frontend React. Réutilise les modules "
        "Python existants (scraper, enrichment, storage) — zéro duplication."
    ),
    version="0.1.0",
)

# CORS pour le dev frontend (Vite sur :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",  # au cas où l'user change de port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints
# ============================================================================

@app.get("/api/health")
def health() -> dict:
    """Ping pour vérifier que le backend tourne."""
    return {"status": "ok", "service": "ScrapperGMB API"}


@app.get("/api/searches", response_model=list[SearchSummary])
def get_searches(limit: int = 100) -> list[SearchSummary]:
    """Liste les scrapes les plus récents."""
    rows = list_searches(limit=limit)
    return [SearchSummary(**r) for r in rows]


@app.get(
    "/api/searches/{search_id}/businesses",
    response_model=SearchBusinessesResponse,
)
def get_businesses_for_search(search_id: int) -> SearchBusinessesResponse:
    """Fiches d'un scrape + counters credit pour les filtres."""
    rows = get_search_businesses(search_id)
    if rows is None:
        raise HTTPException(404, detail=f"Search {search_id} not found")

    items = [BusinessSummary(**r) for r in rows]

    # Counts par credit_color pour les filtres pills frontend
    credit_counts: dict[str, int] = {}
    for r in rows:
        c = r.get("credit_color")
        if c:
            credit_counts[c] = credit_counts.get(c, 0) + 1

    return SearchBusinessesResponse(
        items=items,
        total=len(items),
        credit_counts=credit_counts,
    )


@app.get(
    "/api/businesses/{dedup_key}",
    response_model=BusinessDetail,
)
def get_business_detail(dedup_key: str) -> BusinessDetail:
    """Détail complet d'une fiche pour la page détail."""
    # On cherche dans l'ensemble des fiches (toutes recherches confondues)
    all_biz = get_known_businesses(limit=50000)
    match = next(
        (b for b in all_biz if b.get("dedup_key") == dedup_key),
        None,
    )
    if not match:
        raise HTTPException(404, detail=f"Business {dedup_key} not found")

    # Booléens dérivés (les payloads complets restent côté backend)
    detail = BusinessDetail(
        **match,
        has_seo_audit=bool(match.get("seo_audit")),
        has_credit_ai_report=bool(match.get("credit_ai_report")),
    )
    return detail


# ============================================================================
# Campagne d'appels
# ============================================================================

@app.get("/api/campaign", response_model=CampaignResponse)
def get_campaign(status: str | None = None) -> CampaignResponse:
    """Fiches dans le contexte campagne d'appels, filtrables par statut."""
    rows = get_campaign_businesses(status=status, limit=5000)
    items = [CampaignBusiness(**r) for r in rows]
    # Compteurs par statut (toujours sur l'ensemble, pas le filtré)
    stats = campaign_stats() or {}
    return CampaignResponse(
        items=items,
        total=len(items),
        status_counts=stats,
    )


# ============================================================================
# Historique global
# ============================================================================

@app.get("/api/history", response_model=HistoryResponse)
def get_history() -> HistoryResponse:
    """Stats globales + liste des derniers scrapes pour le tab Historique."""
    stats = history_stats() or {}
    searches = list_searches(limit=100)
    return HistoryResponse(
        stats=HistoryStats(
            total_searches=stats.get("total_searches", 0),
            total_businesses=stats.get("total_businesses", 0),
            total_called=stats.get("total_called", 0),
        ),
        searches=[SearchSummary(**s) for s in searches],
    )

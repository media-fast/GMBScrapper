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

import uuid
from typing import Any, MutableMapping

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from scraper.runner import init_scrape_state, start_background_scrape
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
    ScrapeProgress,
    ScrapeStartRequest,
    ScrapeStartResponse,
    SearchBusinessesResponse,
    SearchSummary,
)


# ============================================================================
# In-memory store des états de scrape
# ============================================================================
# Pas de persistance — l'état est éphémère pendant la durée du scrape (~3-15 min).
# Une fois le scrape terminé, l'état reste accessible jusqu'au redémarrage du
# process pour que le front puisse afficher le panel « Recherche terminée ».
# Pour un outil interne 1-3 users, c'est largement suffisant.
_scrape_states: dict[str, MutableMapping[str, Any]] = {}

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

# ============================================================================
# Scrape — lancer + suivre la progression
# ============================================================================

@app.post("/api/scrapes", response_model=ScrapeStartResponse)
def start_scrape(payload: ScrapeStartRequest) -> ScrapeStartResponse:
    """Lance un nouveau scrape en arrière-plan.

    Réutilise `start_background_scrape` qui spawn un thread daemon. Le
    résultat (l'état mutable) est stocké dans `_scrape_states[id]` et peut
    être récupéré via GET /api/scrapes/{id}/progress.
    """
    # 1. Nouvel état vierge
    state = init_scrape_state()
    scrape_id = uuid.uuid4().hex[:12]
    _scrape_states[scrape_id] = state

    # 2. Démarre le thread (réutilise la pipeline existante)
    start_background_scrape(
        state,
        metiers=payload.metiers,
        cities=payload.cities,
        max_per_city=payload.max_per_city,
        headless=payload.headless,
        strict_city=payload.strict_city,
        exclude_seen=True,  # toujours True côté API
        require_phone=payload.require_phone,
        do_vat=payload.do_vat,
        do_bce=payload.do_bce,
        do_fin=payload.do_fin,
        workers=payload.workers,
        do_credit_scoring=payload.do_credit_scoring,
    )
    return ScrapeStartResponse(scrape_id=scrape_id)


@app.get("/api/scrapes/{scrape_id}/progress", response_model=ScrapeProgress)
def get_scrape_progress(scrape_id: str) -> ScrapeProgress:
    """Snapshot de l'état d'un scrape (polling 1.5 s côté front)."""
    state = _scrape_states.get(scrape_id)
    if state is None:
        raise HTTPException(404, detail=f"Scrape {scrape_id} introuvable")

    # Normalise quelques champs (datetime → str)
    def _iso(v: Any) -> str | None:
        if v is None:
            return None
        try:
            return v.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(v)

    log = state.get("log") or []
    return ScrapeProgress(
        scrape_id=scrape_id,
        active=bool(state.get("active", False)),
        phase=str(state.get("phase", "idle")),
        started_at=_iso(state.get("started_at")),
        ended_at=_iso(state.get("ended_at")),
        cities_total=int(state.get("cities_total", 0)),
        variants_total=int(state.get("variants_total", 0)),
        prospects_brut=int(state.get("prospects_brut", 0)),
        result_count=int(state.get("result_count", 0)),
        vat_enriched=int(state.get("vat_enriched", 0)),
        google_blocked=bool(state.get("google_blocked", False)),
        error=state.get("error"),
        log_tail=list(log[-15:]),  # 15 dernières lignes
        losses=dict(state.get("losses") or {}),
        result_search_id=state.get("result_search_id"),
    )


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

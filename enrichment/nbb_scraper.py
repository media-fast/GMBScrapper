"""Scraper Playwright pour récupérer les dépôts BNB SANS clé API.

Charge la page publique consult.cbso.nbb.be/consult-enterprise/<bce>
(SPA Angular), attend le rendu du tableau des dépôts, puis extrait les
métadonnées du dernier dépôt :
  - Année d'exercice
  - Date de dépôt
  - Type de modèle (FULL / ABBREVIATED / MICRO)
  - Nombre total de dépôts

⚠ Lent : ~3-5 s par fiche (ouvre une session Chromium headless). À utiliser :
  - en batch via scripts/backfill_nbb_via_playwright.py (réutilise UN
    seul browser pour N fiches)
  - en fallback de fetch_nbb_financials si NBB_API_KEY est absente
    (mais alors le scrape principal devient très lent → opt-in seulement)

Format de page (extrait observé pour BCE 0424735977 le 27/05/2026) :

    42 résultat(s)
    Volledig model kapitaalvennootschap     ← modèle
    Initial
    Référence 2025-00335501Date de dépôt 29/07/2025
    Date de fin d'exercice
    31/12/2024
    NL
"""

import asyncio
import re
from typing import Callable, Optional

from playwright.async_api import (
    Page,
    TimeoutError as _PWT,
    async_playwright,
)

from .nbb import NbbData, nbb_consult_url


CONSULT_BASE = "https://consult.cbso.nbb.be/consult-enterprise/"
DEFAULT_TIMEOUT_MS = 20000
DEFAULT_WAIT_AFTER_LOAD_MS = 1500


# ─── Regex patterns sur le texte brut de la page (FR + NL bilingual) ──
_RE_DEPOSIT_DATE = re.compile(r"Date de d[ée]p[oô]t\s+(\d{2})/(\d{2})/(\d{4})")
_RE_EXERCISE_END = re.compile(
    r"Date de fin d['']exercice\s*\n\s*(\d{2})/(\d{2})/(\d{4})"
)
_RE_TOTAL_COUNT = re.compile(r"(\d+)\s+r[ée]sultat")
# Modèles de comptes (FR + NL)
_MODEL_KEYWORDS = [
    ("FULL", ("modèle complet", "complete model", "volledig model",
              "volledig schema")),
    ("ABBREVIATED", ("modèle abrégé", "abbreviated model",
                     "verkort model", "verkort schema")),
    ("MICRO", ("modèle micro", "micro model", "micro-schema")),
]


def _parse_page_text(text: str) -> Optional[dict]:
    """Extrait les métadonnées du dernier dépôt depuis le texte de la page.

    Renvoie None si aucune date de dépôt n'est détectée (entreprise sans
    dépôt à la BNB, ou page mal chargée).
    """
    # 1. Date du dernier dépôt (premier match = le plus récent, l'API les
    #    trie par défaut en ordre décroissant côté Angular)
    m = _RE_DEPOSIT_DATE.search(text)
    if not m:
        return None
    deposit_dd, deposit_mm, deposit_yy = m.groups()
    deposit_date = f"{deposit_yy}-{deposit_mm}-{deposit_dd}"

    # 2. Année de l'exercice du dernier dépôt
    m_ex = _RE_EXERCISE_END.search(text)
    year = m_ex.group(3) if m_ex else None

    # 3. Nombre total de dépôts
    m_total = _RE_TOTAL_COUNT.search(text)
    deposits_count = int(m_total.group(1)) if m_total else 0

    # 4. Type de modèle (sur tout le texte — premier dépôt = type principal)
    text_low = text.lower()
    model_type = None
    for tag, keywords in _MODEL_KEYWORDS:
        if any(kw in text_low for kw in keywords):
            model_type = tag
            break

    return {
        "year": year,
        "deposit_date": deposit_date,
        "model_type": model_type,
        "deposits_count": deposits_count,
    }


async def _scrape_one_attempt(page: Page, bce_digits: str) -> Optional[dict]:
    """Une seule tentative de scrape (utilisée par _scrape_one + retries)."""
    url = f"{CONSULT_BASE}{bce_digits}"
    # `networkidle` est nettement plus fiable que `domcontentloaded` ici :
    # Angular fait plusieurs XHR avant d'hydrater le tableau. On a 30 s de
    # budget, largement suffisant pour les pages les plus chargées.
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except _PWT:
        # Si networkidle traîne, fallback sur load
        try:
            await page.goto(url, wait_until="load", timeout=20000)
        except _PWT:
            return None

    # Polling court pour absorber les renders progressifs Angular
    # (parfois la table arrive en 2-3 passes après networkidle).
    await page.wait_for_timeout(DEFAULT_WAIT_AFTER_LOAD_MS)
    for _ in range(8):  # 8 × 500 ms = 4 s grace (au lieu de 6)
        text = await page.inner_text("body")
        if _RE_DEPOSIT_DATE.search(text):
            return _parse_page_text(text)
        # ⚠ « 0 résultat » indique vraiment « pas de dépôt » — mais
        # seulement si on a aussi le nom de l'entreprise (= page vraiment
        # chargée). Sinon c'est juste un état intermédiaire du SPA.
        if (re.search(r"0\s+r[ée]sultat", text, re.IGNORECASE)
                and len(text) > 200):
            return None
        await page.wait_for_timeout(500)

    # Dernière chance après le polling
    text = await page.inner_text("body")
    return _parse_page_text(text)


async def _scrape_one(page: Page, bce_digits: str,
                      max_retries: int = 2) -> Optional[dict]:
    """Scrape avec retry sur les échecs transitoires.

    Le SPA Angular CBSO peut parfois servir une page incomplète :
      - networkidle déclenché trop tôt
      - hydratation du tableau qui rate
      - rate limiting silencieux
    On retry jusqu'à `max_retries` fois (+1 attempt = 3 essais max) avec
    un backoff progressif. Cas typique observé : un même BCE renvoie
    None au premier passage puis OK au second avec ~13 dépôts.
    """
    for attempt in range(max_retries + 1):
        result = await _scrape_one_attempt(page, bce_digits)
        if result is not None and result.get("deposit_date"):
            return result
        if attempt < max_retries:
            # Backoff progressif : 1s → 2s entre les tentatives
            await page.wait_for_timeout(1000 * (attempt + 1))
    return result  # last result (None ou dict incomplet)


# ============================================================================
# API publique
# ============================================================================

async def scrape_nbb_async(bce: str) -> NbbData:
    """Lance un browser et scrape les dépôts pour UN BCE (~3-5 s).

    Pour un usage one-shot. Pour batch, utiliser batch_scrape_nbb_async
    qui réutilise UN browser pour N BCEs.
    """
    digits = re.sub(r"\D", "", bce or "")
    data = NbbData(consult_url=nbb_consult_url(bce))
    if len(digits) != 10:
        return data

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36",
            )
            page = await ctx.new_page()
            result = await _scrape_one(page, digits)
            if result:
                data.year = result["year"]
                data.deposit_date = result["deposit_date"]
                data.model_type = result["model_type"]
                data.deposits_count = result["deposits_count"]
                data.available = True
        finally:
            await browser.close()
    return data


async def batch_scrape_nbb_async(
    bces: list[str],
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> dict[str, NbbData]:
    """Scrape plusieurs BCEs avec UN SEUL browser (économise ~2 s/fiche).

    Args:
        bces: liste des numéros BCE à scraper
        progress: callback(idx, total, bce) appelé avant chaque scrape

    Returns:
        dict {bce: NbbData}. Pour les BCE sans dépôt, NbbData.available
        est False.
    """
    results: dict[str, NbbData] = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36",
            )
            page = await ctx.new_page()
            for i, bce in enumerate(bces, 1):
                if progress:
                    progress(i, len(bces), bce)
                digits = re.sub(r"\D", "", bce or "")
                data = NbbData(consult_url=nbb_consult_url(bce))
                if len(digits) == 10:
                    try:
                        result = await _scrape_one(page, digits)
                        if result:
                            data.year = result["year"]
                            data.deposit_date = result["deposit_date"]
                            data.model_type = result["model_type"]
                            data.deposits_count = result["deposits_count"]
                            data.available = True
                    except Exception:
                        pass  # garde data avec available=False
                results[bce] = data
        finally:
            await browser.close()
    return results


def scrape_nbb(bce: str) -> NbbData:
    """Wrapper sync de scrape_nbb_async pour les contextes non-async."""
    try:
        return asyncio.run(scrape_nbb_async(bce))
    except RuntimeError:
        # Cas où un event loop tourne déjà (ex: Streamlit thread)
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(scrape_nbb_async(bce))
        finally:
            loop.close()

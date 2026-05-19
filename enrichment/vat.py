import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from scraper.models import Business

from .bce_detail import fetch_bce_detail
from .companyweb import companyweb_url, fetch_companyweb_score
from .kbo import lookup_vat_via_kbo
from .nbb import fetch_nbb_financials, nbb_consult_url
from .website import fetch_website_contact


def _vat_to_bce(vat: str) -> str:
    digits = "".join(c for c in vat if c.isdigit())
    if len(digits) == 10:
        return f"{digits[0:4]}.{digits[4:7]}.{digits[7:10]}"
    return vat


def _enrich_from_bce_detail(business: Business) -> None:
    if not business.bce_number:
        return
    detail = fetch_bce_detail(business.bce_number)
    if not detail:
        return
    business.managers = detail.managers_str
    business.creation_date = detail.creation_date
    business.capital = detail.capital
    business.establishments_count = detail.establishments_count
    business.nace_activities = detail.nace_str
    if not business.legal_form:
        business.legal_form = detail.legal_form
    if not business.bce_status:
        business.bce_status = detail.status
    if not business.email and detail.email:
        business.email = detail.email
    if not business.website and detail.website:
        business.website = detail.website


def _enrich_financial(business: Business) -> None:
    if not business.bce_number:
        return
    business.nbb_url = nbb_consult_url(business.bce_number)
    business.companyweb_url = companyweb_url(business.bce_number)

    nbb = fetch_nbb_financials(business.bce_number)
    if nbb.available:
        business.nbb_year = nbb.year
        business.nbb_revenue = nbb.revenue
        business.nbb_equity = nbb.equity
        business.nbb_employees = nbb.employees

    cw = fetch_companyweb_score(business.bce_number)
    if cw.available:
        business.companyweb_score = cw.score


def enrich_business_with_vat(
    business: Business,
    use_website: bool = True,
    use_kbo: bool = True,
    use_bce_detail: bool = True,
    use_financial: bool = True,
) -> Business:
    # 1. Site web : TVA + email pro
    if use_website and business.website:
        try:
            contact = fetch_website_contact(business.website)
            if contact.email and not business.email:
                business.email = contact.email
            if contact.vat:
                business.vat_number = contact.vat
                business.bce_number = _vat_to_bce(contact.vat)
                business.bce_match_score = 100
                business.bce_match_warning = "TVA trouvée sur le site web"
        except Exception:
            pass

    # 2. KBO (fallback si pas de TVA via le site)
    if use_kbo and not business.vat_number:
        try:
            hit, score = lookup_vat_via_kbo(
                name=business.name,
                locality=business.locality or business.city or "",
                postal=business.postal_code or "",
                address=business.address or "",
            )
            business.bce_match_score = score
            if hit:
                business.vat_number = hit.vat_number
                business.bce_number = hit.bce_number
                business.legal_form = hit.entity_type or None
                business.bce_status = hit.status or None
                if score < 85:
                    business.bce_match_warning = f"Match KBO faible (score {score}) — à vérifier"
                else:
                    business.bce_match_warning = f"Match KBO (score {score})"
            else:
                business.bce_match_warning = "Aucun match KBO suffisant"
        except Exception as e:
            business.bce_match_warning = f"Erreur KBO : {e}"

    # 3. Fiche détail BCE : dirigeants, date création, capital, NACE
    if use_bce_detail and business.bce_number:
        try:
            _enrich_from_bce_detail(business)
        except Exception:
            pass

    # 4. Données financières (BNB) + solvabilité (CompanyWeb)
    if use_financial and business.bce_number:
        try:
            _enrich_financial(business)
        except Exception:
            pass

    return business


def enrich_all(
    businesses: list[Business],
    on_progress: Optional[Callable[[str], None]] = None,
    delay_between: float = 1.0,
) -> list[Business]:
    total = len(businesses)
    for i, b in enumerate(businesses, start=1):
        if on_progress:
            on_progress(f"Enrichissement ({i}/{total}) : {b.name}")
        enrich_business_with_vat(b)
        if delay_between:
            time.sleep(delay_between)
    return businesses


def enrich_all_parallel(
    businesses: list[Business],
    on_progress: Optional[Callable[[str], None]] = None,
    max_workers: int = 6,
) -> list[Business]:
    total = len(businesses)
    if total == 0:
        return businesses

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_biz = {
            executor.submit(enrich_business_with_vat, b): b for b in businesses
        }
        for fut in as_completed(future_to_biz):
            done += 1
            biz = future_to_biz[fut]
            if on_progress:
                try:
                    fut.result()
                    tag = "[OK]" if biz.vat_number else "[--]"
                except Exception as e:
                    tag = f"[ERR {e}]"
                on_progress(f"Enrichissement ({done}/{total}) {tag} {biz.name}")
    return businesses

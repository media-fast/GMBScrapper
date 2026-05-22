"""Orchestrateur : lance les audits site web + GMB en parallèle."""

from concurrent.futures import ThreadPoolExecutor

from .gmb import audit_gmb
from .website import audit_website


def run_full_audit(business: dict) -> dict:
    """Lance les deux audits en parallèle et calcule un score global."""
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_web = ex.submit(audit_website, business.get("website"))
        f_gmb = ex.submit(audit_gmb, business)
        web = f_web.result()
        gmb = f_gmb.result()

    # Score global = moyenne pondérée (site web 60%, GMB 40%)
    web_score = web.get("score", 0) if web.get("ok") else 0
    gmb_score = gmb.get("score", 0) if gmb.get("ok") else 0
    global_score = round(0.6 * web_score + 0.4 * gmb_score)

    return {
        "website": web,
        "gmb": gmb,
        "global_score": global_score,
    }

"""Orchestrateur : lance les audits site web + GMB en parallèle.

Génère aussi un rapport IA structuré au format Media Fast (si une clé
OpenAI/Anthropic est configurée). Le rapport accentue les points
perfectibles (80 % manques, 20 % positifs) et propose :
  - Points forts / faibles (3 max chacun)
  - Diagnostic présence locale
  - Tableau de pages locales à créer (1 service × 1 commune)
  - Top 10 mots-clés longue traîne
  - Plan d'action priorisé avec emojis colorés
"""

from concurrent.futures import ThreadPoolExecutor

from .gmb import audit_gmb
from .website import audit_website


def run_full_audit(business: dict) -> dict:
    """Lance les audits + génère le rapport IA structuré.

    Returns: {
        "website": dict,        # findings techniques du site
        "gmb": dict,            # findings GMB
        "global_score": int,    # 0-100
        "ai_report": str | None,    # markdown du rapport IA
        "ai_report_meta": dict,     # provider + message
    }
    """
    # 1. Audits techniques en parallèle
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_web = ex.submit(audit_website, business.get("website"))
        f_gmb = ex.submit(audit_gmb, business)
        web = f_web.result()
        gmb = f_gmb.result()

    # 2. Score global (site web 60 %, GMB 40 %)
    web_score = web.get("score", 0) if web.get("ok") else 0
    gmb_score = gmb.get("score", 0) if gmb.get("ok") else 0
    global_score = round(0.6 * web_score + 0.4 * gmb_score)

    # 3. Génération du rapport IA (format strict Media Fast)
    ai_report = None
    ai_report_meta = {"ok": False, "message": "Non généré", "provider": None}
    try:
        from .ai_seo_report import generate_seo_report
        res = generate_seo_report(business, web, gmb)
        ai_report_meta = {
            "ok": res.get("ok", False),
            "message": res.get("message", ""),
            "provider": res.get("provider"),
        }
        if res.get("ok"):
            ai_report = res.get("report")
    except Exception as e:  # noqa: BLE001
        ai_report_meta = {"ok": False, "message": f"Erreur génération IA : {e}",
                          "provider": None}

    return {
        "website": web,
        "gmb": gmb,
        "global_score": global_score,
        "ai_report": ai_report,
        "ai_report_meta": ai_report_meta,
    }

"""Audit Google Business Profile (GBP / GMB) à partir des données déjà scrapées.

Analyse la complétude et la performance de la fiche Google Maps :
- Présence de la fiche
- Catégorie, téléphone, site web, adresse, horaires
- Volume et qualité des avis
- Plus Code (géolocalisation)
"""

from typing import Optional


def _finding(severity: str, title: str, detail: str = "", recommendation: str = "") -> dict:
    return {
        "severity": severity,
        "title": title,
        "detail": detail,
        "recommendation": recommendation,
    }


def audit_gmb(business: dict) -> dict:
    """Analyse la fiche Google Business Profile à partir du dict entreprise."""
    findings: list[dict] = []
    metrics: dict = {}

    if not business.get("gmaps_url"):
        findings.append(_finding(
            "critical", "Pas de fiche Google Business Profile",
            "Aucune fiche Google Maps détectée pour cette entreprise.",
            "Création immédiate d'une fiche GBP — opportunité commerciale prioritaire.",
        ))
        metrics["profile_exists"] = False
        return {"ok": True, "score": 0, "findings": findings, "metrics": metrics}

    metrics["profile_exists"] = True
    findings.append(_finding("ok", "Fiche Google Business Profile présente"))

    # Catégorie principale
    if business.get("category"):
        findings.append(_finding(
            "ok", "Catégorie principale définie",
            f"« {business['category']} »",
        ))
    else:
        findings.append(_finding(
            "warning", "Catégorie principale manquante",
            "Aucune catégorie détectée sur la fiche.",
            "Choisir une catégorie principale précise (impact direct sur le ranking local).",
        ))

    # Téléphone
    if business.get("phone"):
        findings.append(_finding("ok", "Téléphone renseigné", business["phone"]))
    else:
        findings.append(_finding(
            "critical", "Pas de numéro de téléphone",
            "Aucun téléphone visible sur la fiche — les clients ne peuvent pas appeler.",
            "Ajouter un numéro de téléphone (clic-to-call mobile).",
        ))

    # Site web lié
    if business.get("website"):
        findings.append(_finding(
            "ok", "Site web lié à la fiche",
            business["website"],
        ))
    else:
        findings.append(_finding(
            "warning", "Pas de site web lié",
            "Aucun site web associé à la fiche Google Maps.",
            "Lier un site web — augmente les conversions et le SEO local.",
        ))

    # Adresse
    if business.get("address"):
        findings.append(_finding("ok", "Adresse renseignée", business["address"]))
    else:
        findings.append(_finding(
            "warning", "Adresse incomplète",
            "Adresse non détectée — impact négatif sur le référencement local.",
            "Compléter l'adresse exacte sur la fiche.",
        ))

    # Horaires
    if business.get("hours"):
        findings.append(_finding(
            "ok", "Horaires d'ouverture visibles",
            (business["hours"][:80] + "…") if len(business["hours"]) > 80 else business["hours"],
        ))
    else:
        findings.append(_finding(
            "warning", "Horaires d'ouverture manquants",
            "Pas d'horaires affichés sur la fiche.",
            "Renseigner les horaires (jours fériés inclus) — booste le taux de clic vers l'établissement.",
        ))

    # Avis
    rating = business.get("rating")
    rcount = int(business.get("reviews_count") or 0)
    metrics["rating"] = rating
    metrics["reviews_count"] = rcount

    if not rating or rcount == 0:
        findings.append(_finding(
            "critical", "Aucun avis Google",
            "La fiche n'a pas d'avis clients.",
            "Lancer une campagne de collecte d'avis (objectif : 10-20 avis pour démarrer).",
        ))
    else:
        try:
            rating_f = float(rating)
        except (TypeError, ValueError):
            rating_f = 0.0

        if rcount < 10:
            findings.append(_finding(
                "warning", f"Peu d'avis ({rcount})",
                f"Note {rating}/5 sur seulement {rcount} avis — manque de crédibilité.",
                "Cibler 30+ avis pour gagner en visibilité dans le pack local.",
            ))
        elif rating_f < 3.5:
            findings.append(_finding(
                "critical", f"Note basse ({rating}/5 sur {rcount} avis)",
                "Réputation en ligne dégradée.",
                "Audit des avis négatifs + stratégie de réponse + plan de collecte de nouveaux avis.",
            ))
        elif rating_f < 4.0:
            findings.append(_finding(
                "warning", f"Note moyenne ({rating}/5 sur {rcount} avis)",
                "Marge de progression sur la satisfaction client.",
                "Analyse des avis pour identifier les axes d'amélioration.",
            ))
        elif rcount < 30:
            findings.append(_finding(
                "ok", f"Bonne note ({rating}/5)",
                f"{rcount} avis — encore de la marge pour renforcer l'autorité locale.",
                "Continuer à collecter activement (objectif 50+).",
            ))
        else:
            findings.append(_finding(
                "ok", f"Excellente réputation ({rating}/5 sur {rcount} avis)",
                "Atout majeur pour le référencement local.",
            ))

    # Plus Code (présence géo précise)
    if business.get("plus_code"):
        findings.append(_finding("ok", "Géolocalisation précise (Plus Code)"))

    # Score
    score = 100
    for f in findings:
        if f["severity"] == "critical":
            score -= 15
        elif f["severity"] == "warning":
            score -= 6
    score = max(0, score)

    return {"ok": True, "score": score, "findings": findings, "metrics": metrics}

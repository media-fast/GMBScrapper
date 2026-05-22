"""Synonymes et requêtes alternatives pour multiplier la couverture Google Maps.

Une seule recherche `opticien` ne récupère pas les fiches indexées seulement sous
`lunetterie` ou `magasin de lunettes`. En lançant les 3 variantes, on triple
le pool de fiches (dédupliquées en aval).

Usage :
    metiers = ["opticien", "dentiste"]
    expanded = expand_metier_synonyms(metiers)
    # → ["opticien", "lunetterie", "magasin de lunettes", "optique",
    #    "dentiste", "cabinet dentaire", "orthodontiste"]
"""

from typing import Iterable


# Dictionnaire métier canonique → variantes à interroger sur Google Maps.
# La 1re entrée est le métier original (clé) pour garantir qu'on ne dérive pas
# trop. Les variantes suivantes élargissent la couverture.
METIER_SYNONYMS: dict[str, list[str]] = {
    # Santé / paramédical
    "opticien": [
        "opticien", "lunetterie", "magasin de lunettes", "optique",
    ],
    "audioprothésiste": [
        "audioprothésiste", "prothèses auditives", "appareils auditifs",
        "audicien",
    ],
    "orthopédiste": [
        "orthopédiste", "orthopédie", "magasin d'orthopédie",
        "matériel orthopédique",
    ],
    "ostéopathe": [
        "ostéopathe", "cabinet ostéopathie", "ostéopathie",
    ],
    "dentiste": [
        "dentiste", "cabinet dentaire", "orthodontiste", "stomatologue",
    ],
    "kinésithérapeute": [
        "kinésithérapeute", "kiné", "cabinet de kinésithérapie",
        "physiothérapeute",
    ],
    "pharmacie": [
        "pharmacie", "pharmacien",
    ],
    "médecin généraliste": [
        "médecin généraliste", "cabinet médical", "médecin de famille",
    ],

    # Bâtiment / second œuvre
    "plombier": [
        "plombier", "sanitaire", "chauffagiste", "plomberie",
    ],
    "électricien": [
        "électricien", "installation électrique", "électricité générale",
    ],
    "chauffagiste": [
        "chauffagiste", "chauffage central", "installation chauffage",
    ],
    "menuisier": [
        "menuisier", "menuiserie", "menuiserie sur mesure",
    ],

    # Automobile
    "garage automobile": [
        "garage automobile", "garage", "mécanicien auto", "réparation auto",
        "entretien voiture",
    ],
    "carrosserie": [
        "carrosserie", "tôlerie", "réparation carrosserie",
    ],

    # Commerces de bouche
    "restaurant": [
        "restaurant", "brasserie", "bistrot", "restaurant gastronomique",
    ],
    "boulangerie": [
        "boulangerie", "boulanger", "boulangerie pâtisserie",
    ],
    "boucherie": [
        "boucherie", "boucher", "charcuterie",
    ],
    "fleuriste": [
        "fleuriste", "fleurs", "magasin de fleurs",
    ],

    # Beauté
    "coiffeur": [
        "coiffeur", "salon de coiffure",
    ],
    "esthéticienne": [
        "esthéticienne", "institut de beauté",
    ],
    "salon de beauté": [
        "salon de beauté", "centre esthétique", "spa",
    ],

    # Services pro
    "avocat": [
        "avocat", "cabinet d'avocats",
    ],
    "comptable": [
        "comptable", "expert-comptable", "cabinet comptable",
        "fiduciaire",
    ],
    "notaire": [
        "notaire", "étude notariale",
    ],
    "agent immobilier": [
        "agent immobilier", "agence immobilière",
    ],
}


def expand_metier_synonyms(
    metiers: Iterable[str],
    enabled: bool = True,
) -> list[str]:
    """Étend une liste de métiers avec leurs variantes/synonymes.

    Si `enabled=False`, la liste est renvoyée telle quelle (toggle UI off).
    Les doublons (case-insensitive) sont dédupliqués mais l'ordre d'apparition
    est conservé.

    Pour un métier inconnu (non listé dans METIER_SYNONYMS), il est conservé
    tel quel sans variantes.
    """
    if not enabled:
        return [m for m in metiers if m and m.strip()]

    seen: set[str] = set()
    expanded: list[str] = []
    for m in metiers:
        if not m or not m.strip():
            continue
        key = m.strip().lower()
        variants = METIER_SYNONYMS.get(key, [m])
        for v in variants:
            v_low = v.strip().lower()
            if v_low and v_low not in seen:
                seen.add(v_low)
                expanded.append(v.strip())
    return expanded


def estimate_synonym_multiplier(metiers: Iterable[str]) -> float:
    """Estime le facteur multiplicateur moyen (nombre moyen de variantes par métier)."""
    metiers_list = [m.strip().lower() for m in metiers if m and m.strip()]
    if not metiers_list:
        return 1.0
    total = sum(len(METIER_SYNONYMS.get(m, [m])) for m in metiers_list)
    return total / len(metiers_list)

"""Tests pour enrichment.nbb_scraper (parsing pur, sans Playwright)."""

import pytest

from enrichment.nbb_scraper import _parse_page_text


# Échantillon réel observé sur consult.cbso.nbb.be (BCE 0424735977)
SAMPLE_PEARLE = """Fr
Centrale des bilans
Consultation des comptes annuels
Recherche surListe des dépôts
Nouvelle recherche
0424735977
Grand Opticiens Belgium
Stationsstraat, 102-108
2800 Mechelen Belgïe


Forme juridique

Société anonyme

Situation juridique

Situation normale

Banque carrefour des entreprises
Comptes annuels et autres documents reçus et acceptés
Tout sélectionner
42 résultat(s)
Par page
10
Volledig model kapitaalvennootschap
Initial
Référence 2025-00335501Date de dépôt 29/07/2025
Date de fin d'exercice
31/12/2024
NL
Volledig model kapitaalvennootschap
Initial
Référence 2024-00474103Date de dépôt 23/09/2024
Date de fin d'exercice
31/12/2023
NL
"""

# Échantillon en français (BCE 0820154202 — Modèle abrégé)
SAMPLE_OPTIL = """Fr
Centrale des bilans
0820154202
OPTIL Waterloo
15 résultat(s)
Modèle abrégé société à capital
Initial
Référence 2025-00100000Date de dépôt 01/07/2025
Date de fin d'exercice
31/12/2024
FR
Modèle abrégé société à capital
Initial
Référence 2024-00099999Date de dépôt 28/06/2024
Date de fin d'exercice
31/12/2023
FR
"""

# Échantillon vide (BCE 0496518357 — Nooz Opticien : aucun dépôt)
SAMPLE_EMPTY = "En\nNouvelle recherche"


class TestParseFullModel:
    def test_extracts_latest_deposit_date(self):
        r = _parse_page_text(SAMPLE_PEARLE)
        assert r is not None
        assert r["deposit_date"] == "2025-07-29"

    def test_extracts_latest_exercise_year(self):
        r = _parse_page_text(SAMPLE_PEARLE)
        assert r["year"] == "2024"

    def test_extracts_model_type_full(self):
        # "Volledig model" → FULL en NL
        r = _parse_page_text(SAMPLE_PEARLE)
        assert r["model_type"] == "FULL"

    def test_extracts_deposits_count(self):
        r = _parse_page_text(SAMPLE_PEARLE)
        assert r["deposits_count"] == 42


class TestParseAbbreviatedModel:
    def test_extracts_abbreviated_model_fr(self):
        r = _parse_page_text(SAMPLE_OPTIL)
        assert r is not None
        assert r["model_type"] == "ABBREVIATED"
        assert r["year"] == "2024"
        assert r["deposit_date"] == "2025-07-01"
        assert r["deposits_count"] == 15


class TestParseEmptyPage:
    def test_no_deposit_returns_none(self):
        r = _parse_page_text(SAMPLE_EMPTY)
        assert r is None

    def test_empty_string_returns_none(self):
        assert _parse_page_text("") is None

    def test_random_text_without_dates_returns_none(self):
        assert _parse_page_text("Hello world, no deposit data here") is None


class TestModelDetectionVariants:
    @pytest.mark.parametrize("snippet,expected", [
        ("Modèle complet société anonyme", "FULL"),
        ("Modèle abrégé entreprise", "ABBREVIATED"),
        ("Modèle micro société", "MICRO"),
        ("Volledig schema kapitaalvennootschap", "FULL"),
        ("Verkort schema entreprise", "ABBREVIATED"),
        ("Micro-schema vennootschap", "MICRO"),
    ])
    def test_model_keywords(self, snippet, expected):
        text = (
            f"42 résultat(s)\n{snippet}\nInitial\n"
            f"Référence 2024-001Date de dépôt 15/06/2024\n"
            f"Date de fin d'exercice\n31/12/2023\nFR"
        )
        r = _parse_page_text(text)
        assert r is not None
        assert r["model_type"] == expected


class TestDateApostropheVariants:
    """L'exercice peut être écrit avec apostrophe courbe (') ou droite (')."""

    def test_curly_apostrophe(self):
        text = (
            "1 résultat(s)\nModèle abrégé\nInitial\n"
            "Référence 2024-001Date de dépôt 15/06/2024\n"
            "Date de fin d'exercice\n31/12/2023\nFR"
        )
        r = _parse_page_text(text)
        assert r is not None
        assert r["year"] == "2023"

    def test_straight_apostrophe(self):
        text = (
            "1 résultat(s)\nModèle abrégé\nInitial\n"
            "Référence 2024-001Date de dépôt 15/06/2024\n"
            "Date de fin d'exercice\n31/12/2023\nFR"
        )
        r = _parse_page_text(text)
        assert r is not None
        assert r["year"] == "2023"

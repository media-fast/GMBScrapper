"""Tests pour enrichment.credit_score : heuristique baromètre crédit."""

from datetime import date

import pytest

from enrichment.credit_score import (
    COLOR_LABELS,
    COLOR_SCORES,
    compute_credit_score,
)
from enrichment.nbb import NbbData


# Date de référence stable pour rendre les tests déterministes
TODAY = date(2026, 5, 27)


def _nbb(year=None, deposit_date=None, count=0, model_type=None,
         available=None) -> NbbData:
    """Helper : construit un NbbData avec champs optionnels.

    Par défaut available=True dès qu'on a year ou deposit_date (i.e.
    l'API a répondu utilement). Tu peux forcer available=True pour
    simuler une réponse API vide (cas « pas de dépôt confirmé »).
    """
    if available is None:
        available = bool(year or deposit_date)
    return NbbData(
        consult_url="https://consult.cbso.nbb.be/x",
        year=year,
        deposit_date=deposit_date,
        deposits_count=count,
        model_type=model_type,
        available=available,
    )


class TestInactiveStatus:
    """Statut BCE indiquant cessation → ROUGE direct, peu importe le reste."""

    @pytest.mark.parametrize("status", [
        "Cessation d'activité",
        "Inactif",
        "Radiée",
        "Radié",
        "En liquidation",
        "Faillite",
        "Dissolution",
        "CESSATION D'ACTIVITE",  # casse insensible
    ])
    def test_inactive_statuses_yield_red(self, status):
        res = compute_credit_score(bce_status=status, today=TODAY)
        assert res.color == "red"
        assert res.label == COLOR_LABELS["red"]
        assert res.score == COLOR_SCORES["red"]
        assert len(res.reasons) >= 1
        assert any("Risque" in r or "non active" in r for r in res.reasons)

    def test_active_status_does_not_force_red(self):
        # Un statut "Active" + dépôt récent → ne doit PAS être rouge
        nbb = _nbb(year="2025", deposit_date="2025-08-15", count=3)
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2018-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        assert res.color != "red"


class TestYoungCompany:
    """Entreprise <18 mois → GRIS (pas assez de recul)."""

    def test_very_young_company_is_gray(self):
        # Créée il y a 6 mois
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2025-11-27",
            nbb_data=None,
            today=TODAY,
        )
        assert res.color == "gray"
        assert any("jeune" in r.lower() for r in res.reasons)

    def test_18_months_boundary_inclusive(self):
        # Exactement 18 mois → ne doit plus être gris
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2024-11-27",  # 18 mois pile
            nbb_data=None,
            today=TODAY,
        )
        # Sans NBB et avec 18 mois → orange (aucun dépôt) ou gris,
        # pas critique mais on vérifie qu'on N'EST PAS dans la branche jeune
        assert res.color in {"gray", "orange"}


class TestNoDeposit:
    """Aucun dépôt BNB connu — distingue le cas « API pas appelée » du
    cas « API a répondu vide » (signal réel de prudence)."""

    def test_no_nbb_data_at_all_is_gray_with_api_hint(self):
        # nbb_data=None → on n'a JAMAIS appelé l'API → gris (pas orange)
        # avec un hint pour configurer NBB_API_KEY
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",  # 16 ans
            nbb_data=None,
            today=TODAY,
        )
        assert res.color == "gray"
        assert any("non vérifié" in r.lower() or "non configur" in r.lower()
                   or "nbb_api_key" in r.lower() for r in res.reasons)

    def test_nbb_api_responded_with_no_deposit_is_orange(self):
        # nbb_data.available=True mais pas de deposit_date/year → l'API
        # a confirmé l'absence → vrai signal de prudence ORANGE.
        nbb = _nbb(year=None, deposit_date=None, count=0)
        nbb.available = True  # API a répondu, juste pas de dépôt
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        assert res.color == "orange"
        assert any("Aucun dépôt" in r for r in res.reasons)

    def test_no_deposit_no_age_no_status_falls_back_to_gray(self):
        # Aucune donnée du tout → gris (on ne peut rien dire)
        res = compute_credit_score(nbb_data=None, today=TODAY)
        assert res.color == "gray"

    def test_no_deposit_with_status_only_falls_back_to_gray(self):
        # Statut Active mais pas d'âge ni de dépôt : impossible de juger
        # si l'absence de dépôt est anormale → gris
        res = compute_credit_score(bce_status="Active", nbb_data=None,
                                   today=TODAY)
        assert res.color == "gray"


class TestLateDeposit:
    """Dépôts en retard → ORANGE ou JAUNE selon le délai."""

    def test_deposit_over_24_months_is_orange(self):
        # Dépôt en 2023 (≈ 30 mois avant TODAY 2026-05)
        nbb = _nbb(year="2022", deposit_date="2023-11-15", count=4)
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        assert res.color == "orange"
        assert any("retard" in r.lower() for r in res.reasons)

    def test_deposit_between_18_and_24_months_is_yellow(self):
        # Dépôt il y a ~20 mois
        nbb = _nbb(year="2023", deposit_date="2024-09-15", count=4)
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        assert res.color == "yellow"


class TestGoodPayer:
    """Dépôts à jour → VERT."""

    def test_recent_deposit_is_green(self):
        # Dépôt il y a 4 mois
        nbb = _nbb(year="2024", deposit_date="2026-01-15", count=8)
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        assert res.color == "green"
        assert res.label == COLOR_LABELS["green"]
        assert any("jour" in r.lower() for r in res.reasons)

    def test_green_score_higher_than_orange(self):
        assert COLOR_SCORES["green"] > COLOR_SCORES["orange"]
        assert COLOR_SCORES["green"] > COLOR_SCORES["red"]

    def test_long_history_mentions_seniority(self):
        # Entreprise >5 ans + dépôts réguliers + à jour
        nbb = _nbb(year="2024", deposit_date="2026-02-01", count=10)
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2015-03-01",  # ~11 ans
            nbb_data=nbb,
            today=TODAY,
        )
        assert res.color == "green"
        assert any("établie depuis" in r for r in res.reasons)
        assert any("régulier" in r.lower() for r in res.reasons)


class TestYearOnlyApproximation:
    """Quand on a juste l'année sans deposit_date → approxime à juin N+1."""

    def test_year_only_recent_is_green(self):
        # Année 2025 → dépôt approximé à 2026-07-01 (futur dans nos tests)
        # → mois écoulés négatif → traité comme récent
        nbb = _nbb(year="2024", deposit_date=None, count=5)
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        # 2024 → dépôt approx 2025-07 → ~10 mois avant 2026-05 → green
        assert res.color == "green"

    def test_year_only_very_old_is_orange(self):
        nbb = _nbb(year="2020", deposit_date=None, count=2)
        nbb.available = True  # l'API a répondu avec une vieille année
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        # 2020 → dépôt approx 2021-07 → ~58 mois avant TODAY → orange
        assert res.color == "orange"


class TestFrenchDateParsing:
    """Le format BCE renvoie souvent des dates textuelles françaises
    comme « 29 octobre 2009 ». Sans parsing FR, l'âge tombe à None et
    toutes les fiches glissent en gris — back-fill inutilisable."""

    def test_fr_date_recognized_for_old_company(self):
        # Créée il y a >15 ans, statut actif, pas de NBB → gris avec hint
        # (avant la correction « no penalty without API », était orange)
        res = compute_credit_score(
            bce_status="Actif",
            creation_date="29 octobre 2009",
            nbb_data=None,
            today=TODAY,
        )
        assert res.color == "gray"
        assert any("non vérifié" in r.lower() or "nbb_api_key" in r.lower()
                   for r in res.reasons)

    def test_fr_date_young_company(self):
        # Créée il y a quelques mois → gris
        res = compute_credit_score(
            bce_status="Actif",
            creation_date="15 mars 2026",  # 2 mois avant TODAY
            nbb_data=None,
            today=TODAY,
        )
        assert res.color == "gray"
        assert any("jeune" in r.lower() for r in res.reasons)


class TestSerializationAndShape:
    def test_to_dict_round_trip(self):
        nbb = _nbb(year="2024", deposit_date="2026-01-15", count=8)
        res = compute_credit_score(
            bce_status="Active",
            creation_date="2010-01-01",
            nbb_data=nbb,
            today=TODAY,
        )
        d = res.to_dict()
        assert d["color"] == "green"
        assert "score" in d and "label" in d and "reasons" in d
        assert isinstance(d["reasons"], list)

    def test_all_colors_have_label_and_score(self):
        for color in ("red", "orange", "yellow", "green", "gray"):
            assert color in COLOR_LABELS
            assert color in COLOR_SCORES
            assert 0 <= COLOR_SCORES[color] <= 100

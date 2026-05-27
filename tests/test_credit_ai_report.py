"""Tests pour enrichment.credit_ai_report (Phase 2 — popup IA crédit).

On ne teste PAS l'appel HTTP réel : on mock httpx pour valider la logique
de provider detection, le build du prompt, et le format de retour.
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from enrichment import credit_ai_report
from enrichment.credit_ai_report import (
    _build_user_prompt,
    _fmt_eur,
    _ratio_div,
    _ratio_pct,
    generate_credit_report,
    is_configured,
)


class TestProviderDetection:
    def test_no_keys_means_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            assert not is_configured()

    def test_openai_key_configures(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            assert is_configured()

    def test_anthropic_key_configures(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True):
            assert is_configured()

    def test_forced_openai_falls_back_if_no_key(self):
        with patch.dict(os.environ, {
            "AI_BRIEFING_PROVIDER": "openai",
            "ANTHROPIC_API_KEY": "sk-ant",
        }, clear=True):
            # Forced openai mais pas de clé openai → fallback anthropic
            assert is_configured()


class TestFormatters:
    # _fmt_eur utilise \xa0 (espace insécable) comme séparateur de
    # milliers — convention française. Les tests utilisent NBSP aussi.
    NBSP = "\xa0"

    @pytest.mark.parametrize("v,expected", [
        (None, "Non disponible"),
        (0, "0 €"),
        (1000, f"1{NBSP}000 €"),
        (1500000, f"1{NBSP}500{NBSP}000 €"),
        ("invalid", "Non disponible"),
    ])
    def test_fmt_eur(self, v, expected):
        assert _fmt_eur(v) == expected

    def test_ratio_pct(self):
        assert _ratio_pct(50, 200) == "25.0 %"
        assert _ratio_pct(None, 200) == "Non disponible"
        assert _ratio_pct(50, 0) == "Non disponible"
        assert _ratio_pct(50, None) == "Non disponible"

    def test_ratio_div(self):
        assert _ratio_div(150, 100) == "1.50"
        assert _ratio_div(None, 100) == "Non disponible"
        assert _ratio_div(100, 0) == "Non disponible"


class TestUserPromptBuilder:
    def test_prompt_includes_essential_fields(self):
        business = {
            "name": "Test SPRL",
            "bce_number": "0123.456.789",
            "bce_status": "Active",
            "creation_date": "2010-01-01",
            "credit_color": "green",
            "credit_label": "Bon payeur",
            "credit_reasons": '["Dépôts à jour"]',
        }
        nbb_meta = {"year": "2024", "deposit_date": "2025-08-01",
                    "model_type": "ABBREVIATED", "deposits_count": 8}
        accounting = {
            "10/15": 150000.0,
            "17/49": 80000.0,
            "20/58": 280000.0,
            "9904": 25000.0,
        }
        heuristic = {"color": "green", "label": "Bon payeur",
                     "reasons": ["Dépôts à jour"]}

        prompt = _build_user_prompt(business, nbb_meta, accounting, heuristic)

        # Champs essentiels présents
        assert "Test SPRL" in prompt
        assert "0123.456.789" in prompt
        assert "Active" in prompt
        assert "2024" in prompt
        assert "150\xa0000 €" in prompt      # capitaux propres formatés (NBSP)
        assert "GREEN" in prompt             # heuristique couleur upper
        assert "Bon payeur" in prompt
        # Solvabilité = 150000/280000 = 53.6%
        assert "53.6 %" in prompt

    def test_prompt_handles_missing_accounting_gracefully(self):
        business = {"name": "Petite SARL", "bce_number": "0999.999.999"}
        nbb_meta = {"year": None, "deposit_date": None, "deposits_count": 0}
        accounting = {}  # aucune donnée
        heuristic = {"color": "gray", "label": "Données insuffisantes",
                     "reasons": []}

        prompt = _build_user_prompt(business, nbb_meta, accounting, heuristic)
        assert "Petite SARL" in prompt
        # Tous les codes doivent dire "Non disponible"
        assert prompt.count("Non disponible") >= 5
        assert "GRAY" in prompt


class TestGenerateCreditReport:
    def test_no_provider_returns_friendly_error(self):
        with patch.dict(os.environ, {}, clear=True):
            res = generate_credit_report({"bce_number": "0123.456.789",
                                          "name": "Test"})
            assert res["ok"] is False
            assert "Aucune clé IA" in res["message"]
            assert res["provider"] is None
            assert res["report"] == ""

    def test_with_openai_calls_openai_endpoint(self):
        # Mock httpx.Client.post pour retourner un faux succès OpenAI
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "**Analyse crédit — Test**\n\nVerdict : 🟢 BON PAYEUR"}}]
        }

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch("httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.post.return_value = mock_response
                # Mock aussi fetch_nbb_financials pour éviter un vrai appel réseau
                with patch("enrichment.credit_ai_report._fetch_accounting_data",
                           return_value={}):
                    res = generate_credit_report({
                        "bce_number": "0123.456.789",
                        "name": "Test SPRL",
                        "credit_color": "green",
                    })

        assert res["ok"] is True
        assert res["provider"] == "openai"
        assert "BON PAYEUR" in res["report"]
        assert res["accounting_codes_count"] == 0

    def test_api_error_returns_friendly_message(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            with patch("httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.post.return_value = mock_response
                with patch("enrichment.credit_ai_report._fetch_accounting_data",
                           return_value={}):
                    res = generate_credit_report({
                        "bce_number": "0123.456.789", "name": "Test",
                    })

        assert res["ok"] is False
        assert "500" in res["message"]

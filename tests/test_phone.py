"""Tests pour enrichment.website._normalize_phone et _extract_phone."""

import pytest

from enrichment.website import _normalize_phone, _extract_phone


class TestNormalizePhone:
    @pytest.mark.parametrize("raw,expected", [
        # Format international Bruxelles (02)
        ("+32 2 354 12 88", "+3223541288"),
        ("0032 2 354 12 88", "+3223541288"),
        ("02 354 12 88", "+3223541288"),
        ("(+32) 2/354.12.88", "+3223541288"),
        # Format international Liège (04)
        ("+32 4 234 56 78", "+3242345678"),
        # Mobile (047X / 048X / 049X)
        ("+32 475 12 34 56", "+32475123456"),
        ("0475/12.34.56", "+32475123456"),
        ("0475-12-34-56", "+32475123456"),
        ("04 75 12 34 56", "+32475123456"),
        # Avec parenthèses et tirets mixés
        ("0(2) 354-12-88", "+3223541288"),
    ])
    def test_valid_belgian_phones(self, raw, expected):
        assert _normalize_phone(raw) == expected

    @pytest.mark.parametrize("raw", [
        "+33 1 23 45 67 89",       # France
        "+44 20 7946 0958",        # UK
        "123",                      # trop court
        "",                         # vide
        None,                       # None
        "abc",                      # pas de chiffres
        "0",                        # un seul chiffre
        "00 32",                    # vide après préfixe
    ])
    def test_invalid_phones_return_none(self, raw):
        assert _normalize_phone(raw) is None


class TestExtractPhoneFromHtml:
    def test_tel_link_is_most_reliable(self):
        html = '<a href="tel:+32475123456">Appelez-nous</a>'
        assert _extract_phone(html) == "+32475123456"

    def test_callto_link(self):
        html = '<a href="callto:0475123456">Appel</a>'
        assert _extract_phone(html) == "+32475123456"

    def test_text_only_with_hint(self):
        html = "<p>Tél : 02 354 12 88</p>"
        assert _extract_phone(html) == "+3223541288"

    def test_text_only_no_hint(self):
        html = "<div>0475/12.34.56 ou autre chose</div>"
        result = _extract_phone(html)
        assert result == "+32475123456"

    def test_returns_none_when_no_phone(self):
        html = "<p>Notre adresse : 1410 Waterloo. Email contact@x.be</p>"
        assert _extract_phone(html) is None

    def test_tel_link_priority_over_regex(self):
        # Le tel: link est différent d'un numéro dans le texte —
        # le tel: doit gagner
        html = '<p>Bureau : 02 999 99 99</p><a href="tel:+32475111111">Mobile</a>'
        assert _extract_phone(html) == "+32475111111"

    def test_picks_first_valid_phone_when_multiple_in_text(self):
        html = "<div>02 354 12 88 ou 02 354 12 89</div>"
        result = _extract_phone(html)
        # On accepte n'importe lequel des deux (l'ordre dépend du scoring)
        assert result in ("+3223541288", "+3223541289")

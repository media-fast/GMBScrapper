"""Tests pour scraper.gmaps._detect_google_block.

Mock minimal d'une page Playwright pour tester la logique de détection
sans avoir besoin d'un vrai navigateur. On ne teste pas l'exception
GoogleBlockedError elle-même (couvert par le smoke test au démarrage).
"""

import asyncio

import pytest

from scraper.gmaps import _detect_google_block


class FakePage:
    """Mock minimal d'une Page Playwright pour _detect_google_block."""

    def __init__(self, url="", title="", body_text="", captcha_form=False):
        self.url = url
        self._title = title
        self._body_text = body_text
        self._captcha_form = captcha_form

    async def query_selector(self, selector):
        # On simule un retour "truthy" pour le selector CAPTCHA
        if self._captcha_form and "captcha" in selector.lower():
            return object()  # n'importe quel objet non-None = truthy
        return None

    async def title(self):
        return self._title

    async def evaluate(self, _script):
        # On renvoie le body_text en lowercase (comme le vrai script)
        return self._body_text.lower()


def _run(coro):
    """Helper pour exécuter un coroutine en sync dans un test."""
    return asyncio.run(coro)


class TestDetectGoogleBlock:
    def test_normal_page_returns_none(self):
        page = FakePage(
            url="https://www.google.com/maps/search/dentiste+waterloo",
            title="dentiste waterloo - Google Maps",
            body_text="Résultats pour dentiste à Waterloo",
        )
        assert _run(_detect_google_block(page)) is None

    def test_sorry_url_detected(self):
        page = FakePage(
            url="https://www.google.com/sorry/index?continue=https://maps.google.com",
            title="",
            body_text="",
        )
        result = _run(_detect_google_block(page))
        assert result is not None
        assert "/sorry/" in result

    def test_recaptcha_url_detected(self):
        page = FakePage(
            url="https://www.google.com/recaptcha/api2/anchor",
        )
        result = _run(_detect_google_block(page))
        assert result is not None
        assert "/recaptcha/" in result

    def test_captcha_form_selector_detected(self):
        page = FakePage(
            url="https://www.google.com/maps",
            captcha_form=True,
        )
        result = _run(_detect_google_block(page))
        assert result is not None
        assert "CAPTCHA" in result or "captcha" in result.lower()

    def test_suspicious_title_detected(self):
        page = FakePage(
            url="https://www.google.com/maps",
            title="Sorry...",
        )
        result = _run(_detect_google_block(page))
        assert result is not None
        assert "sorry" in result.lower()

    @pytest.mark.parametrize("body_text", [
        "Our systems have detected unusual traffic from your network",
        "Nos systèmes ont détecté un trafic inhabituel sur ce réseau",
        "Verify you are a human by clicking below",
        "Pour continuer, vérifier que vous êtes bien humain",
    ])
    def test_block_text_in_body_detected(self, body_text):
        page = FakePage(
            url="https://www.google.com/maps",
            body_text=body_text,
        )
        result = _run(_detect_google_block(page))
        assert result is not None, f"Should detect block in: {body_text!r}"

    def test_innocuous_body_text_not_detected(self):
        page = FakePage(
            url="https://www.google.com/maps/search/dentiste",
            body_text="Voici les résultats de votre recherche pour dentiste à Waterloo.",
        )
        assert _run(_detect_google_block(page)) is None

    def test_exception_in_url_does_not_crash(self):
        """Si page.url lève (rare), la détection ne doit pas crasher."""
        class BrokenPage:
            @property
            def url(self):
                raise RuntimeError("connection lost")

            async def query_selector(self, _):
                return None

            async def title(self):
                return ""

            async def evaluate(self, _):
                return ""

        # Doit retourner None (pas d'exception) puisque les autres checks passent
        assert _run(_detect_google_block(BrokenPage())) is None

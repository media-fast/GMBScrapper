import asyncio
import os
import re
from typing import Callable, Optional
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

from .models import Business

# playwright-stealth (optionnel) : patches d'évasion (navigator.webdriver, plugins,
# WebGL, sec-ch-ua, hairline…). Si non installé, on bascule sur un fallback manuel.
# Requiert v2.0+ pour l'API `Stealth` class — cf. requirements.txt.
try:
    from playwright_stealth import Stealth
    _STEALTH_AVAILABLE = True
except ImportError:
    Stealth = None  # type: ignore
    _STEALTH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Profil navigateur
# ---------------------------------------------------------------------------

# Chrome récent (mai 2026). Mettre à jour quand des nouvelles versions deviennent
# largement déployées pour éviter le flag "navigateur obsolète".
CHROME_VERSION_FULL = "130.0.6723.92"
CHROME_VERSION_MAJOR = "130"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    f"Chrome/{CHROME_VERSION_MAJOR}.0.0.0 Safari/537.36"
)

# Sec-CH-UA cohérent avec User-Agent (Chrome 130)
SEC_CH_UA = (
    f'"Chromium";v="{CHROME_VERSION_MAJOR}", '
    f'"Google Chrome";v="{CHROME_VERSION_MAJOR}", '
    f'"Not?A_Brand";v="99"'
)


# Coordonnées (lat, lng) des principaux chefs-lieux belges pour aligner la
# géolocalisation avec la ville recherchée. Fallback : centre de Bruxelles.
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "bruxelles":    (50.8503, 4.3517),
    "waterloo":     (50.7172, 4.3995),
    "braine-l'alleud": (50.6826, 4.3699),
    "nivelles":     (50.5980, 4.3239),
    "wavre":        (50.7173, 4.6068),
    "ottignies":    (50.6649, 4.5677),
    "la hulpe":     (50.7300, 4.4859),
    "tubize":       (50.6912, 4.2010),
    "halle":        (50.7333, 4.2378),
    "namur":        (50.4674, 4.8720),
    "liege":        (50.6326, 5.5797),
    "liège":        (50.6326, 5.5797),
    "charleroi":    (50.4108, 4.4446),
    "mons":         (50.4542, 3.9560),
    "tournai":      (50.6056, 3.3893),
    "louvain":      (50.8798, 4.7005),
    "leuven":       (50.8798, 4.7005),
    "anvers":       (51.2194, 4.4025),
    "antwerpen":    (51.2194, 4.4025),
    "gent":         (51.0543, 3.7174),
    "gand":         (51.0543, 3.7174),
    "bruges":       (51.2093, 3.2247),
    "brugge":       (51.2093, 3.2247),
    "arlon":        (49.6837, 5.8164),
    "bastogne":     (50.0023, 5.7180),
    "dinant":       (50.2603, 4.9128),
    "verviers":     (50.5879, 5.8631),
    "hasselt":      (50.9307, 5.3378),
}
_DEFAULT_COORDS = (50.8503, 4.3517)  # Bruxelles


def _coords_for_city(city: str) -> dict[str, float]:
    """Coordonnées GPS d'une ville belge pour aligner la géolocalisation du navigateur."""
    key = (city or "").strip().lower()
    lat, lng = _CITY_COORDS.get(key, _DEFAULT_COORDS)
    return {"latitude": lat, "longitude": lng}


def _running_in_docker() -> bool:
    """Détecte si on tourne dans un container Docker (sandbox Chrome problématique)."""
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read() or "containerd" in f.read()
    except (FileNotFoundError, OSError):
        return False


def _build_stealth() -> Optional["Stealth"]:
    """Construit une instance Stealth configurée pour un profil Chrome belge réaliste.

    Retourne None si la lib `playwright-stealth>=2.0` n'est pas installée.
    """
    if not _STEALTH_AVAILABLE:
        return None
    return Stealth(
        navigator_languages_override=("fr-BE", "fr", "en-US", "en"),
        navigator_platform_override="Win32",
        # Override du User-Agent géré côté contexte Playwright (pas ici)
        # Toutes les autres évasions par défaut sont activées.
    )


# Plugins pseudo-réalistes utilisés UNIQUEMENT en fallback (sans playwright-stealth).
# Un `navigator.plugins = [1,2,3,4,5]` est trivialement détectable ; ici on simule
# les vrais Plugin objects que Chrome expose.
_FALLBACK_INIT_SCRIPT = """
(() => {
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  const fakePlugins = [
    { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
  ];
  Object.defineProperty(navigator, 'plugins', {
    get: () => Object.assign(fakePlugins, { length: fakePlugins.length, item: (i) => fakePlugins[i] }),
  });
  Object.defineProperty(navigator, 'languages', { get: () => ['fr-BE', 'fr', 'en-US', 'en'] });
})();
"""


GMAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}"
RESULTS_FEED_SELECTOR = "div[role='feed']"
RESULT_CARD_SELECTOR = "a.hfpxzc"
DETAIL_NAME_SELECTOR = "h1.DUwDvf"
CONSENT_BUTTONS = [
    "button:has-text('Tout accepter')",
    "button:has-text('Accept all')",
    "button:has-text('Tout refuser')",
    "button:has-text('Reject all')",
]

POSTAL_RE = re.compile(r"\b(\d{4})\s+([A-Za-zÀ-ÿ' \-]+)")


# ---------------------------------------------------------------------------
# Détection de blocage Google (CAPTCHA / IP bannie)
# ---------------------------------------------------------------------------

class GoogleBlockedError(RuntimeError):
    """Levée quand Google bloque l'IP (CAPTCHA / 429 / sorry page).

    Cas typique : trop de requêtes depuis la même IP → Google sert une page
    /sorry/ avec un reCAPTCHA. Inutile de retry — il faut soit changer d'IP
    (VPN/proxy), soit attendre 1–24 h.
    """


# Phrases qui apparaissent sur les pages de CAPTCHA Google (FR + EN + NL).
# Couvre les variantes /sorry/ et le challenge inline.
_BLOCK_TEXT_PATTERNS = [
    "unusual traffic",                  # EN
    "trafic inhabituel",                # FR
    "ongebruikelijk verkeer",           # NL
    "verify you are a human",           # EN
    "vérifier que vous êtes",           # FR ("vérifier que vous êtes humain/un humain")
    "our systems have detected",        # EN
    "nos systèmes ont détecté",         # FR
    "before you continue to google",    # EN (pas un block mais consent — exclu plus bas)
]
# Sous-chaînes URL qui indiquent un block sans ambiguïté.
_BLOCK_URL_MARKERS = ("/sorry/", "/recaptcha/")


async def _detect_google_block(page: Page) -> Optional[str]:
    """Inspecte la page courante et renvoie une raison si Google bloque.

    Retourne None si tout va bien. Best-effort : toute exception interne est
    avalée pour ne pas masquer un échec scrape légitime — la détection n'est
    qu'un canal d'information.
    """
    # 1. URL — signal le plus fiable (Google redirige sur /sorry/...)
    try:
        url = page.url or ""
        for marker in _BLOCK_URL_MARKERS:
            if marker in url:
                return f"Google a redirigé vers une page de challenge ({marker} dans l'URL)"
    except Exception:
        pass

    # 2. Selector spécifique au formulaire CAPTCHA
    try:
        captcha_form = await page.query_selector(
            "form#captcha-form, form[action*='/sorry/'], iframe[src*='recaptcha']"
        )
        if captcha_form:
            return "Formulaire CAPTCHA Google détecté sur la page"
    except Exception:
        pass

    # 3. Titre de page
    try:
        title = (await page.title() or "").lower()
        if "sorry" in title or "captcha" in title:
            return f"Titre de page suspect : {title!r}"
    except Exception:
        pass

    # 4. Texte du body (fallback) — on lit seulement le début pour rester rapide
    try:
        body_text = await page.evaluate(
            "() => (document.body && document.body.innerText || '').slice(0, 2000).toLowerCase()"
        )
        for pat in _BLOCK_TEXT_PATTERNS:
            if pat in body_text:
                return f"Texte de blocage Google détecté : {pat!r}"
    except Exception:
        pass

    return None


async def _dismiss_consent(page: Page) -> None:
    for sel in CONSENT_BUTTONS:
        try:
            await page.locator(sel).first.click(timeout=2500)
            await page.wait_for_timeout(800)
            return
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue


async def _scroll_results(page: Page, max_results: int) -> None:
    feed = page.locator(RESULTS_FEED_SELECTOR)
    try:
        await feed.wait_for(timeout=10_000)
    except PlaywrightTimeoutError:
        return

    last_count = 0
    stable_iterations = 0
    # Pour récupérer "tout" : plus d'itérations + tolérance d'attente plus longue
    # avant de conclure que Google n'a plus rien à montrer.
    max_iterations = 80 if max_results > 100 else 40
    max_stable = 5 if max_results > 100 else 3

    for _ in range(max_iterations):
        cards = await page.locator(RESULT_CARD_SELECTOR).count()
        if cards >= max_results:
            return
        if cards == last_count:
            stable_iterations += 1
            if stable_iterations >= max_stable:
                return
        else:
            stable_iterations = 0
            last_count = cards

        await feed.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
        await page.wait_for_timeout(800)


def _parse_address(raw: str) -> tuple[Optional[str], Optional[str]]:
    if not raw:
        return None, None
    m = POSTAL_RE.search(raw)
    if not m:
        return None, None
    return m.group(1), m.group(2).strip()


async def _extract_detail(page: Page) -> dict:
    data: dict = {}

    try:
        await page.locator(DETAIL_NAME_SELECTOR).wait_for(timeout=8_000)
    except PlaywrightTimeoutError:
        return data

    data["name"] = (await page.locator(DETAIL_NAME_SELECTOR).first.inner_text()).strip()

    try:
        cat = await page.locator("button[jsaction*='category']").first.inner_text(timeout=2000)
        data["category"] = cat.strip()
    except Exception:
        pass

    try:
        rating_text = await page.locator("div.F7nice span[aria-hidden='true']").first.inner_text(timeout=2000)
        data["rating"] = float(rating_text.replace(",", "."))
    except Exception:
        pass

    try:
        reviews_aria = await page.locator("div.F7nice span[aria-label*='avis'], div.F7nice span[aria-label*='review']").first.get_attribute("aria-label", timeout=2000)
        if reviews_aria:
            m = re.search(r"([\d\s ]+)", reviews_aria)
            if m:
                data["reviews_count"] = int(re.sub(r"\D", "", m.group(1)))
    except Exception:
        pass

    info_items = page.locator("[data-item-id]")
    n = await info_items.count()
    for i in range(n):
        el = info_items.nth(i)
        try:
            item_id = await el.get_attribute("data-item-id")
            label = await el.get_attribute("aria-label")
            href = await el.get_attribute("href")
        except Exception:
            continue
        if not item_id:
            continue
        value = (label or "").split(":", 1)[-1].strip() if label else ""

        if item_id == "address" and value:
            data["address"] = value
            postal, locality = _parse_address(value)
            if postal:
                data["postal_code"] = postal
            if locality:
                data["locality"] = locality
        elif item_id.startswith("phone") and value:
            data["phone"] = value
        elif item_id == "authority":
            if href and href.startswith("http"):
                data["website"] = href
            elif value:
                data["website"] = value
        elif item_id == "oloc" and value:
            data["plus_code"] = value

    try:
        hours_btn = page.locator("button[data-item-id='oh']").first
        hours_label = await hours_btn.get_attribute("aria-label", timeout=1500)
        if hours_label:
            data["hours"] = hours_label.replace("Voir le détail des horaires d'ouverture, ", "").strip()
    except Exception:
        pass

    data["gmaps_url"] = page.url
    return data


async def _scrape(
    query: str,
    city: str,
    max_results: int,
    headless: bool,
    locale: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> list[Business]:
    full_query = f"{query} {city}".strip()
    url = GMAPS_SEARCH_URL.format(query=quote_plus(full_query))

    results: list[Business] = []

    # ---- Stealth : enveloppe async_playwright si la lib est dispo, sinon fallback ----
    stealth = _build_stealth()
    playwright_ctx = async_playwright()
    if stealth is not None:
        playwright_ctx = stealth.use_async(playwright_ctx)

    if on_progress:
        on_progress(
            f"Stealth : {'ON (playwright-stealth)' if stealth else 'OFF (fallback init_script)'}"
        )

    # ---- Args Chromium : --no-sandbox UNIQUEMENT en Docker (sécurité) ----
    chromium_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
    ]
    if _running_in_docker():
        chromium_args += ["--no-sandbox", "--disable-dev-shm-usage"]

    async with playwright_ctx as p:
        browser = await p.chromium.launch(headless=headless, args=chromium_args)
        context = await browser.new_context(
            locale=locale,
            user_agent=USER_AGENT,
            viewport={"width": 1400, "height": 900},
            # Headers cohérents avec Chrome 130 sur Windows
            extra_http_headers={
                "Accept-Language": "fr-BE,fr;q=0.9,en;q=0.8",
                "Sec-CH-UA": SEC_CH_UA,
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": '"Windows"',
                "Sec-CH-UA-Platform-Version": '"15.0.0"',
            },
            color_scheme="light",
            timezone_id="Europe/Brussels",
            # Géolocalisation alignée avec la ville recherchée (sinon Brussels par défaut)
            geolocation=_coords_for_city(city),
            permissions=["geolocation"],
        )
        # Sans playwright-stealth, on applique un fallback init_script avec
        # navigator.plugins pseudo-réalistes (et navigator.webdriver=undefined).
        if not _STEALTH_AVAILABLE:
            await context.add_init_script(_FALLBACK_INIT_SCRIPT)

        page = await context.new_page()

        if on_progress:
            on_progress(f"Ouverture Google Maps : {full_query}")

        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await _dismiss_consent(page)
        await page.wait_for_timeout(1500)

        # ⛔ Détection IP bannie / CAPTCHA Google. On vérifie APRÈS le consent
        # parce que la page consent peut être confondue avec un challenge.
        block_reason = await _detect_google_block(page)
        if block_reason:
            if on_progress:
                on_progress(f"⛔ Google bloqué : {block_reason}")
            await context.close()
            await browser.close()
            raise GoogleBlockedError(block_reason)

        await _scroll_results(page, max_results)

        cards = page.locator(RESULT_CARD_SELECTOR)
        total = min(await cards.count(), max_results)

        if on_progress:
            on_progress(f"{total} résultats trouvés pour {full_query}")

        for i in range(total):
            try:
                card = cards.nth(i)
                name_attr = await card.get_attribute("aria-label") or ""

                if on_progress:
                    on_progress(f"  ({i + 1}/{total}) {name_attr or '...'}")

                await card.scroll_into_view_if_needed(timeout=5000)
                await card.click(timeout=8000)
                await page.wait_for_timeout(1100)

                detail = await _extract_detail(page)
                if not detail.get("name"):
                    detail["name"] = name_attr

                results.append(
                    Business(
                        name=detail.get("name", "").strip(),
                        query=query,
                        city=city,
                        google_rank=i + 1,
                        address=detail.get("address"),
                        postal_code=detail.get("postal_code"),
                        locality=detail.get("locality"),
                        phone=detail.get("phone"),
                        website=detail.get("website"),
                        category=detail.get("category"),
                        rating=detail.get("rating"),
                        reviews_count=detail.get("reviews_count"),
                        hours=detail.get("hours"),
                        gmaps_url=detail.get("gmaps_url"),
                        plus_code=detail.get("plus_code"),
                    )
                )

                await page.keyboard.press("Escape")
                await page.wait_for_timeout(350)
            except Exception as e:
                if on_progress:
                    on_progress(f"  ! erreur sur résultat {i + 1} : {e}")
                continue

        await context.close()
        await browser.close()

    return results


def scrape_google_maps(
    query: str,
    cities: list[str],
    max_results_per_city: int = 30,
    headless: bool = True,
    locale: str = "fr-BE",
    on_progress: Optional[Callable[[str], None]] = None,
) -> list[Business]:
    all_results: list[Business] = []
    for city in cities:
        city = city.strip()
        if not city:
            continue
        try:
            city_results = asyncio.run(
                _scrape(query, city, max_results_per_city, headless, locale, on_progress)
            )
            all_results.extend(city_results)
        except GoogleBlockedError:
            # Ne PAS avaler : on remonte au runner pour qu'il stoppe le pipeline
            # complet et affiche un bandeau dédié — un retry serait inutile,
            # l'IP est bannie.
            raise
        except Exception as e:
            if on_progress:
                on_progress(f"Échec scraping {city} : {e}")
    return all_results

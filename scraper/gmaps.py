import asyncio
import re
from typing import Callable, Optional
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeoutError

from .models import Business


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
    for _ in range(40):
        cards = await page.locator(RESULT_CARD_SELECTOR).count()
        if cards >= max_results:
            return
        if cards == last_count:
            stable_iterations += 1
            if stable_iterations >= 3:
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

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            locale=locale,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 900},
        )
        page = await context.new_page()

        if on_progress:
            on_progress(f"Ouverture Google Maps : {full_query}")

        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await _dismiss_consent(page)
        await page.wait_for_timeout(1500)

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
        except Exception as e:
            if on_progress:
                on_progress(f"Échec scraping {city} : {e}")
    return all_results

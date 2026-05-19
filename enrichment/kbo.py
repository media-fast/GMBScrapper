import re
import threading
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from rapidfuzz import fuzz


KBO_BASE = "https://kbopub.economie.fgov.be/kbopub/"
KBO_FORM_URL = KBO_BASE + "zoeknaamfonetischform.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-BE,fr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

NUMBER_RE = re.compile(r"\b(\d{4}\.\d{3}\.\d{3})\b")
POSTAL_LOCALITY_RE = re.compile(r"(\d{4})\s+([A-Za-zÀ-ÿ' \-]+)")


@dataclass
class KboHit:
    bce_number: str
    name: str
    address: str
    entity_type: str
    status: str

    @property
    def vat_number(self) -> str:
        digits = re.sub(r"\D", "", self.bce_number)
        return f"BE{digits}" if len(digits) == 10 else ""


_thread_local = threading.local()


def _get_session() -> httpx.Client:
    now = time.time()
    client = getattr(_thread_local, "client", None)
    primed_at = getattr(_thread_local, "primed_at", 0.0)

    if client is None or now - primed_at > 600:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
        client = httpx.Client(headers=HEADERS, timeout=15.0, follow_redirects=True)
        try:
            client.get(KBO_FORM_URL, params={"lang": "fr"})
        except Exception:
            pass
        _thread_local.client = client
        _thread_local.primed_at = now
    return client


def search_kbo(name: str, locality: str = "", postal: str = "") -> list[KboHit]:
    if not name or not name.strip():
        return []

    client = _get_session()

    params = {
        "lang": "fr",
        "searchWord": name.strip(),
        "_oudeBenaming": "on",
        "pstcdeNPRP": (postal or "").strip(),
        "postgemeente1": (locality or "").strip(),
        "ondNP": "true",
        "_ondNP": "on",
        "ondRP": "true",
        "_ondRP": "on",
        "vest": "true",
        "_vest": "on",
        "filterEnkelActieve": "true",
        "_filterEnkelActieve": "on",
        "rechtsvormFonetic": "ALL",
        "actionNPRP": "Rechercher",
    }

    headers = dict(HEADERS)
    headers["Referer"] = KBO_FORM_URL + "?lang=fr"

    try:
        r = client.get(KBO_FORM_URL, params=params, headers=headers)
    except Exception:
        return []

    if r.status_code != 200:
        return []

    return _parse_results(r.text)


def _parse_results(html: str) -> list[KboHit]:
    soup = BeautifulSoup(html, "html.parser")
    hits: list[KboHit] = []

    for tr in soup.select("tr"):
        cells = tr.find_all("td")
        if len(cells) < 5:
            continue

        text_blob = tr.get_text(" ", strip=True)
        m = NUMBER_RE.search(text_blob)
        if not m:
            continue

        bce = m.group(1)

        entity_type = ""
        status = ""
        type_cell = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""
        if type_cell:
            parts = [p.strip() for p in type_cell.split() if p.strip()]
            if parts:
                entity_type = parts[0]
                if len(parts) > 1:
                    status = " ".join(parts[1:])

        name_cell = tr.find("td", class_="benaming")
        name = name_cell.get_text(" ", strip=True) if name_cell else ""

        address = ""
        for c in reversed(cells):
            txt = c.get_text(" ", strip=True)
            if POSTAL_LOCALITY_RE.search(txt):
                address = txt
                break

        if not name and not address:
            continue

        hits.append(
            KboHit(
                bce_number=bce,
                name=name,
                address=address,
                entity_type=entity_type,
                status=status,
            )
        )

    seen = set()
    unique = []
    for h in hits:
        key = (h.bce_number, h.name, h.address)
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    return unique


def best_match(
    candidates: list[KboHit],
    name: str,
    address: str = "",
    threshold: int = 65,
) -> tuple[Optional[KboHit], int]:
    if not candidates:
        return None, 0

    name_lc = name.lower()
    address_lc = address.lower()

    best: Optional[KboHit] = None
    best_score = 0
    for h in candidates:
        name_score = fuzz.token_set_ratio(name_lc, h.name.lower())
        if address_lc and h.address:
            addr_score = fuzz.token_set_ratio(address_lc, h.address.lower())
            score = int(0.65 * name_score + 0.35 * addr_score)
        else:
            score = name_score
        if score > best_score:
            best_score = score
            best = h

    if best_score < threshold:
        return None, best_score
    return best, best_score


def lookup_vat_via_kbo(
    name: str,
    locality: str = "",
    postal: str = "",
    address: str = "",
) -> tuple[Optional[KboHit], int]:
    candidates = search_kbo(name, locality=locality, postal=postal)

    if not candidates and " " in name:
        first_word = name.split()[0]
        candidates = search_kbo(first_word, locality=locality, postal=postal)

    return best_match(candidates, name, address)

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


VAT_PATTERNS = [
    re.compile(r"BE[\s\-\.]?(0|1)\d{3}[\s\-\.]?\d{3}[\s\-\.]?\d{3}", re.IGNORECASE),
    re.compile(r"\b(?:TVA|BTW|VAT)[\s\-:]*(?:BE)?[\s\-\.]?((?:0|1)\d{3}[\s\-\.]?\d{3}[\s\-\.]?\d{3})", re.IGNORECASE),
    re.compile(r"(?:numéro d['’]entreprise|ondernemingsnummer)[\s:]*((?:0|1)\d{3}[\s\-\.]?\d{3}[\s\-\.]?\d{3})", re.IGNORECASE),
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

EMAIL_BLOCKLIST = (
    "example.com", "example.be", "exemple", "voorbeeld", "exempel",
    "sentry", "wix.com", "wixpress", "godaddy", "@2x",
    "yourdomain", "domain.com", "email.com", "test.com", "squarespace",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", "core.win", "u003e",
    "name@", "nom@", "info@info",
)

LEGAL_PAGES = [
    "mentions-legales", "mentions_legales", "legal", "legales",
    "cgv", "cgu", "conditions-generales", "conditions",
    "contact", "a-propos", "about", "qui-sommes-nous",
    "impressum", "footer",
]


@dataclass
class WebsiteContact:
    vat: Optional[str] = None
    email: Optional[str] = None


def _normalize_vat(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits or not digits.startswith(("0", "1")) or len(digits) != 10:
        return ""
    return f"BE{digits}"


def _extract_vat_from_text(text: str) -> Optional[str]:
    for pattern in VAT_PATTERNS:
        match = pattern.search(text)
        if match:
            normalized = _normalize_vat(match.group(0))
            if normalized:
                return normalized
    return None


def _extract_email(html: str, soup: Optional[BeautifulSoup] = None) -> Optional[str]:
    if soup is None:
        soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if addr and not any(b in addr.lower() for b in EMAIL_BLOCKLIST):
                return addr.lower()

    for m in EMAIL_RE.finditer(html):
        addr = m.group(0).lower()
        if not any(b in addr for b in EMAIL_BLOCKLIST):
            return addr
    return None


def _build_candidate_urls(base_url: str) -> list[str]:
    parsed = urlparse(base_url)
    if not parsed.scheme:
        base_url = "https://" + base_url
        parsed = urlparse(base_url)

    root = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [root + "/"]
    for path in LEGAL_PAGES:
        candidates.append(urljoin(root + "/", path))
        candidates.append(urljoin(root + "/", path + "/"))
    return candidates


def fetch_website_contact(website: str, timeout: float = 8.0) -> WebsiteContact:
    """Récupère le numéro de TVA et l'email professionnel depuis le site web."""
    result = WebsiteContact()
    if not website:
        return result

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-BE,fr;q=0.9,nl-BE;q=0.8,en;q=0.7",
    }

    candidate_urls = _build_candidate_urls(website)

    with httpx.Client(headers=headers, timeout=timeout, follow_redirects=True) as client:
        try:
            home = client.get(candidate_urls[0])
            if home.status_code < 400:
                soup = BeautifulSoup(home.text, "html.parser")
                result.vat = result.vat or _extract_vat_from_text(home.text)
                result.email = result.email or _extract_email(home.text, soup)
                for a in soup.find_all("a", href=True):
                    href = a["href"].lower()
                    text = (a.get_text() or "").lower()
                    if any(k in href or k in text for k in ["mention", "legal", "cgv", "impressum", "contact"]):
                        full = urljoin(candidate_urls[0], a["href"])
                        if full not in candidate_urls:
                            candidate_urls.insert(1, full)
        except Exception:
            pass

        for url in candidate_urls[1:]:
            if result.vat and result.email:
                break
            try:
                r = client.get(url)
                if r.status_code >= 400:
                    continue
                result.vat = result.vat or _extract_vat_from_text(r.text)
                result.email = result.email or _extract_email(r.text)
            except Exception:
                continue

    return result


def fetch_vat_from_website(website: str, timeout: float = 8.0) -> Optional[str]:
    """Compat : retourne uniquement la TVA."""
    return fetch_website_contact(website, timeout).vat

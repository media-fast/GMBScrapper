import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

from .kbo import KBO_BASE, _get_session


KBO_DETAIL_URL = KBO_BASE + "toonondernemingps.html"

FUNCTION_RE = re.compile(
    r"^(Administrateur(?:\s+d[ée]l[ée]gu[ée])?|Administrateur-g[ée]rant|"
    r"G[ée]rant(?:\s+statutaire)?(?:\s+non\s+statutaire)?|"
    r"Repr[ée]sentant\s+permanent|"
    r"Personne\s+charg[ée]e\s+de\s+la\s+gestion|"
    r"D[ée]l[ée]gu[ée]\s+[àa]\s+la\s+gestion|"
    r"Pr[ée]sident|Membre\s+du\s+comit[ée]|Liquidateur|Fondateur|Commissaire)",
    re.IGNORECASE,
)

BCE_NUMBER_RE = re.compile(r"^\s*\d{4}\.\d{3}\.\d{3}\s*$")
NACE_RE = re.compile(
    r"(\d{2}\.\d{2,4})\s*-\s*([A-Za-zÀ-ÿ][^|]+?)\s+Depuis le\b"
)
NO_DATA = "pas de données"


@dataclass
class BceDetail:
    bce_number: str = ""
    status: Optional[str] = None
    legal_form: Optional[str] = None
    creation_date: Optional[str] = None
    denomination: Optional[str] = None
    seat_address: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    establishments_count: Optional[int] = None
    capital: Optional[str] = None
    managers: list = field(default_factory=list)
    nace_activities: list = field(default_factory=list)

    @property
    def managers_str(self) -> Optional[str]:
        if not self.managers:
            return None
        return " ; ".join(f"{name} ({func})" for func, name in self.managers)

    @property
    def nace_str(self) -> Optional[str]:
        if not self.nace_activities:
            return None
        return " | ".join(self.nace_activities[:3])


def _clean(text: str) -> str:
    text = (text or "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _value_only(text: str) -> str:
    """Retire les suffixes 'Depuis le ...' / 'Dénomination en ...'."""
    text = _clean(text)
    text = re.split(r"\bDepuis le\b", text)[0]
    text = re.split(r"D[ée]nomination en", text)[0]
    return text.strip(" ,;")


def _parse_person_name(raw: str) -> Optional[str]:
    raw = _clean(raw)
    if not raw or BCE_NUMBER_RE.match(raw):
        return None
    raw = re.sub(r"\(\s*\d{4}\.\d{3}\.\d{3}\s*\)", "", raw).strip()
    if not raw:
        return None
    if "," in raw:
        last, _, first = raw.partition(",")
        first = first.strip()
        last = last.strip()
        full = f"{first} {last}".strip()
    else:
        full = raw
    return full or None


def fetch_bce_detail(bce_number: str) -> Optional[BceDetail]:
    digits = re.sub(r"\D", "", bce_number or "")
    if len(digits) != 10:
        return None

    client = _get_session()
    try:
        r = client.get(
            KBO_DETAIL_URL,
            params={"lang": "fr", "ondernemingsnummer": digits},
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None

    return _parse_detail(r.text, digits)


def _parse_detail(html: str, digits: str) -> BceDetail:
    soup = BeautifulSoup(html, "html.parser")
    detail = BceDetail(bce_number=f"{digits[0:4]}.{digits[4:7]}.{digits[7:10]}")

    seen_managers = set()

    for tr in soup.select("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue

        label = _clean(cells[0].get_text(" "))
        value = _clean(cells[1].get_text(" "))
        if not label:
            continue

        low_label = label.lower()
        low_value = value.lower()

        if low_label.startswith("statut"):
            detail.status = _value_only(value)
        elif low_label.startswith("date de début") or low_label.startswith("date de debut"):
            detail.creation_date = _value_only(value)
        elif low_label.startswith("dénomination") or low_label.startswith("denomination"):
            if not detail.denomination:
                detail.denomination = _value_only(value)
        elif low_label.startswith("adresse du siège") or low_label.startswith("adresse du siege"):
            detail.seat_address = _value_only(value)
        elif low_label.startswith("forme légale") or low_label.startswith("forme legale"):
            detail.legal_form = _value_only(value)
        elif low_label.startswith("e-mail"):
            if NO_DATA not in low_value:
                detail.email = _value_only(value)
        elif low_label.startswith("adresse web"):
            if NO_DATA not in low_value:
                detail.website = _value_only(value)
        elif "unités d'établissement" in low_label or "unites d'etablissement" in low_label:
            m = re.search(r"\d+", value)
            if m:
                detail.establishments_count = int(m.group(0))
        elif low_label.startswith("capital"):
            detail.capital = _value_only(value)
        elif FUNCTION_RE.match(label):
            name = _parse_person_name(value)
            if name:
                key = (label.lower(), name.lower())
                if key not in seen_managers:
                    seen_managers.add(key)
                    detail.managers.append((label, name))

    page_text = _clean(soup.get_text(" "))
    for m in NACE_RE.finditer(page_text):
        code = m.group(1).strip()
        desc = m.group(2).strip()
        if len(desc) > 90:
            desc = desc[:90].rsplit(" ", 1)[0] + "…"
        entry = f"{code} {desc}"
        if desc and entry not in detail.nace_activities:
            detail.nace_activities.append(entry)

    return detail

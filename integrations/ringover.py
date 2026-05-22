"""Intégration Ringover (téléphonie cloud).

Capacités :
  1. push_contacts      : envoie les entreprises comme contacts Ringover
  2. click_to_call      : déclenche un appel (le tél du commercial sonne, puis l'entreprise)
  3. sync_call_statuses : lit les journaux d'appels et passe les entreprises appelées en "Déjà appelé"
  4. ringover_csv       : export CSV au format import-contacts Ringover (repli sans API)

Configuration (variables d'environnement) :
  RINGOVER_API_KEY        : clé API (Dashboard Ringover > Developer > API key) — REQUIS
  RINGOVER_DEFAULT_NUMBER : numéro du commercial pour le click-to-call (optionnel)
"""

import csv
import io
import os
import re
from typing import Optional

import httpx

from storage import mark_called_by_phones


API_BASE = "https://public-api.ringover.com/v3"


# ---------------------------------------------------------------------------
# Parsing du champ "managers" (issu de la BCE/KBO)
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"^(?:M\.|Mme|Mr\.?|Mrs\.?|Madame|Monsieur|Dhr\.?|Mevr\.?)\s+",
                       re.IGNORECASE)
_ROLE_SUFFIX_RE = re.compile(
    r"\s*(?:[-,(]|·)\s*(?:g[ée]rant(?:e)?|administrateur(?:.trice)?|"
    r"directeur(?:.trice)?|pr[ée]sident(?:e)?|associ[ée](?:.e)?|"
    r"co[-\s]?g[ée]rant(?:e)?|d[ée]l[ée]gu[ée](?:e)?|bestuurder|zaakvoerder)"
    r"\b.*$",
    re.IGNORECASE,
)


def split_manager_name(raw: str) -> tuple[str, str]:
    """Sépare un dirigeant en (prénom, nom).

    Heuristique :
    - prend le premier dirigeant si plusieurs (séparés par ; ou ,)
    - retire les titres (M., Mme…) et les rôles en suffixe (gérant…)
    - si certains tokens sont en MAJUSCULES (typique KBO) → ce sont les noms
    - sinon → premier token = prénom, reste = nom
    """
    if not raw:
        return ("", "")
    first = re.split(r"[;/]|,\s*(?=[A-ZÀ-Ÿ])", raw, maxsplit=1)[0].strip()
    first = _TITLE_RE.sub("", first)
    first = _ROLE_SUFFIX_RE.sub("", first)
    first = first.strip(" ,.-—–")
    if not first:
        return ("", "")

    tokens = [t for t in first.split() if t]
    if not tokens:
        return ("", "")
    if len(tokens) == 1:
        # Un seul token : on le met comme nom de famille
        return ("", tokens[0])

    # Repère les tokens en MAJUSCULES (au moins 2 lettres) — typique KBO "DUPONT John"
    upper_tokens = [t for t in tokens if len(t) >= 2 and t == t.upper() and any(c.isalpha() for c in t)]
    if upper_tokens and len(upper_tokens) < len(tokens):
        lastname = " ".join(upper_tokens)
        firstname = " ".join(t for t in tokens if t not in upper_tokens)
        return (firstname.strip().title(), lastname.strip())

    # Sinon : premier token = prénom, suite = nom
    return (tokens[0].title(), " ".join(t.title() for t in tokens[1:]))
PHONE_IN_TEXT_RE = re.compile(r"\+?\d[\d ().\-]{7,}\d")


def _api_key() -> str:
    return os.environ.get("RINGOVER_API_KEY", "").strip()


def _default_number() -> str:
    return os.environ.get("RINGOVER_DEFAULT_NUMBER", "").strip()


def is_configured() -> bool:
    return bool(_api_key())


def _headers() -> dict:
    return {
        "Authorization": _api_key(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _to_e164(phone: str, default_cc: str = "32") -> Optional[str]:
    if not phone:
        return None
    raw = phone.strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    if raw.startswith("+"):
        return "+" + digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith(default_cc) and len(digits) > 9:
        return "+" + digits
    return "+" + default_cc + digits.lstrip("0")


# --------------------------------------------------------------------------
# 1. Journaux d'appels
# --------------------------------------------------------------------------

def list_recent_calls(limit: int = 100) -> dict:
    if not is_configured():
        return {"ok": False, "message": "Clé API Ringover non configurée.", "calls": []}
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(
                f"{API_BASE}/calls",
                headers=_headers(),
                params={"limit_count": min(limit, 1000)},
            )
        if r.status_code != 200:
            return {"ok": False, "message": f"Ringover a répondu {r.status_code}: {r.text[:200]}",
                    "calls": []}
        payload = r.json()
        calls = payload.get("call_list", payload) if isinstance(payload, dict) else payload
        if not isinstance(calls, list):
            calls = []
        return {"ok": True, "message": f"{len(calls)} appels récupérés", "calls": calls}
    except Exception as e:
        return {"ok": False, "message": f"Erreur Ringover : {e}", "calls": []}


def _extract_phone_numbers(obj) -> set[str]:
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, (str, int)):
            for m in PHONE_IN_TEXT_RE.finditer(str(node)):
                found.add(m.group(0))

    walk(obj)
    return found


# --------------------------------------------------------------------------
# 2. Synchronisation des statuts
# --------------------------------------------------------------------------

def sync_call_statuses(limit: int = 200) -> dict:
    result = list_recent_calls(limit)
    if not result["ok"]:
        return {"ok": False, "message": result["message"], "updated": 0}

    numbers: set[str] = set()
    for call in result["calls"]:
        numbers |= _extract_phone_numbers(call)

    updated = mark_called_by_phones(numbers)
    return {
        "ok": True,
        "updated": updated,
        "message": f"{updated} entreprise(s) passée(s) en « Déjà appelé » "
                   f"(sur {len(result['calls'])} appels analysés).",
    }


# --------------------------------------------------------------------------
# 3. Click-to-call
# --------------------------------------------------------------------------

def click_to_call(to_number: str, from_number: Optional[str] = None) -> dict:
    if not is_configured():
        return {"ok": False, "message": "Clé API Ringover non configurée."}

    target = _to_e164(to_number)
    if not target:
        return {"ok": False, "message": f"Numéro cible invalide : {to_number}"}

    source = _to_e164(from_number or _default_number()) if (from_number or _default_number()) else None

    body = {"to_number": target}
    if source:
        body["from_number"] = source

    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.post(f"{API_BASE}/callback", headers=_headers(), json=body)
        if r.status_code in (200, 201, 204):
            return {"ok": True, "message": f"Appel lancé vers {target}. Décroche ton téléphone."}
        return {"ok": False, "message": f"Ringover a répondu {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "message": f"Erreur Ringover : {e}"}


# --------------------------------------------------------------------------
# 4. Push de contacts
# --------------------------------------------------------------------------

def _phone_to_int(phone: str) -> Optional[int]:
    """Ringover v3 attend un numéro en integer (pas de + ni de séparateurs)."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = "32" + digits.lstrip("0")
    try:
        return int(digits)
    except ValueError:
        return None


def _contact_payload(business: dict) -> Optional[dict]:
    """Construit le dict d'un contact pour l'API Ringover v3 ({contacts:[...]}).

    Prénom / Nom = dirigeant extrait du champ managers (BCE/KBO).
    Si pas de dirigeant identifié, le nom de l'entreprise sert de lastname.
    """
    phone_int = _phone_to_int(business.get("phone") or "")
    if not phone_int:
        return None
    company = (business.get("name") or "").strip() or "Entreprise"

    firstname, lastname = split_manager_name(business.get("managers") or "")
    if not lastname:
        lastname = company

    payload = {
        "lastname": lastname[:80],
        "company": company[:80],
        "numbers": [{"number": phone_int, "type": "office"}],
        "is_shared": True,
    }
    if firstname:
        payload["firstname"] = firstname[:80]
    return payload


def push_contacts(businesses: list[dict]) -> dict:
    if not is_configured():
        return {"ok": False, "message": "Clé API Ringover non configurée.",
                "pushed": 0, "failed": 0, "errors": []}

    pushed, failed, errors = 0, 0, []
    contact_ids: dict = {}

    # On envoie par paquets de 1 pour pouvoir tracer les échecs individuellement
    try:
        with httpx.Client(timeout=25.0) as client:
            for b in businesses:
                contact = _contact_payload(b)
                if contact is None:
                    failed += 1
                    errors.append(f"{b.get('name', '?')} : pas de numéro de téléphone")
                    continue

                body = {"contacts": [contact]}
                try:
                    r = client.post(f"{API_BASE}/contacts", headers=_headers(), json=body)
                    if r.status_code in (200, 201, 204):
                        pushed += 1
                        try:
                            data = r.json()
                            inner = data if isinstance(data, list) else data.get("contacts", data)
                            if isinstance(inner, list) and inner:
                                first = inner[0]
                                cid = first.get("contact_id") or first.get("id") if isinstance(first, dict) else None
                                if cid and b.get("dedup_key"):
                                    contact_ids[b["dedup_key"]] = str(cid)
                        except Exception:
                            pass
                    else:
                        failed += 1
                        snippet = r.text[:140].replace("\n", " ")
                        errors.append(f"{contact['company']} : HTTP {r.status_code} {snippet}")
                except Exception as e:
                    failed += 1
                    errors.append(f"{contact['company']} : {e}")
    except Exception as e:
        return {"ok": False, "message": f"Erreur Ringover : {e}",
                "pushed": pushed, "failed": failed, "errors": errors}

    msg = f"{pushed} contact(s) envoyé(s) vers Ringover"
    if failed:
        msg += f", {failed} échec(s)"
    if pushed == 0 and failed > 0 and any("HTTP 500" in e for e in errors):
        msg += " — Erreur serveur Ringover (vérifie les scopes 'Contacts' sur la clé API)"
    return {"ok": pushed > 0, "message": msg, "pushed": pushed, "failed": failed,
            "errors": errors[:20], "contact_ids": contact_ids}


# --------------------------------------------------------------------------
# 5. Export CSV (repli sans API)
# --------------------------------------------------------------------------

def ringover_csv(businesses: list[dict]) -> bytes:
    """CSV au format import contacts Ringover.

    Prénom / Nom = dirigeant extrait du champ managers (BCE/KBO).
    Si pas de dirigeant connu, fallback : Nom = nom de l'entreprise.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Prénom", "Nom", "Société", "Numéro", "Email", "Notes"])
    for b in businesses:
        phone = _to_e164(b.get("phone") or "") or ""
        company = (b.get("name") or "").strip()

        firstname, lastname = split_manager_name(b.get("managers") or "")
        if not firstname and not lastname:
            # Aucun dirigeant identifié → fallback sur le nom de l'entreprise
            lastname = company

        notes = []
        if b.get("managers"):
            notes.append(f"Dirigeant(s) source : {b['managers']}")
        if b.get("vat_number"):
            notes.append(f"TVA: {b['vat_number']}")
        if b.get("city"):
            notes.append(b["city"])
        if b.get("call_status"):
            notes.append(f"Statut: {b['call_status']}")

        writer.writerow([firstname, lastname, company, phone, b.get("email") or "", " | ".join(notes)])
    return buf.getvalue().encode("utf-8-sig")

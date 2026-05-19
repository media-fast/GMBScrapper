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


API_BASE = "https://public-api.ringover.com/v2"
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

def _contact_payload(business: dict) -> Optional[dict]:
    phone = _to_e164(business.get("phone") or "")
    if not phone:
        return None
    name = (business.get("name") or "").strip() or "Entreprise"
    notes_bits = []
    if business.get("managers"):
        notes_bits.append(f"Dirigeant(s): {business['managers']}")
    if business.get("vat_number"):
        notes_bits.append(f"TVA: {business['vat_number']}")
    if business.get("city"):
        notes_bits.append(f"Ville: {business['city']}")
    return {
        "firstname": "",
        "lastname": name,
        "company": name,
        "numbers": [{"type": "office", "number": phone}],
        "emails": [business["email"]] if business.get("email") else [],
        "notes": " | ".join(notes_bits),
    }


def push_contacts(businesses: list[dict]) -> dict:
    if not is_configured():
        return {"ok": False, "message": "Clé API Ringover non configurée.",
                "pushed": 0, "failed": 0, "errors": []}

    pushed, failed, errors = 0, 0, []
    contact_ids: dict = {}

    try:
        with httpx.Client(timeout=25.0) as client:
            for b in businesses:
                payload = _contact_payload(b)
                if payload is None:
                    failed += 1
                    errors.append(f"{b.get('name', '?')} : pas de numéro de téléphone")
                    continue
                try:
                    r = client.post(f"{API_BASE}/contacts", headers=_headers(), json=payload)
                    if r.status_code in (200, 201):
                        pushed += 1
                        try:
                            data = r.json()
                            cid = data.get("contact_id") or data.get("id")
                            if cid and b.get("dedup_key"):
                                contact_ids[b["dedup_key"]] = str(cid)
                        except Exception:
                            pass
                    else:
                        failed += 1
                        errors.append(f"{payload['company']} : HTTP {r.status_code} {r.text[:120]}")
                except Exception as e:
                    failed += 1
                    errors.append(f"{payload['company']} : {e}")
    except Exception as e:
        return {"ok": False, "message": f"Erreur Ringover : {e}",
                "pushed": pushed, "failed": failed, "errors": errors}

    msg = f"{pushed} contact(s) envoyé(s) vers Ringover"
    if failed:
        msg += f", {failed} échec(s)"
    return {"ok": pushed > 0, "message": msg, "pushed": pushed, "failed": failed,
            "errors": errors[:20], "contact_ids": contact_ids}


# --------------------------------------------------------------------------
# 5. Export CSV (repli sans API)
# --------------------------------------------------------------------------

def ringover_csv(businesses: list[dict]) -> bytes:
    """CSV au format import contacts Ringover."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Prénom", "Nom", "Société", "Numéro", "Email", "Notes"])
    for b in businesses:
        phone = _to_e164(b.get("phone") or "") or ""
        name = (b.get("name") or "").strip()
        notes = []
        if b.get("managers"):
            notes.append(f"Dirigeant: {b['managers']}")
        if b.get("vat_number"):
            notes.append(f"TVA: {b['vat_number']}")
        if b.get("city"):
            notes.append(b["city"])
        if b.get("call_status"):
            notes.append(f"Statut: {b['call_status']}")
        writer.writerow(["", name, name, phone, b.get("email") or "", " | ".join(notes)])
    return buf.getvalue().encode("utf-8-sig")

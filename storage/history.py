import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from typing import Optional

from scraper.models import Business


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "history.db")

# Statuts de campagne d'appels
STATUS_TO_CALL = "À appeler"
STATUS_CALLED = "Déjà appelé"
STATUS_CALLBACK = "À rappeler"
STATUS_DO_NOT_CALL = "Ne plus rappeler"
CALL_STATUSES = [STATUS_TO_CALL, STATUS_CALLED, STATUS_CALLBACK, STATUS_DO_NOT_CALL]


SCHEMA = """
CREATE TABLE IF NOT EXISTS searches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    query       TEXT NOT NULL,
    cities      TEXT,
    ran_at      TEXT NOT NULL,
    total       INTEGER DEFAULT 0,
    new_count   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS businesses (
    dedup_key            TEXT PRIMARY KEY,
    name                 TEXT,
    bce_number           TEXT,
    vat_number           TEXT,
    address              TEXT,
    city                 TEXT,
    query                TEXT,
    phone                TEXT,
    website              TEXT,
    managers             TEXT,
    first_seen           TEXT,
    last_seen            TEXT,
    search_id            INTEGER,
    call_status          TEXT DEFAULT 'À appeler',
    call_notes           TEXT DEFAULT '',
    last_call_at         TEXT,
    callback_date        TEXT,
    ringover_contact_id  TEXT
);
"""

# Colonnes ajoutées après coup (migration des bases existantes)
MIGRATION_COLUMNS = {
    "call_status": "TEXT DEFAULT 'À appeler'",
    "call_notes": "TEXT DEFAULT ''",
    "last_call_at": "TEXT",
    "callback_date": "TEXT",
    "ringover_contact_id": "TEXT",
}


def _connect() -> sqlite3.Connection:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(businesses)")}
        for col, ddl in MIGRATION_COLUMNS.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE businesses ADD COLUMN {col} {ddl}")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def phone_key(raw: str) -> str:
    """Normalise un numéro pour le matching (chiffres nationaux belges)."""
    d = re.sub(r"\D", "", raw or "")
    if d.startswith("0032"):
        d = d[4:]
    elif d.startswith("32"):
        d = d[2:]
    return d.lstrip("0")


def dedup_key(business: Business) -> str:
    if business.bce_number:
        digits = re.sub(r"\D", "", business.bce_number)
        if len(digits) == 10:
            return f"bce:{digits}"
    name = _norm(business.name)
    postal = (business.postal_code or "").strip()
    return f"nm:{name}|{postal}"


def get_seen_keys() -> dict:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT dedup_key, first_seen FROM businesses").fetchall()
    return {r["dedup_key"]: r["first_seen"] for r in rows}


def mark_seen(businesses: list[Business]) -> int:
    seen = get_seen_keys()
    count = 0
    for b in businesses:
        key = dedup_key(b)
        if key in seen:
            b.already_seen = True
            b.first_seen = seen[key]
            count += 1
        else:
            b.already_seen = False
            b.first_seen = None
    return count


def save_search(query: str, cities: list[str], businesses: list[Business]) -> int:
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_count = sum(1 for b in businesses if not b.already_seen)

    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO searches (query, cities, ran_at, total, new_count) VALUES (?, ?, ?, ?, ?)",
            (query, ", ".join(cities), now, len(businesses), new_count),
        )
        search_id = cur.lastrowid

        for b in businesses:
            key = dedup_key(b)
            existing = conn.execute(
                "SELECT first_seen FROM businesses WHERE dedup_key = ?", (key,)
            ).fetchone()
            first_seen = existing["first_seen"] if existing else now

            conn.execute(
                """
                INSERT INTO businesses
                    (dedup_key, name, bce_number, vat_number, address, city, query,
                     phone, website, managers, first_seen, last_seen, search_id, call_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dedup_key) DO UPDATE SET
                    name=excluded.name,
                    bce_number=COALESCE(excluded.bce_number, businesses.bce_number),
                    vat_number=COALESCE(excluded.vat_number, businesses.vat_number),
                    phone=COALESCE(excluded.phone, businesses.phone),
                    website=COALESCE(excluded.website, businesses.website),
                    managers=COALESCE(excluded.managers, businesses.managers),
                    last_seen=excluded.last_seen
                """,
                (
                    key, b.name, b.bce_number, b.vat_number, b.address, b.city,
                    b.query, b.phone, b.website, b.managers, first_seen, now,
                    search_id, STATUS_TO_CALL,
                ),
            )
    return search_id


def list_searches(limit: int = 50) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM searches ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_known_businesses(limit: int = 5000) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM businesses ORDER BY last_seen DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def history_stats() -> dict:
    init_db()
    with _connect() as conn:
        n_searches = conn.execute("SELECT COUNT(*) c FROM searches").fetchone()["c"]
        n_biz = conn.execute("SELECT COUNT(*) c FROM businesses").fetchone()["c"]
        n_vat = conn.execute(
            "SELECT COUNT(*) c FROM businesses WHERE vat_number IS NOT NULL AND vat_number != ''"
        ).fetchone()["c"]
    return {"searches": n_searches, "businesses": n_biz, "with_vat": n_vat}


def clear_history() -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM businesses")
        conn.execute("DELETE FROM searches")


# --------------------------------------------------------------------------
# Campagne d'appels
# --------------------------------------------------------------------------

def get_campaign_businesses(status: Optional[str] = None, limit: int = 5000) -> list[dict]:
    """Liste des entreprises pour la campagne d'appels, avec statut."""
    init_db()
    query = "SELECT * FROM businesses"
    params: list = []
    if status and status in CALL_STATUSES:
        query += " WHERE call_status = ?"
        params.append(status)
    query += " ORDER BY CASE call_status" \
             " WHEN 'À rappeler' THEN 0 WHEN 'À appeler' THEN 1" \
             " WHEN 'Déjà appelé' THEN 2 ELSE 3 END, last_seen DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_call_fields(
    dedup_key_value: str,
    call_status: Optional[str] = None,
    call_notes: Optional[str] = None,
    callback_date: Optional[str] = None,
    last_call_at: Optional[str] = None,
    ringover_contact_id: Optional[str] = None,
) -> None:
    init_db()
    sets, params = [], []
    if call_status is not None:
        sets.append("call_status = ?"); params.append(call_status)
    if call_notes is not None:
        sets.append("call_notes = ?"); params.append(call_notes)
    if callback_date is not None:
        sets.append("callback_date = ?"); params.append(callback_date)
    if last_call_at is not None:
        sets.append("last_call_at = ?"); params.append(last_call_at)
    if ringover_contact_id is not None:
        sets.append("ringover_contact_id = ?"); params.append(ringover_contact_id)
    if not sets:
        return
    params.append(dedup_key_value)
    with _connect() as conn:
        conn.execute(f"UPDATE businesses SET {', '.join(sets)} WHERE dedup_key = ?", params)


def bulk_update_campaign(edits: list[dict]) -> int:
    """edits : liste de dicts {dedup_key, call_status, call_notes, callback_date}."""
    init_db()
    count = 0
    with _connect() as conn:
        for e in edits:
            key = e.get("dedup_key")
            if not key:
                continue
            conn.execute(
                "UPDATE businesses SET call_status = ?, call_notes = ?, callback_date = ? "
                "WHERE dedup_key = ?",
                (e.get("call_status", STATUS_TO_CALL), e.get("call_notes", "") or "",
                 e.get("callback_date") or None, key),
            )
            count += 1
    return count


def campaign_stats() -> dict:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT call_status, COUNT(*) c FROM businesses GROUP BY call_status"
        ).fetchall()
    stats = {s: 0 for s in CALL_STATUSES}
    for r in rows:
        if r["call_status"] in stats:
            stats[r["call_status"]] = r["c"]
    return stats


def mark_called_by_phones(called_numbers: set[str]) -> int:
    """Passe en 'Déjà appelé' les entreprises dont le téléphone correspond
    à un numéro composé (sync Ringover). Ne touche pas aux statuts manuels
    'À rappeler' / 'Ne plus rappeler'."""
    init_db()
    called_keys = {phone_key(n) for n in called_numbers if phone_key(n)}
    if not called_keys:
        return 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    updated = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT dedup_key, phone, call_status FROM businesses "
            "WHERE phone IS NOT NULL AND phone != ''"
        ).fetchall()
        for r in rows:
            if phone_key(r["phone"]) in called_keys:
                if r["call_status"] == STATUS_TO_CALL:
                    conn.execute(
                        "UPDATE businesses SET call_status = ?, last_call_at = ? WHERE dedup_key = ?",
                        (STATUS_CALLED, now, r["dedup_key"]),
                    )
                else:
                    conn.execute(
                        "UPDATE businesses SET last_call_at = ? WHERE dedup_key = ?",
                        (now, r["dedup_key"]),
                    )
                updated += 1
    return updated

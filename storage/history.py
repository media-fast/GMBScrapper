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

CREATE TABLE IF NOT EXISTS search_businesses (
    search_id   INTEGER NOT NULL,
    dedup_key   TEXT NOT NULL,
    google_rank INTEGER,
    category    TEXT,
    PRIMARY KEY (search_id, dedup_key),
    FOREIGN KEY (search_id) REFERENCES searches(id),
    FOREIGN KEY (dedup_key) REFERENCES businesses(dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_search_businesses_search ON search_businesses(search_id);
CREATE INDEX IF NOT EXISTS idx_search_businesses_dedup  ON search_businesses(dedup_key);
"""

# Colonnes ajoutées après coup (migration des bases existantes)
MIGRATION_COLUMNS = {
    "call_status": "TEXT DEFAULT 'À appeler'",
    "call_notes": "TEXT DEFAULT ''",
    "last_call_at": "TEXT",
    "callback_date": "TEXT",
    "ringover_contact_id": "TEXT",
    # Tous les champs Business persistés pour que l'historique reste complet
    "locality": "TEXT",
    "postal_code": "TEXT",
    "email": "TEXT",
    "category": "TEXT",
    "legal_form": "TEXT",
    "bce_status": "TEXT",
    "creation_date": "TEXT",
    "capital": "TEXT",
    "establishments_count": "INTEGER",
    "nace_activities": "TEXT",
    "rating": "REAL",
    "reviews_count": "INTEGER",
    "hours": "TEXT",
    "gmaps_url": "TEXT",
    "plus_code": "TEXT",
    "nbb_url": "TEXT",
    "nbb_year": "TEXT",
    "nbb_revenue": "TEXT",
    "nbb_equity": "TEXT",
    "nbb_employees": "TEXT",
    "companyweb_url": "TEXT",
    "companyweb_score": "TEXT",
    "ai_briefing": "TEXT",        # JSON-encoded briefing IA
    "ai_briefing_at": "TEXT",     # timestamp dernière génération
    "seo_audit": "TEXT",          # JSON-encoded audit SEO (website + GMB)
    "seo_audit_at": "TEXT",       # timestamp dernier audit
    # Scoring crédit heuristique (enrichment/credit_score.py)
    "credit_color": "TEXT",       # red / orange / yellow / green / gray
    "credit_score": "INTEGER",    # 0-100 (plus haut = mieux)
    "credit_label": "TEXT",       # libellé FR humain (« Bon payeur », etc.)
    "credit_reasons": "TEXT",     # JSON-encoded list[str]
    "credit_computed_at": "TEXT", # timestamp du calcul
    # Rapport crédit IA approfondi (enrichment/credit_ai_report.py)
    "credit_ai_report": "TEXT",       # markdown du rapport IA
    "credit_ai_report_at": "TEXT",    # timestamp de génération
    "credit_ai_report_meta": "TEXT",  # JSON {provider, message, codes_count}
}

# Champs persistés pour chaque entreprise (lus depuis Business.to_dict())
BUSINESS_PERSISTED_FIELDS = [
    "name", "bce_number", "vat_number", "address", "city", "query", "phone",
    "website", "managers",
    "locality", "postal_code", "email", "category",
    "legal_form", "bce_status", "creation_date", "capital",
    "establishments_count", "nace_activities",
    "rating", "reviews_count", "hours", "gmaps_url", "plus_code",
    "nbb_url", "nbb_year", "nbb_revenue", "nbb_equity", "nbb_employees",
    "companyweb_url", "companyweb_score",
    "credit_color", "credit_score", "credit_label", "credit_reasons",
    "credit_computed_at",
]


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

        # Migration : rétro-remplir search_businesses depuis businesses.search_id
        count = conn.execute("SELECT COUNT(*) c FROM search_businesses").fetchone()["c"]
        if count == 0:
            conn.execute(
                """
                INSERT OR IGNORE INTO search_businesses (search_id, dedup_key, google_rank, category)
                SELECT search_id, dedup_key, NULL, NULL
                FROM businesses
                WHERE search_id IS NOT NULL
                """
            )

        # Migration : ancienne clé BCE `bce:0123456789` → nouvelle clé
        # `bce:0123456789|<postal>` pour distinguer les magasins de chaîne.
        # Idempotent : les clés déjà au nouveau format (contenant `|`) sont
        # ignorées. Les anciennes lignes sans postal deviennent `bce:...|`.
        #
        # ⚠️ Atomicité : on s'appuie sur la transaction implicite du context
        # manager `with _connect() as conn:` — toute exception non-IntegrityError
        # remonte et déclenche un ROLLBACK automatique de TOUT init_db (schéma
        # de base inclus, mais idempotent au prochain run). Pas d'état hybride
        # mi-ancien mi-nouveau format possible.
        #
        # 🪶 Streaming par batchs de 500 lignes au lieu d'un fetchall global :
        # une base avec 100k anciennes fiches ne fait plus exploser la RAM
        # (100k tuples Python ≈ 30 Mo de pic ➜ 500 tuples ≈ 0,15 Mo de pic).
        # La WHERE clause exclut naturellement les lignes déjà migrées
        # (qui contiennent `|`) donc le prochain batch ne les re-fetche pas.
        # Les rares collisions IntegrityError sont mémorisées dans `skipped`
        # pour ne pas boucler à l'infini sur les mêmes lignes.
        _migrate_dedup_keys_streaming(conn)


_MIGRATION_BATCH_SIZE = 500


def _migrate_dedup_keys_streaming(conn: sqlite3.Connection) -> None:
    """Migre les anciennes clés `bce:XXX` → `bce:XXX|<postal>` par batchs.

    Streaming via re-query à chaque batch : la WHERE clause s'auto-rétrécit
    au fur et à mesure que les lignes sont migrées (la nouvelle clé contient
    `|` donc ne matche plus). Les collisions sont tracées pour ne pas être
    re-fetchées indéfiniment.
    """
    skipped: set[str] = set()
    base_where = (
        "WHERE dedup_key LIKE 'bce:%' AND dedup_key NOT LIKE '%|%'"
    )
    while True:
        if skipped:
            placeholders = ",".join("?" * len(skipped))
            sql = (
                f"SELECT dedup_key, postal_code FROM businesses "
                f"{base_where} AND dedup_key NOT IN ({placeholders}) "
                f"LIMIT ?"
            )
            params: tuple = (*skipped, _MIGRATION_BATCH_SIZE)
        else:
            sql = (
                f"SELECT dedup_key, postal_code FROM businesses "
                f"{base_where} LIMIT ?"
            )
            params = (_MIGRATION_BATCH_SIZE,)

        batch = conn.execute(sql, params).fetchall()
        if not batch:
            return

        for row in batch:
            old_key = row["dedup_key"]
            postal = (row["postal_code"] or "").strip()
            new_key = f"{old_key}|{postal}"
            try:
                conn.execute(
                    "UPDATE businesses SET dedup_key = ? WHERE dedup_key = ?",
                    (new_key, old_key),
                )
                conn.execute(
                    "UPDATE search_businesses SET dedup_key = ? WHERE dedup_key = ?",
                    (new_key, old_key),
                )
            except sqlite3.IntegrityError:
                # Collision rare (la new_key existe déjà). On mémorise pour
                # ne pas la re-fetcher au prochain batch (sinon boucle infinie).
                skipped.add(old_key)
                continue


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
    """Clé d'unicité d'une fiche (entité × emplacement).

    On INCLUT le code postal même quand le BCE est connu, sinon les chaînes
    (Pearle Waterloo / Pearle Liège partagent BE0424.735.977) sont fusionnées
    en une seule fiche, ce qui est faux pour de la prospection commerciale :
    chaque magasin physique = un prospect distinct (manager, téléphone, RDV
    différents).
    """
    postal = (business.postal_code or "").strip()
    if business.bce_number:
        digits = re.sub(r"\D", "", business.bce_number)
        if len(digits) == 10:
            return f"bce:{digits}|{postal}"
    name = _norm(business.name)
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

        # Construction dynamique de l'INSERT à partir de BUSINESS_PERSISTED_FIELDS
        meta_cols = ["dedup_key", "first_seen", "last_seen", "search_id", "call_status"]
        all_cols = meta_cols + BUSINESS_PERSISTED_FIELDS
        placeholders = ", ".join("?" * len(all_cols))
        # ON CONFLICT : on garde l'ancien si le nouveau est NULL (sauf name et last_seen)
        always_overwrite = {"name", "last_seen", "search_id"}
        update_clauses = []
        for col in BUSINESS_PERSISTED_FIELDS + ["last_seen"]:
            if col in always_overwrite:
                update_clauses.append(f"{col}=excluded.{col}")
            else:
                update_clauses.append(
                    f"{col}=COALESCE(excluded.{col}, businesses.{col})"
                )
        update_clauses.append("search_id=excluded.search_id")
        upsert_sql = (
            f"INSERT INTO businesses ({', '.join(all_cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(dedup_key) DO UPDATE SET {', '.join(update_clauses)}"
        )

        for b in businesses:
            key = dedup_key(b)
            existing = conn.execute(
                "SELECT first_seen FROM businesses WHERE dedup_key = ?", (key,)
            ).fetchone()
            first_seen = existing["first_seen"] if existing else now

            values = [key, first_seen, now, search_id, STATUS_TO_CALL]
            for field in BUSINESS_PERSISTED_FIELDS:
                values.append(getattr(b, field, None))

            conn.execute(upsert_sql, values)

            conn.execute(
                "INSERT OR REPLACE INTO search_businesses "
                "(search_id, dedup_key, google_rank, category) VALUES (?, ?, ?, ?)",
                (search_id, key, getattr(b, "google_rank", None), getattr(b, "category", None)),
            )
    return search_id


def get_search(search_id: int) -> Optional[dict]:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM searches WHERE id = ?", (search_id,)).fetchone()
    return dict(row) if row else None


def get_search_businesses(search_id: int) -> list[dict]:
    """Liste les entreprises d'un scrape donné, avec rang Google."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT b.*, sb.google_rank AS google_rank
            FROM businesses b
            JOIN search_businesses sb ON sb.dedup_key = b.dedup_key
            WHERE sb.search_id = ?
            ORDER BY COALESCE(sb.google_rank, 999), b.name
            """,
            (search_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_search(search_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM search_businesses WHERE search_id = ?", (search_id,))
        conn.execute("DELETE FROM searches WHERE id = ?", (search_id,))


# --------------------------------------------------------------------------
# Cache des briefings IA
# --------------------------------------------------------------------------
import json as _json


def get_briefing(dedup_key_value: str) -> Optional[dict]:
    if not dedup_key_value:
        return None
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT ai_briefing, ai_briefing_at FROM businesses WHERE dedup_key = ?",
            (dedup_key_value,),
        ).fetchone()
    if not row or not row["ai_briefing"]:
        return None
    try:
        data = _json.loads(row["ai_briefing"])
        data["_generated_at"] = row["ai_briefing_at"]
        return data
    except Exception:
        return None


def save_briefing(dedup_key_value: str, briefing: dict) -> None:
    if not dedup_key_value or not briefing:
        return
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = _json.dumps(briefing, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            "UPDATE businesses SET ai_briefing = ?, ai_briefing_at = ? WHERE dedup_key = ?",
            (payload, now, dedup_key_value),
        )


def get_seo_audit(dedup_key_value: str) -> Optional[dict]:
    if not dedup_key_value:
        return None
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT seo_audit, seo_audit_at FROM businesses WHERE dedup_key = ?",
            (dedup_key_value,),
        ).fetchone()
    if not row or not row["seo_audit"]:
        return None
    try:
        data = _json.loads(row["seo_audit"])
        data["_generated_at"] = row["seo_audit_at"]
        return data
    except Exception:
        return None


def save_seo_audit(dedup_key_value: str, audit: dict) -> None:
    if not dedup_key_value or not audit:
        return
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    payload = _json.dumps(audit, ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            "UPDATE businesses SET seo_audit = ?, seo_audit_at = ? WHERE dedup_key = ?",
            (payload, now, dedup_key_value),
        )


def get_credit_ai_report(dedup_key_value: str) -> Optional[dict]:
    """Récupère le dernier rapport crédit IA généré pour une fiche.

    Returns:
        dict avec keys 'report' (str markdown), 'meta' (dict provider/...),
        '_generated_at' (str timestamp), ou None si pas de cache.
    """
    if not dedup_key_value:
        return None
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT credit_ai_report, credit_ai_report_at, credit_ai_report_meta "
            "FROM businesses WHERE dedup_key = ?",
            (dedup_key_value,),
        ).fetchone()
    if not row or not row["credit_ai_report"]:
        return None
    try:
        meta = _json.loads(row["credit_ai_report_meta"] or "{}")
    except Exception:
        meta = {}
    return {
        "report": row["credit_ai_report"],
        "meta": meta,
        "_generated_at": row["credit_ai_report_at"],
    }


def save_credit_ai_report(dedup_key_value: str, result: dict) -> None:
    """Persiste le rapport crédit IA. `result` = dict du retour de
    generate_credit_report (keys: report, provider, message, ...)."""
    if not dedup_key_value or not result or not result.get("report"):
        return
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta = {
        "provider": result.get("provider"),
        "message": result.get("message"),
        "accounting_codes_count": result.get("accounting_codes_count", 0),
    }
    with _connect() as conn:
        conn.execute(
            "UPDATE businesses SET credit_ai_report = ?, credit_ai_report_at = ?, "
            "credit_ai_report_meta = ? WHERE dedup_key = ?",
            (result["report"], now, _json.dumps(meta, ensure_ascii=False),
             dedup_key_value),
        )


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

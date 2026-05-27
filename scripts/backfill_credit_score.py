"""Back-fill du scoring crédit heuristique (Phase 1) sur les fiches
existantes en DB qui n'ont pas encore de `credit_color`.

Pratique pour les fiches scrapées AVANT la mise en place du scoring
Phase 1 : on recalcule à partir des données déjà persistées
(bce_status, creation_date, nbb_year).

Usage :
    python -m scripts.backfill_credit_score

Le script :
  - lit toutes les businesses sans credit_color
  - construit un NbbData synthétique depuis nbb_year (deposit_date
    inconnu → approximé à juin N+1 par compute_credit_score)
  - applique compute_credit_score
  - persiste les 5 champs credit_* en DB
  - print un résumé par couleur

Idempotent : on peut le relancer sans risque (skip les déjà scorés).
"""

import json
import os
import sqlite3
import sys

# Permet d'exécuter le script depuis la racine du projet
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enrichment.credit_score import compute_credit_score  # noqa: E402
from enrichment.nbb import NbbData  # noqa: E402
from storage.history import DB_PATH, init_db  # noqa: E402


def _nbb_from_row(row: sqlite3.Row) -> NbbData:
    """Reconstruit un NbbData synthétique à partir des colonnes DB."""
    return NbbData(
        consult_url="",  # pas utilisé par compute_credit_score
        year=row["nbb_year"] if "nbb_year" in row.keys() else None,
        revenue=row["nbb_revenue"] if "nbb_revenue" in row.keys() else None,
        equity=row["nbb_equity"] if "nbb_equity" in row.keys() else None,
        employees=row["nbb_employees"] if "nbb_employees" in row.keys() else None,
        # On n'a pas le deposit_date exact en DB → laisse None,
        # compute_credit_score approximera depuis l'année.
        deposit_date=None,
        model_type=None,
        deposits_count=1 if (row["nbb_year"] if "nbb_year" in row.keys() else None) else 0,
        available=bool(row["nbb_year"] if "nbb_year" in row.keys() else None),
    )


def main() -> int:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # On ne re-score PAS les fiches déjà scorées (idempotence)
        rows = conn.execute(
            "SELECT dedup_key, bce_status, creation_date, nbb_year, "
            "       nbb_revenue, nbb_equity, nbb_employees, bce_number "
            "FROM businesses WHERE credit_color IS NULL OR credit_color = ''"
        ).fetchall()

        print(f"-> {len(rows)} fiche(s) a scorer\n")

        updated = 0
        by_color: dict[str, int] = {}
        for row in rows:
            nbb = _nbb_from_row(row)
            score = compute_credit_score(
                bce_status=row["bce_status"],
                creation_date=row["creation_date"],
                nbb_data=nbb if nbb.available else None,
            )
            # Invalide AUSSI le rapport IA caché (cf. backfill_nbb_via_playwright)
            conn.execute(
                "UPDATE businesses SET "
                "  credit_color = ?, credit_score = ?, credit_label = ?, "
                "  credit_reasons = ?, credit_computed_at = ?, "
                "  credit_ai_report = NULL, credit_ai_report_at = NULL, "
                "  credit_ai_report_meta = NULL "
                "WHERE dedup_key = ?",
                (
                    score.color, score.score, score.label,
                    json.dumps(score.reasons, ensure_ascii=False),
                    score.computed_at, row["dedup_key"],
                ),
            )
            updated += 1
            by_color[score.color] = by_color.get(score.color, 0) + 1

        conn.commit()

    # Resume (ASCII-only pour eviter UnicodeEncodeError sur Windows cp1252)
    print(f"OK - {updated} fiche(s) scoree(s)\n")
    print("Repartition par couleur :")
    color_order = ["green", "yellow", "orange", "red", "gray"]
    icons = {"green": "[GREEN]", "yellow": "[YELLOW]", "orange": "[ORANGE]",
             "red": "[RED]", "gray": "[GRAY]"}
    for c in color_order:
        if c in by_color:
            print(f"  {icons[c]:9s} {c:8s} : {by_color[c]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

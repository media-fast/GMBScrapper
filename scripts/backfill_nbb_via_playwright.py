"""Back-fill batch des données BNB via Playwright (SANS clé API).

Pour chaque fiche avec BCE mais sans `nbb_year` en DB :
  1. Charge consult.cbso.nbb.be via Playwright headless
  2. Extrait year + deposit_date + model_type + deposits_count
  3. UPDATE businesses
  4. Recalcule credit_score avec les nouvelles données

Lent (~3-5 s par fiche). Un seul browser Chromium est lancé pour TOUTES
les fiches → économie de ~2 s par fiche vs scrape unitaire.

Usage :
    python -m scripts.backfill_nbb_via_playwright          # toutes les
                                                            # fiches éligibles
    python -m scripts.backfill_nbb_via_playwright --limit 10   # premières 10
    python -m scripts.backfill_nbb_via_playwright --force     # re-scrape
                                                                # même les fiches
                                                                # déjà enrichies

Idempotent par défaut (skip les fiches qui ont déjà nbb_year).
"""

import argparse
import asyncio
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enrichment.credit_score import compute_credit_score  # noqa: E402
from enrichment.nbb_scraper import batch_scrape_nbb_async  # noqa: E402
from storage.history import DB_PATH, init_db  # noqa: E402


def _select_targets(force: bool, limit: int) -> list[sqlite3.Row]:
    """Retourne les fiches à enrichir."""
    init_db()
    where = (
        "WHERE bce_number IS NOT NULL AND bce_number != ''"
        if force else
        "WHERE bce_number IS NOT NULL AND bce_number != '' "
        "  AND (nbb_year IS NULL OR nbb_year = '')"
    )
    sql = (
        f"SELECT dedup_key, name, bce_number, bce_status, creation_date "
        f"FROM businesses {where} ORDER BY name"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql).fetchall()


async def _enrich_all(rows: list[sqlite3.Row]) -> int:
    """Scrape toutes les fiches + persiste + recompute score. Renvoie le
    nombre de fiches enrichies avec succès."""
    bces = [r["bce_number"] for r in rows]

    def progress(i: int, total: int, bce: str) -> None:
        print(f"  [{i:3d}/{total}] BCE {bce} ...", flush=True)

    t0 = time.time()
    results = await batch_scrape_nbb_async(bces, progress=progress)
    elapsed = time.time() - t0
    print(f"\nScrape termine en {elapsed:.1f}s ({elapsed/max(len(bces),1):.1f}s/fiche)")

    updated = 0
    by_color: dict[str, int] = {}
    with sqlite3.connect(DB_PATH) as conn:
        for row in rows:
            data = results.get(row["bce_number"])
            if not data:
                continue
            # Recompute credit_score AVEC les nouvelles données (même si
            # data.available=False, ça affine la raison via nbb_data fourni)
            score = compute_credit_score(
                bce_status=row["bce_status"],
                creation_date=row["creation_date"],
                nbb_data=data,
            )
            # ⚠ On invalide AUSSI le rapport IA caché (Phase 2) car il a
            # été généré avec l'ancien contexte (ex: orange « non vérifié »).
            # Le prochain clic « Voir l'analyse complète » regénérera un
            # rapport frais basé sur le nouveau scoring.
            conn.execute(
                "UPDATE businesses SET "
                "  nbb_year = COALESCE(?, nbb_year), "
                "  nbb_deposit_date = ?, nbb_model_type = ?, "
                "  nbb_deposits_count = ?, "
                "  credit_color = ?, credit_score = ?, credit_label = ?, "
                "  credit_reasons = ?, credit_computed_at = ?, "
                "  credit_ai_report = NULL, credit_ai_report_at = NULL, "
                "  credit_ai_report_meta = NULL "
                "WHERE dedup_key = ?",
                (
                    data.year, data.deposit_date, data.model_type,
                    data.deposits_count,
                    score.color, score.score, score.label,
                    json.dumps(score.reasons, ensure_ascii=False),
                    score.computed_at, row["dedup_key"],
                ),
            )
            if data.available:
                updated += 1
            by_color[score.color] = by_color.get(score.color, 0) + 1
        conn.commit()

    print(f"\nOK - {updated}/{len(rows)} fiches enrichies avec dépôts BNB")
    print("\nNouvelle repartition credit_color :")
    icons = {"green": "[GREEN]", "yellow": "[YELLOW]", "orange": "[ORANGE]",
             "red": "[RED]", "gray": "[GRAY]"}
    for c in ("green", "yellow", "orange", "red", "gray"):
        if c in by_color:
            print(f"  {icons[c]:9s} {c:8s} : {by_color[c]}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=0,
                        help="Limite le nombre de fiches à traiter")
    parser.add_argument("--force", action="store_true",
                        help="Re-scrape même les fiches déjà enrichies")
    args = parser.parse_args()

    rows = _select_targets(args.force, args.limit)
    if not rows:
        print("Aucune fiche eligible (toutes deja enrichies ou pas de BCE).")
        return 0

    print(f"-> {len(rows)} fiche(s) a scraper via Playwright "
          f"(~{len(rows) * 4:.0f}s estimes)\n")
    asyncio.run(_enrich_all(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

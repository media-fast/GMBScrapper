"""Smoke test rapide sans Streamlit.

Usage :
    python cli_test.py "opticien" "Waterloo" --max 3

Affiche les fiches scrapées + l'enrichissement TVA dans la console.
"""

import argparse

from enrichment import enrich_all
from scraper import scrape_google_maps


def main() -> None:
    parser = argparse.ArgumentParser(description="Test ScrapperGMB en CLI")
    parser.add_argument("query", help="Métier (ex: opticien)")
    parser.add_argument("city", help="Ville (ex: Waterloo)")
    parser.add_argument("--max", type=int, default=5, help="Nombre max de résultats")
    parser.add_argument("--no-vat", action="store_true", help="Ne pas chercher la TVA")
    parser.add_argument("--show", action="store_true", help="Afficher le navigateur")
    args = parser.parse_args()

    def log(msg: str) -> None:
        print(msg, flush=True)

    print(f"\n=== Recherche : {args.query} à {args.city} (max {args.max}) ===\n")

    businesses = scrape_google_maps(
        query=args.query,
        cities=[args.city],
        max_results_per_city=args.max,
        headless=not args.show,
        on_progress=log,
    )

    print(f"\n--- {len(businesses)} entreprises extraites ---\n")

    if not args.no_vat and businesses:
        print("\n=== Enrichissement TVA ===\n")
        businesses = enrich_all(businesses, on_progress=log, delay_between=0.5)

    print("\n=== Résultats ===\n")
    for b in businesses:
        print(f"• {b.name}")
        print(f"   Adresse  : {b.address}")
        print(f"   Tél      : {b.phone}")
        print(f"   Web      : {b.website}")
        print(f"   TVA      : {b.vat_number}  ({b.bce_match_warning})")
        print(f"   Catégorie: {b.category}")
        print()


if __name__ == "__main__":
    main()

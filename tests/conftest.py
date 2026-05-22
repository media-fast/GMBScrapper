"""Configuration partagée des tests pytest."""

import sys
from pathlib import Path

# Permet aux tests d'importer scraper, storage, enrichment depuis la racine
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

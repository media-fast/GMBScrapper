"""Backend FastAPI pour le POC React+Tailwind.

Réutilise les modules Python existants (storage, scraper, enrichment) — zéro
duplication de logique. Le but : exposer les opérations en REST pour que le
frontend React les consomme à la place de l'UI Streamlit.

Démarrer :
    uvicorn backend.main:app --reload --port 8000

Doc auto-générée :
    http://localhost:8000/docs
"""

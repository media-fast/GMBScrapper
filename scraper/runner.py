"""Exécution du pipeline de scraping en arrière-plan (thread Streamlit-safe).

Le scraping est lancé dans un threading.Thread auquel on attache le contexte
Streamlit (add_script_run_ctx) → le thread peut lire/écrire st.session_state
tout en SURVIVANT aux reruns du script principal déclenchés par les interactions
widget de l'utilisateur.

Architecture :

    [main thread]                     [scraping thread]
    ───────────────                  ──────────────────
    click "Lancer"
        │
        ├── start_background_scrape() ──► thread_target_fn()
        │                                 │
        ├── st.rerun() (auto-refresh)     ├── scrape_google_maps()
        │   ├── lit scrape_state[]        ├── filter_by_city()
        │   ├── affiche progress panel    ├── enrich_all_parallel()
        │   └── st.rerun() ◄──────────────┤── (update scrape_state[] à chaque étape)
        │                                 │
        └── boucle tant que active=True   └── save_search() → done

L'utilisateur peut modifier la form, naviguer les tabs, etc. : le thread
continue son travail indépendamment.
"""

import threading
from datetime import datetime
from typing import Any, Callable, MutableMapping

from streamlit.runtime.scriptrunner import add_script_run_ctx

from .filters import filter_by_city
from .gmaps import scrape_google_maps


# Phases possibles de scrape_state["phase"]
PHASE_IDLE = "idle"
PHASE_SCRAPING = "scraping"
PHASE_FILTERING = "filtering"
PHASE_DEDUP_SEEN = "dedup_seen"
PHASE_ENRICHMENT = "enrichment"
PHASE_DEDUP_POST = "dedup_post"
PHASE_SAVING = "saving"
PHASE_DONE = "done"
PHASE_CANCELLED = "cancelled"
PHASE_ERROR = "error"


def init_scrape_state() -> dict:
    """Structure par défaut pour st.session_state.scrape_state."""
    return {
        "active": False,
        "phase": PHASE_IDLE,
        "started_at": None,
        "ended_at": None,
        "communes_done": 0,
        "communes_total": 0,
        # Compteurs distincts pour la transparence (cf. _render_*_panel)
        "prospects_brut": 0,        # Fiches brutes scrapées sur Google (monotone)
        "prospects_found": 0,       # Fiches restantes après chaque filtre (décroît)
        "vat_enriched": 0,
        "skipped_count": 0,
        "dropped_count": 0,
        # Détail des pertes par étape (pour le panneau Terminé)
        "losses": {
            "city_filter": 0,        # filtrage strict par ville
            "dedup_seen": 0,         # déjà connues dans l'historique
            "dedup_post_bce": 0,     # doublons révélés post-enrichissement BCE
            "dedup_intra": 0,        # mêmes BCE + même postal dans le même batch
            "phone_filter": 0,       # téléphone obligatoire
        },
        "last_log": "",
        "log_lines": [],
        "metiers": [],
        "cities": [],
        "result_search_id": None,
        "result_count": 0,
        "error": None,
        "cancel_requested": False,
    }


def _append_log(state: MutableMapping[str, Any], msg: str, max_lines: int = 50) -> None:
    state["last_log"] = msg
    lines = state.get("log_lines") or []
    lines.append(f"{datetime.now().strftime('%H:%M:%S')} · {msg}")
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    state["log_lines"] = lines


def _run_pipeline(
    state: MutableMapping[str, Any],
    *,
    metiers: list[str],
    cities: list[str],
    max_per_city: int,
    headless: bool,
    strict_city: bool,
    exclude_seen: bool,
    require_phone: bool,
    do_vat: bool,
    do_bce: bool,
    do_fin: bool,
    workers: int,
) -> None:
    """Pipeline complet, exécuté dans le thread background."""
    # Imports tardifs pour éviter les cycles + s'assurer du chargement dans le thread
    from enrichment import enrich_all_parallel
    from storage import mark_seen, save_search
    from storage.history import dedup_key as _dk

    state["active"] = True
    state["phase"] = PHASE_SCRAPING
    state["started_at"] = datetime.now()
    state["ended_at"] = None
    state["communes_total"] = len(metiers) * len(cities)
    state["communes_done"] = 0
    state["prospects_brut"] = 0
    state["prospects_found"] = 0
    state["vat_enriched"] = 0
    state["skipped_count"] = 0
    state["dropped_count"] = 0
    state["losses"] = {
        "city_filter": 0,
        "dedup_seen": 0,
        "dedup_post_bce": 0,
        "dedup_intra": 0,
        "phone_filter": 0,
    }
    state["log_lines"] = []
    state["last_log"] = "Démarrage…"
    state["metiers"] = list(metiers)
    state["cities"] = list(cities)
    state["error"] = None
    state["result_search_id"] = None
    state["result_count"] = 0

    def _cancelled() -> bool:
        return bool(state.get("cancel_requested", False))

    def _log(msg: str) -> None:
        _append_log(state, msg)

    try:
        businesses = []
        # --- Scraping ville par ville (granularité fine pour la progression) ---
        for m in metiers:
            if _cancelled():
                state["phase"] = PHASE_CANCELLED
                _log("Recherche annulée par l'utilisateur.")
                return
            _log(f"Scraping métier : {m}")
            for city in cities:
                if _cancelled():
                    state["phase"] = PHASE_CANCELLED
                    _log("Recherche annulée par l'utilisateur.")
                    return

                # on_progress du scraper alimente le log mais pas les compteurs
                def _scrape_progress(msg: str) -> None:
                    _log(msg)

                part = scrape_google_maps(
                    query=m,
                    cities=[city],
                    max_results_per_city=max_per_city,
                    headless=headless,
                    on_progress=_scrape_progress,
                )
                businesses.extend(part)
                state["communes_done"] += 1
                # prospects_brut = total scrapé sur Google (monotone)
                # prospects_found = pareil pendant le scrape, sera décrémenté
                # par chaque filtre qui suit
                state["prospects_brut"] = len(businesses)
                state["prospects_found"] = len(businesses)
                _log(f"{m} · {city} — {len(part)} prospects (total {len(businesses)})")

        _log(f"Scraping terminé : {len(businesses)} fiches brutes.")

        # --- Filtre ville ---
        dropped = []
        if strict_city and businesses:
            state["phase"] = PHASE_FILTERING
            businesses, dropped = filter_by_city(businesses)
            state["dropped_count"] = len(dropped)
            state["losses"]["city_filter"] = len(dropped)
            state["prospects_found"] = len(businesses)
            _log(f"Filtre ville : {len(businesses)} gardées, {len(dropped)} hors zone.")

        # --- Dédup historique ---
        skipped = []
        if exclude_seen and businesses:
            state["phase"] = PHASE_DEDUP_SEEN
            mark_seen(businesses)
            skipped = [b for b in businesses if b.already_seen]
            businesses = [b for b in businesses if not b.already_seen]
            state["skipped_count"] = len(skipped)
            state["losses"]["dedup_seen"] = len(skipped)
            state["prospects_found"] = len(businesses)
            if skipped:
                _log(f"Dédup historique : {len(skipped)} déjà connues écartées.")

        # --- Enrichissement (parallèle) ---
        if (do_vat or do_bce or do_fin) and businesses:
            if _cancelled():
                state["phase"] = PHASE_CANCELLED
                _log("Annulée avant enrichissement.")
                return
            state["phase"] = PHASE_ENRICHMENT
            _log(f"Enrichissement parallèle (workers={workers})…")
            try:
                businesses = enrich_all_parallel(
                    businesses, on_progress=_log, max_workers=workers
                )
                state["vat_enriched"] = sum(1 for b in businesses if b.vat_number)
            except Exception as e:  # noqa: BLE001
                _log(f"! Erreur enrichissement : {e}")

        if _cancelled():
            state["phase"] = PHASE_CANCELLED
            _log("Recherche annulée après enrichissement.")
            return

        # --- Re-dédup post-BCE ---
        if exclude_seen and businesses:
            state["phase"] = PHASE_DEDUP_POST
            mark_seen(businesses)
            newly = [b for b in businesses if b.already_seen]
            if newly:
                skipped += newly
                businesses = [b for b in businesses if not b.already_seen]
                state["skipped_count"] = len(skipped)
                state["losses"]["dedup_post_bce"] = len(newly)
                state["prospects_found"] = len(businesses)
                _log(f"Dédup post-BCE : {len(newly)} doublons supplémentaires écartés.")

        # --- Dédup intra-batch ---
        seen_keys: set[str] = set()
        unique = []
        for b in businesses:
            k = _dk(b)
            if k in seen_keys:
                continue
            seen_keys.add(k)
            unique.append(b)
        intra_dupes = len(businesses) - len(unique)
        if intra_dupes:
            state["losses"]["dedup_intra"] = intra_dupes
            _log(f"Dédup intra-batch : {intra_dupes} doublons fusionnés.")
        businesses = unique
        state["prospects_found"] = len(businesses)

        # --- Filtre téléphone obligatoire ---
        if require_phone:
            before = len(businesses)
            businesses = [b for b in businesses if b.phone]
            removed = before - len(businesses)
            if removed:
                state["losses"]["phone_filter"] = removed
                state["prospects_found"] = len(businesses)
                _log(f"Filtre téléphone : {removed} fiches sans tél écartées.")

        # --- Sauvegarde ---
        state["phase"] = PHASE_SAVING
        if len(metiers) == 1:
            search_label = metiers[0]
        else:
            search_label = " / ".join(metiers[:3]) + (" …" if len(metiers) > 3 else "")
        try:
            new_search_id = save_search(search_label, cities, businesses)
            state["result_search_id"] = new_search_id
        except Exception as e:  # noqa: BLE001
            _log(f"! Erreur sauvegarde : {e}")

        state["result_count"] = len(businesses)
        state["vat_enriched"] = sum(1 for b in businesses if b.vat_number)
        state["phase"] = PHASE_DONE
        _log(
            f"Terminé : {len(businesses)} entreprises, "
            f"{state['vat_enriched']} avec TVA."
        )

    except Exception as e:  # noqa: BLE001
        state["phase"] = PHASE_ERROR
        state["error"] = str(e)
        _log(f"! Erreur inattendue : {e}")
    finally:
        state["active"] = False
        state["ended_at"] = datetime.now()


def start_background_scrape(
    state: MutableMapping[str, Any],
    **pipeline_kwargs,
) -> threading.Thread:
    """Lance le pipeline dans un thread et l'enregistre avec le contexte Streamlit.

    Le `state` est une référence vers `st.session_state.scrape_state` (un dict
    Streamlit-managed). Toute écriture dans le thread est immédiatement visible
    par le main thread sur le prochain rerun.
    """
    # Reset complet de l'état avant de démarrer
    state.update(init_scrape_state())
    state["active"] = True  # affichage immédiat du panel de progression
    state["phase"] = PHASE_SCRAPING
    state["cancel_requested"] = False
    state["started_at"] = datetime.now()

    def _target() -> None:
        try:
            _run_pipeline(state, **pipeline_kwargs)
        except Exception as e:  # filet de sécurité supplémentaire
            state["phase"] = PHASE_ERROR
            state["error"] = str(e)
            state["active"] = False

    thread = threading.Thread(target=_target, daemon=True, name="ScrapingThread")
    # Attache le contexte d'exécution Streamlit au thread → accès session_state OK
    add_script_run_ctx(thread)
    thread.start()
    return thread


def request_cancel(state: MutableMapping[str, Any]) -> None:
    """Demande l'arrêt propre du scrape en cours."""
    if state.get("active"):
        state["cancel_requested"] = True
        _append_log(state, "Annulation demandée — arrêt à la prochaine étape…")

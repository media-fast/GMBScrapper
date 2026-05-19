from datetime import datetime

import pandas as pd
import streamlit as st

from enrichment import enrich_all_parallel
from export import to_dataframe, to_excel_bytes
from integrations import (
    click_to_call,
    is_configured,
    push_contacts,
    ringover_csv,
    sync_call_statuses,
)
from scraper import filter_by_city, scrape_google_maps
from storage import (
    CALL_STATUSES,
    bulk_update_campaign,
    campaign_stats,
    clear_history,
    get_campaign_businesses,
    get_known_businesses,
    history_stats,
    init_db,
    list_searches,
    mark_seen,
    save_search,
)


st.set_page_config(
    page_title="ScrapperGMB — Prospection B2B",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp { font-family: 'Inter', sans-serif; }
    .stApp { background: #f1f5f9; }

    [data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] * { color: #e2e8f0; }
    [data-testid="stSidebar"] h3 { color: #38bdf8 !important; font-weight: 700; font-size: 0.95rem; }
    [data-testid="stSidebar"] label { color: #cbd5e1 !important; font-weight: 500; }
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stTextArea textarea {
        background: #1e293b; color: #f1f5f9; border: 1px solid #334155; border-radius: 8px;
    }

    .block-container { padding-top: 1.5rem; padding-bottom: 4rem; max-width: 1480px; }

    h1, h2, h3 { color: #0f172a; letter-spacing: -0.02em; }

    .hero {
        background: linear-gradient(125deg, #0f172a 0%, #1e3a8a 55%, #0e7490 100%);
        color: white;
        padding: 1.9rem 2.2rem;
        border-radius: 18px;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.25);
    }
    .hero h1 { color: white; margin: 0 0 0.4rem 0; font-size: 1.95rem !important; font-weight: 800; }
    .hero p { color: #bae6fd; margin: 0; font-size: 1rem; font-weight: 400; }
    .hero .badge {
        display: inline-block; margin-top: 0.9rem; padding: 0.3rem 0.85rem;
        background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.35);
        border-radius: 999px; font-size: 0.8rem; color: #7dd3fc; font-weight: 600;
    }

    [data-testid="stMetric"] {
        background: white; border: 1px solid #e2e8f0; border-radius: 14px;
        padding: 1rem 1.15rem; box-shadow: 0 1px 3px rgba(15,23,42,0.04);
    }
    [data-testid="stMetricLabel"] { font-size: 0.78rem; color: #64748b; font-weight: 600; }
    [data-testid="stMetricValue"] { font-size: 1.7rem; color: #0f172a; font-weight: 800; }

    .stButton > button[kind="primary"] {
        background: linear-gradient(120deg, #2563eb, #0891b2);
        border: 0; border-radius: 11px; font-weight: 700; padding: 0.62rem 1rem;
        box-shadow: 0 4px 12px rgba(37,99,235,0.35); color: white;
    }
    .stButton > button[kind="primary"]:hover { filter: brightness(1.08); }
    .stDownloadButton > button {
        background: #0891b2; color: white; border: 0; border-radius: 11px; font-weight: 700;
    }
    .stDownloadButton > button:hover { background: #0e7490; }

    div[data-baseweb="tab-list"] {
        background: white; border-radius: 12px; padding: 0.35rem;
        border: 1px solid #e2e8f0; gap: 0.25rem;
    }
    div[data-baseweb="tab"] { border-radius: 9px; padding: 0.5rem 1.1rem; font-weight: 600; color: #64748b; }
    div[data-baseweb="tab"][aria-selected="true"] { background: #0f172a; color: #38bdf8; }

    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }

    .empty-state {
        text-align: center; padding: 3.5rem 1rem; background: white;
        border: 2px dashed #cbd5e1; border-radius: 16px; color: #64748b;
    }
    .empty-state .icon { font-size: 3.2rem; margin-bottom: 0.5rem; }
    .empty-state h3 { color: #334155; margin: 0.5rem 0; }

    #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


PRESETS = {
    "Opticiens Brabant Wallon sud": {
        "query": "opticien",
        "cities": "Waterloo\nBraine-l'Alleud\nNivelles\nLa Hulpe\nHalle",
    },
    "Dentistes Brabant Wallon": {
        "query": "dentiste",
        "cities": "Wavre\nOttignies\nLouvain-la-Neuve\nRixensart\nWaterloo",
    },
    "Garages Bruxelles sud": {
        "query": "garage automobile",
        "cities": "Uccle\nIxelles\nForest\nSaint-Gilles",
    },
}

DISPLAY_COLUMNS = [
    "Rang Google", "Nom", "Catégorie", "Localité", "Téléphone", "Email pro",
    "Dirigeant(s)", "Numéro TVA", "Numéro BCE", "Date de création",
    "Note Google", "Site web", "Comptes annuels (BNB)", "Fiche CompanyWeb",
    "Lien Google Maps", "Déjà vue",
]


def _init_state():
    defaults = {
        "results": [], "dropped": [], "skipped": [], "log": [],
        "last_run": None,
        "preset_query": "opticien",
        "preset_cities": "Waterloo\nBraine-l'Alleud\nNivelles\nLa Hulpe\nHalle",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


st.markdown(
    """
    <div class="hero">
        <h1>🎯 ScrapperGMB — Prospection B2B</h1>
        <p>Listes de prospects qualifiés : coordonnées, dirigeants, n° TVA, données BCE & financières.</p>
        <span class="badge">Google Maps · BCE/KBO · BNB · CompanyWeb</span>
    </div>
    """,
    unsafe_allow_html=True,
)


with st.sidebar:
    st.markdown("### 🔍 Recherche")

    preset = st.selectbox(
        "Préréglage",
        ["— Personnalisé —"] + list(PRESETS.keys()),
        index=0,
    )
    if preset != "— Personnalisé —":
        st.session_state.preset_query = PRESETS[preset]["query"]
        st.session_state.preset_cities = PRESETS[preset]["cities"]

    query = st.text_input("Métier / activité", value=st.session_state.preset_query,
                          placeholder="ex : opticien, plombier…")
    cities_raw = st.text_area("Villes (une par ligne)", value=st.session_state.preset_cities, height=130)
    max_per_city = st.slider("Résultats max par ville", 5, 60, 20, 5)
    strict_city = st.toggle("Filtrage strict par ville", value=True,
                            help="Élimine les fiches hors de la ville recherchée")
    exclude_seen = st.toggle("Exclure les entreprises déjà trouvées", value=True,
                             help="Ignore les entreprises présentes dans l'historique des recherches")

    st.markdown("### 💼 Enrichissement")
    do_vat = st.toggle("TVA (site web + KBO)", value=True)
    do_bce = st.toggle("Détail BCE (dirigeants, NACE…)", value=True)
    do_fin = st.toggle("Liens financiers (BNB, CompanyWeb)", value=True)

    with st.expander("⚙️ Paramètres avancés"):
        headless = st.checkbox("Navigateur invisible", value=True)
        workers = st.slider("Workers parallèles", 1, 10, 6)

    st.markdown("")
    run = st.button("🚀 Lancer la recherche", type="primary", use_container_width=True)

    stats = history_stats()
    st.markdown("### 📊 Historique")
    st.caption(
        f"{stats['searches']} recherches · {stats['businesses']} entreprises connues "
        f"· {stats['with_vat']} avec TVA"
    )


tab_results, tab_campaign, tab_dropped, tab_history, tab_help = st.tabs(
    ["📋 Résultats", "📞 Campagne d'appels", "🚫 Hors zone", "🕓 Historique", "ℹ️ Aide"]
)


def log(msg: str) -> None:
    st.session_state.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


if run:
    cities = [c.strip() for c in cities_raw.splitlines() if c.strip()]
    if not query.strip() or not cities:
        st.error("Indique un métier et au moins une ville.")
    else:
        st.session_state.results = []
        st.session_state.dropped = []
        st.session_state.skipped = []
        st.session_state.log = []

        with tab_results:
            status_box = st.status("Recherche en cours…", expanded=True)
            log_ph = status_box.empty()

            def render_log():
                log_ph.code("\n".join(st.session_state.log[-15:]), language="text")

            def cb(msg: str) -> None:
                log(msg)
                render_log()

            try:
                log("Scraping Google Maps…")
                render_log()
                businesses = scrape_google_maps(
                    query=query, cities=cities, max_results_per_city=max_per_city,
                    headless=headless, on_progress=cb,
                )
                log(f"Scraping terminé : {len(businesses)} fiches brutes")
            except Exception as e:
                st.error(f"Erreur scraping : {e}")
                businesses = []

            dropped: list = []
            if strict_city and businesses:
                businesses, dropped = filter_by_city(businesses)
                log(f"Filtre ville : {len(businesses)} gardées, {len(dropped)} hors zone")
                render_log()

            skipped: list = []
            if exclude_seen and businesses:
                mark_seen(businesses)
                skipped = [b for b in businesses if b.already_seen]
                businesses = [b for b in businesses if not b.already_seen]
                log(f"Dédup historique : {len(skipped)} déjà connues écartées")
                render_log()

            if (do_vat or do_bce or do_fin) and businesses:
                log(f"Enrichissement parallèle (workers={workers})…")
                render_log()
                try:
                    businesses = enrich_all_parallel(businesses, on_progress=cb, max_workers=workers)
                except Exception as e:
                    st.error(f"Erreur enrichissement : {e}")

            if exclude_seen and businesses:
                # Re-check : le n° BCE découvert peut révéler des doublons
                mark_seen(businesses)
                newly = [b for b in businesses if b.already_seen]
                if newly:
                    skipped += newly
                    businesses = [b for b in businesses if not b.already_seen]
                    log(f"Dédup post-BCE : {len(newly)} doublons supplémentaires écartés")

            try:
                save_search(query, cities, businesses)
            except Exception as e:
                log(f"! Erreur sauvegarde historique : {e}")

            st.session_state.results = businesses
            st.session_state.dropped = dropped
            st.session_state.skipped = skipped
            st.session_state.last_run = datetime.now()

            vat_n = sum(1 for b in businesses if b.vat_number)
            log(f"✅ Terminé : {len(businesses)} nouvelles entreprises, {vat_n} avec TVA")
            render_log()
            status_box.update(label=f"✅ Recherche terminée — {len(businesses)} nouvelles fiches",
                              state="complete", expanded=False)


results = st.session_state.results
dropped = st.session_state.dropped
skipped = st.session_state.skipped


def _style_top(row):
    rank = row.get("Rang Google")
    if rank == 1:
        return ["background-color: #fef3c7"] * len(row)
    if rank == 2:
        return ["background-color: #e2e8f0"] * len(row)
    return [""] * len(row)


with tab_results:
    if results:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Nouvelles fiches", len(results))
        c2.metric("🥇 Top 2 Google", sum(1 for b in results if b.is_top_ranked))
        c3.metric("📞 Téléphone", sum(1 for b in results if b.phone))
        c4.metric("✉️ Email", sum(1 for b in results if b.email))
        c5.metric("💼 TVA", sum(1 for b in results if b.vat_number))
        c6.metric("👤 Dirigeant", sum(1 for b in results if b.managers))

        st.markdown("")
        f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
        search_text = f1.text_input("Filtrer", placeholder="Nom, ville, dirigeant…",
                                    label_visibility="collapsed")
        only_phone = f2.checkbox("Avec téléphone")
        only_vat = f3.checkbox("Avec TVA")
        only_top = f4.checkbox("Top 2 Google")

        filtered = results
        if search_text:
            s = search_text.lower()
            filtered = [b for b in filtered if any(
                s in (getattr(b, f) or "").lower()
                for f in ["name", "locality", "city", "category", "address", "managers"]
            )]
        if only_phone:
            filtered = [b for b in filtered if b.phone]
        if only_vat:
            filtered = [b for b in filtered if b.vat_number]
        if only_top:
            filtered = [b for b in filtered if b.is_top_ranked]

        if filtered:
            full_df = to_dataframe(filtered)
            display_cols = [c for c in DISPLAY_COLUMNS if c in full_df.columns]
            display_df = full_df[display_cols]

            styler = display_df.style.apply(_style_top, axis=1)

            st.dataframe(
                styler,
                use_container_width=True,
                hide_index=True,
                height=520,
                column_config={
                    "Rang Google": st.column_config.NumberColumn("Rang", width="small"),
                    "Site web": st.column_config.LinkColumn("Site web", width="small"),
                    "Comptes annuels (BNB)": st.column_config.LinkColumn("BNB", width="small"),
                    "Fiche CompanyWeb": st.column_config.LinkColumn("CompanyWeb", width="small"),
                    "Lien Google Maps": st.column_config.LinkColumn("GMaps", width="small"),
                    "Note Google": st.column_config.NumberColumn(format="%.1f ⭐"),
                    "Déjà vue": st.column_config.CheckboxColumn("Déjà vue", width="small"),
                },
            )
            st.caption("🥇 Ligne dorée = 1er sur Google · 🥈 ligne grise = 2e sur Google")

            colA, colB = st.columns([3, 1])
            with colA:
                if st.session_state.last_run:
                    st.caption(f"Dernière recherche : {st.session_state.last_run.strftime('%d/%m/%Y à %H:%M')}")
            with colB:
                excel_bytes = to_excel_bytes(filtered)
                fname = f"prospects_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.download_button("📥 Télécharger Excel", data=excel_bytes, file_name=fname,
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
        else:
            st.info("Aucun résultat ne correspond aux filtres actifs.")

        if skipped:
            with st.expander(f"🔁 {len(skipped)} entreprises écartées (déjà trouvées avant)"):
                sk_df = to_dataframe(skipped)
                show = [c for c in ["Nom", "Localité", "Numéro TVA", "Vue pour la 1re fois"] if c in sk_df.columns]
                st.dataframe(sk_df[show], use_container_width=True, hide_index=True)
    else:
        st.markdown(
            """
            <div class="empty-state">
                <div class="icon">🎯</div>
                <h3>Prêt à prospecter</h3>
                <p>Configure ta recherche dans le panneau de gauche puis clique sur <strong>Lancer la recherche</strong>.</p>
                <p style="font-size:0.85rem;color:#94a3b8;">Astuce : un préréglage remplit métier + villes en un clic.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.log:
        with st.expander("📜 Journal d'exécution"):
            st.code("\n".join(st.session_state.log), language="text")


with tab_campaign:
    cstats = campaign_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📋 À appeler", cstats.get("À appeler", 0))
    m2.metric("✅ Déjà appelé", cstats.get("Déjà appelé", 0))
    m3.metric("🔁 À rappeler", cstats.get("À rappeler", 0))
    m4.metric("🚫 Ne plus rappeler", cstats.get("Ne plus rappeler", 0))

    if is_configured():
        st.success("🟢 Ringover connecté — envoi de contacts, click-to-call et synchronisation actifs.")
    else:
        st.warning(
            "🟠 Ringover non configuré. Définis la variable d'environnement `RINGOVER_API_KEY` "
            "pour activer l'envoi de contacts, le click-to-call et la synchro. "
            "Le suivi de statut et l'export CSV restent disponibles."
        )

    fcol1, fcol2 = st.columns([1, 2])
    status_filter = fcol1.selectbox("Filtrer par statut", ["Tous"] + CALL_STATUSES)
    camp = get_campaign_businesses(None if status_filter == "Tous" else status_filter)

    if not camp:
        st.info("La campagne est vide. Lance une recherche dans l'onglet Résultats pour l'alimenter.")
    else:
        df_camp = pd.DataFrame(camp)
        editor_df = pd.DataFrame({
            "dedup_key": df_camp["dedup_key"],
            "Entreprise": df_camp["name"].fillna(""),
            "Téléphone": df_camp["phone"].fillna(""),
            "Ville": df_camp["city"].fillna(""),
            "Dirigeant(s)": df_camp["managers"].fillna(""),
            "Statut": df_camp["call_status"].fillna("À appeler"),
            "Notes": df_camp["call_notes"].fillna(""),
            "Date de rappel": df_camp["callback_date"].fillna(""),
            "Dernier appel": df_camp["last_call_at"].fillna(""),
        })

        edited = st.data_editor(
            editor_df,
            hide_index=True,
            use_container_width=True,
            height=460,
            column_config={
                "dedup_key": None,
                "Entreprise": st.column_config.TextColumn(disabled=True, width="medium"),
                "Téléphone": st.column_config.TextColumn(disabled=True, width="small"),
                "Ville": st.column_config.TextColumn(disabled=True, width="small"),
                "Dirigeant(s)": st.column_config.TextColumn(disabled=True, width="medium"),
                "Statut": st.column_config.SelectboxColumn(
                    options=CALL_STATUSES, required=True, width="small"),
                "Notes": st.column_config.TextColumn(width="medium"),
                "Date de rappel": st.column_config.TextColumn(
                    help="Format AAAA-MM-JJ", width="small"),
                "Dernier appel": st.column_config.TextColumn(disabled=True, width="small"),
            },
        )

        if st.button("💾 Enregistrer les statuts", type="primary"):
            edits = []
            for _, row in edited.iterrows():
                edits.append({
                    "dedup_key": row["dedup_key"],
                    "call_status": row["Statut"],
                    "call_notes": row["Notes"] or "",
                    "callback_date": (row["Date de rappel"] or "").strip() or None,
                })
            n = bulk_update_campaign(edits)
            st.success(f"{n} fiche(s) mise(s) à jour.")
            st.rerun()

        st.markdown("#### 🔗 Actions Ringover")
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("📲 Envoyer ces contacts vers Ringover",
                         use_container_width=True, disabled=not is_configured()):
                res = push_contacts(camp)
                (st.success if res["ok"] else st.error)(res["message"])
                if res.get("errors"):
                    with st.expander("Détail des échecs"):
                        st.code("\n".join(res["errors"]), language="text")
        with a2:
            if st.button("🔄 Synchroniser les appels passés",
                         use_container_width=True, disabled=not is_configured()):
                res = sync_call_statuses()
                if res["ok"]:
                    st.success(res["message"])
                    st.rerun()
                else:
                    st.error(res["message"])
        with a3:
            st.download_button(
                "📥 Export CSV (import Ringover)",
                data=ringover_csv(camp),
                file_name=f"ringover_contacts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.markdown("#### 📞 Appeler une entreprise")
        callable_biz = [b for b in camp if b.get("phone")]
        if callable_biz:
            labels = {f"{b['name']} — {b['phone']}": b for b in callable_biz}
            cc1, cc2 = st.columns([3, 1])
            pick = cc1.selectbox("Entreprise à appeler", list(labels.keys()),
                                 label_visibility="collapsed")
            with cc2:
                if st.button("📞 Appeler maintenant", use_container_width=True,
                             disabled=not is_configured()):
                    res = click_to_call(labels[pick]["phone"])
                    (st.success if res["ok"] else st.error)(res["message"])
            st.caption(
                "Le click-to-call fait d'abord sonner ton téléphone Ringover, puis compose "
                "le numéro de l'entreprise. L'app Ringover desktop gère aussi les liens `tel:`."
            )
        else:
            st.caption("Aucune entreprise avec numéro de téléphone dans la sélection courante.")


with tab_dropped:
    if dropped:
        st.caption(f"{len(dropped)} fiches retournées par Google mais hors des villes recherchées. "
                   "Désactive le filtrage strict pour les inclure.")
        st.dataframe(to_dataframe(dropped), use_container_width=True, hide_index=True, height=420)
    else:
        st.info("Aucune fiche écartée par le filtre ville.")


with tab_history:
    st.markdown("#### Recherches passées")
    searches = list_searches(50)
    if searches:
        sdf = pd.DataFrame(searches)
        sdf = sdf.rename(columns={
            "id": "N°", "query": "Métier", "cities": "Villes", "ran_at": "Date",
            "total": "Total", "new_count": "Nouvelles",
        })[["N°", "Date", "Métier", "Villes", "Total", "Nouvelles"]]
        st.dataframe(sdf, use_container_width=True, hide_index=True, height=240)
    else:
        st.info("Aucune recherche enregistrée pour l'instant.")

    st.markdown("#### Entreprises connues (base de déduplication)")
    known = get_known_businesses(5000)
    if known:
        kdf = pd.DataFrame(known)
        kdf = kdf.rename(columns={
            "name": "Nom", "bce_number": "BCE", "vat_number": "TVA", "city": "Ville",
            "query": "Métier", "phone": "Téléphone", "managers": "Dirigeant(s)",
            "first_seen": "1re fois", "last_seen": "Dernière fois",
        })
        cols = [c for c in ["Nom", "Ville", "Métier", "TVA", "Téléphone", "Dirigeant(s)", "1re fois", "Dernière fois"]
                if c in kdf.columns]
        st.dataframe(kdf[cols], use_container_width=True, hide_index=True, height=360)

        st.download_button(
            "📥 Exporter tout l'historique (CSV)",
            data=kdf.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"historique_entreprises_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        with st.expander("⚠️ Réinitialiser l'historique"):
            st.warning("Cette action supprime toutes les recherches et la base de déduplication.")
            if st.button("Vider l'historique", type="secondary"):
                clear_history()
                st.success("Historique vidé. Recharge la page.")
    else:
        st.info("La base de déduplication est vide. Elle se remplit à chaque recherche.")


with tab_help:
    st.markdown(
        """
        ### Sources de données

        | Donnée | Source | Coût |
        |---|---|---|
        | Coordonnées, catégorie, note, classement | Google Maps | gratuit (scraping) |
        | N° TVA | Site web de l'entreprise + registre KBO/BCE | gratuit |
        | Dirigeants, date de création, capital, NACE | Fiche détail BCE | gratuit |
        | Comptes annuels (CA, fonds propres) | Banque Nationale de Belgique | lien gratuit ; API gratuite avec clé |
        | Solvabilité / expérience de paiement | CompanyWeb | abonnement payant |

        ### Classement Google
        Les **1er et 2e** résultats sont les plus visibles sur Google Maps — vos concurrents
        les mieux référencés. Ils sont surlignés (🥇 doré / 🥈 gris) dans le tableau et l'Excel.

        ### Historique & déduplication
        Chaque entreprise trouvée est mémorisée (par n° BCE, ou nom + code postal).
        Avec l'option **« Exclure les entreprises déjà trouvées »**, une nouvelle recherche
        ne renvoie que les entreprises **jamais vues** — le commercial ne retravaille jamais
        deux fois le même prospect. L'onglet *Historique* liste tout.

        ### Numéro de portable du gérant
        Le **GSM personnel** d'un dirigeant n'est disponible sur **aucune source publique
        légale** (RGPD). L'outil fournit : nom du/des dirigeant(s) via la BCE, l'email
        professionnel de l'entreprise, et le téléphone fixe. La colonne GSM reste à
        compléter manuellement.

        ### Activer l'enrichissement financier complet (optionnel)
        - **BNB** : inscription gratuite sur https://developer.cbso.nbb.be → définir la
          variable d'environnement `NBB_API_KEY`.
        - **CompanyWeb** : nécessite un abonnement → définir `COMPANYWEB_API_KEY` et
          compléter `enrichment/companyweb.py`.
        Sans clé, l'outil fournit quand même les **liens cliquables** vers les fiches BNB et CompanyWeb.

        ### RGPD
        La prospection B2B est admise sous *intérêt légitime*. Tenir un registre de
        traitement et offrir une désinscription dès le premier contact.
        """
    )

import os
import re
from datetime import datetime

# Charge .env si présent (clés Ringover, OpenAI, Anthropic, BNB, etc.)
# override=True : le .env l'emporte sur les variables d'environnement déjà définies.
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

import pandas as pd
import streamlit as st

from enrichment import enrich_all_parallel
from export import to_dataframe, to_excel_bytes
from integrations import (
    ai_is_configured,
    ai_provider_label,
    click_to_call,
    generate_briefing,
    is_configured,
    push_contacts,
    ringover_csv,
    sync_call_statuses,
)
from scraper import (
    expand_metier_synonyms,
    filter_by_city,
    init_scrape_state,
    request_cancel,
    scrape_google_maps,
    start_background_scrape,
    PHASE_CANCELLED,
    PHASE_DEDUP_POST,
    PHASE_DEDUP_SEEN,
    PHASE_DONE,
    PHASE_ENRICHMENT,
    PHASE_ERROR,
    PHASE_FILTERING,
    PHASE_SAVING,
    PHASE_SCRAPING,
)
import time
from audit import run_full_audit
from data import (
    ARRONDISSEMENTS,
    PROVINCES,
    all_arrondissement_labels,
    expand_arrondissements_to_communes,
)
from data.geo import all_known_commune_names, communes_within_radius
from integrations import ai_synonyms
from storage import (
    CALL_STATUSES,
    bulk_update_campaign,
    campaign_stats,
    clear_history,
    delete_search,
    get_briefing,
    get_campaign_businesses,
    get_known_businesses,
    get_search,
    get_search_businesses,
    get_seo_audit,
    history_stats,
    init_db,
    list_searches,
    mark_seen,
    save_briefing,
    save_search,
    save_seo_audit,
    update_call_fields,
)


# ---------------------------------------------------------------------------
# Icônes Lucide (SVG inline)
# ---------------------------------------------------------------------------
LUCIDE_PATHS = {
    "target":         '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "zap":            '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "phone":          '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "phone-call":     '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/><path d="M14.05 2a9 9 0 0 1 8 7.94"/><path d="M14.05 6A5 5 0 0 1 18 10"/>',
    "check-circle":   '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    "clock":          '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "ban":            '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    "circle-dot":     '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
    "mail":           '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "globe":          '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "briefcase":      '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
    "user":           '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "users":          '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "star":           '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "map-pin":        '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "map":            '<polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/><line x1="9" x2="9" y1="3" y2="18"/><line x1="15" x2="15" y1="6" y2="21"/>',
    "calendar":       '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    "bar-chart":      '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "download":       '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    "trash":          '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    "refresh":        '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/>',
    "external-link":  '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "coins":          '<circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/>',
    "building":       '<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/>',
    "landmark":       '<line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/>',
    "search":         '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "settings":       '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "info":           '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "save":           '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "send":           '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    "trophy":         '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "medal":          '<path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.12 2.2"/><path d="m13 12 5.88-9.8"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/>',
    "file-text":      '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>',
    "rocket":         '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/>',
    "alert-triangle": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "x":              '<line x1="18" x2="6" y1="6" y2="18"/><line x1="6" x2="18" y1="6" y2="18"/>',
    "check":          '<polyline points="20 6 9 17 4 12"/>',
    "link":           '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "history":        '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><polyline points="12 7 12 12 15 15"/>',
}


def lucide(name: str, size: int = 14, color: str = "currentColor", stroke: float = 2.0) -> str:
    """Renvoie un SVG Lucide inline (s'insère dans un <span> ou <div>)."""
    body = LUCIDE_PATHS.get(name)
    if not body:
        return ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:-2px;display:inline-block;flex-shrink:0;">'
        f'{body}</svg>'
    )


st.set_page_config(
    page_title="ScrapperGMB — Prospection B2B",
    page_icon=":material/contact_phone:",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


TAILWIND_CDN = """
<script src="https://cdn.tailwindcss.com"></script>
<script>
  if (window.tailwind) {
    window.tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: { 50: '#f5f3ff', 100: '#ede9fe', 200: '#ddd6fe',
                     300: '#c4b5fd', 400: '#a78bfa', 500: '#8b5cf6',
                     600: '#7c3aed', 700: '#6d28d9', 800: '#5b21b6', 900: '#4c1d95' },
          },
          fontFamily: { sans: ['Inter', 'sans-serif'] },
        }
      }
    }
  }
</script>
"""

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700;800&display=swap');

    :root {
        /* Charte Oui Allo */
        --bg:           #F2F0FF;
        --bg-alt:       #ECE9FF;
        --surface:      #FFFFFF;
        --ink:          #1A1535;
        --ink-soft:     #4A4566;
        --ink-mute:     #7F7A99;
        --line:         #E3DFF5;
        --line-strong:  #D2CDEA;
        --brand-50:     #EFEDFF;
        --brand-100:    #E5E2FF;
        --brand-200:    #C4BFFF;
        --brand-300:    #A7A0FF;
        --brand-400:    #8B7FFF;
        --brand-500:    #6B5FFF;
        --brand-600:    #4338F0;
        --brand-700:    #2E25C9;
        --brand-800:    #1E18A0;
        --accent:       #1F9D55;
        --accent-soft:  #DFF4E8;
        --warn:         #C2410C;
        --warn-soft:    #FBE7D8;
        --danger:       #B91C1C;
        --danger-soft:  #FBE3E3;

        /* Alias slate pour compat avec le code existant */
        --slate-50:  #F2F0FF;
        --slate-100: #ECE9FF;
        --slate-200: #E3DFF5;
        --slate-300: #D2CDEA;
        --slate-400: #BAB3DA;
        --slate-500: #7F7A99;
        --slate-600: #4A4566;
        --slate-700: #2E2A55;
        --slate-800: #1A1535;
        --slate-900: #100C26;

        --shadow-sm: 0 1px 2px rgba(26, 21, 53, 0.04);
        --shadow-md: 0 4px 18px -6px rgba(67, 56, 240, 0.18), 0 1px 3px rgba(26, 21, 53, 0.05);
        --shadow-lg: 0 18px 48px -16px rgba(67, 56, 240, 0.28);

        --font-display: 'Fraunces', 'Times New Roman', serif;
        --font-body:    'Inter', system-ui, -apple-system, sans-serif;
    }

    html, body, [class*="css"], .stApp {
        font-family: var(--font-body);
        color: var(--ink);
    }
    .stApp { background: var(--bg); }

    .block-container { padding-top: 1.4rem; padding-bottom: 4rem; max-width: 1480px; }

    h1, h2, h3, h4 {
        font-family: var(--font-display);
        color: var(--ink);
        letter-spacing: -0.01em;
        font-weight: 600;
    }
    /* Sauf h3/h4 dans la sidebar qui restent en Inter (style label) */
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
        font-family: var(--font-body) !important;
    }

    /* ----- Sidebar (Oui Allo : clair + accents violets) ----- */
    [data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid var(--slate-200);
        box-shadow: 4px 0 20px rgba(124, 58, 237, 0.04);
    }
    [data-testid="stSidebar"] h3 {
        color: var(--brand-700) !important;
        font-weight: 700; font-size: 0.78rem;
        text-transform: uppercase; letter-spacing: 0.08em;
        margin: 1rem 0 0.6rem 0;
    }
    [data-testid="stSidebar"] label { color: var(--slate-700) !important; font-weight: 600; font-size: 0.82rem; }
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stTextArea textarea {
        background: var(--slate-50);
        color: var(--slate-900);
        border: 1px solid var(--slate-200);
        border-radius: 10px;
    }
    [data-testid="stSidebar"] .stTextInput input:focus,
    [data-testid="stSidebar"] .stTextArea textarea:focus {
        border-color: var(--brand-500);
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15);
    }

    /* ----- Hero (style Oui Allo) ----- */
    .hero {
        background: transparent;
        padding: 0;
        margin-bottom: 2.2rem;
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 2rem;
        flex-wrap: wrap;
    }
    .hero-text { max-width: 720px; flex: 1; min-width: 300px; }
    .hero h1 {
        font-family: var(--font-display);
        color: var(--ink);
        margin: 0 0 0.7rem 0;
        font-size: 2.7rem !important;
        font-weight: 600;
        line-height: 1.08;
        letter-spacing: -0.02em;
    }
    .hero h1 em, .hero h1 .accent {
        font-style: italic;
        background: linear-gradient(120deg, transparent 0%, transparent 8%,
                                    var(--brand-100) 8%, var(--brand-100) 92%,
                                    transparent 92%);
        padding: 0 4px;
        color: var(--ink);
        font-weight: 600;
    }
    .hero p {
        color: var(--ink-soft);
        margin: 0;
        font-size: 1rem;
        max-width: 580px;
        line-height: 1.5;
    }
    .hero .hero-badge,
    .hero .eyebrow {
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--brand-600);
        background: var(--brand-100);
        padding: 6px 12px;
        border-radius: 999px;
        margin-bottom: 1rem;
    }
    .hero-stats { display: flex; gap: 2rem; padding-bottom: 0.3rem; flex-wrap: wrap; }
    .hero-stat-label {
        font-size: 0.7rem; letter-spacing: 0.08em; text-transform: uppercase;
        color: var(--ink-mute); font-weight: 600; margin-bottom: 4px;
    }
    .hero-stat-value {
        font-family: var(--font-display);
        font-size: 1.55rem; font-weight: 600;
        color: var(--ink); letter-spacing: -0.02em; line-height: 1;
    }
    .hero .hero-stack { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1.1rem; }
    .hero .hero-stack span {
        background: var(--brand-100); border: 1px solid var(--brand-200);
        color: var(--brand-700); padding: 4px 10px;
        border-radius: 8px; font-size: 0.76rem; font-weight: 600;
    }

    /* ----- Metrics ----- */
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid var(--slate-200);
        border-radius: 16px;
        padding: 1rem 1.15rem;
        box-shadow: var(--shadow-sm);
        transition: all 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
        border-color: var(--brand-200);
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.72rem; color: var(--slate-500); font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.04em;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.55rem; color: var(--slate-900); font-weight: 800;
    }

    /* ----- Buttons (style Oui Allo) ----- */
    .stButton > button[kind="primary"] {
        background: var(--ink);
        border: 0; border-radius: 12px;
        font-weight: 600; padding: 0.62rem 1.4rem;
        color: white;
        box-shadow: 0 4px 14px -4px rgba(26, 21, 53, 0.4);
        transition: all 0.2s;
    }
    .stButton > button[kind="primary"]:hover {
        background: var(--brand-600);
        transform: translateY(-1px);
        box-shadow: 0 6px 20px -4px rgba(67, 56, 240, 0.5);
    }
    .stButton > button:not([kind="primary"]) {
        background: white;
        color: var(--ink-soft);
        border: 1px solid var(--line);
        border-radius: 12px;
        font-weight: 500;
        transition: all 0.2s;
    }
    .stButton > button:not([kind="primary"]):hover {
        background: var(--brand-100);
        border-color: var(--brand-300);
        color: var(--brand-700);
    }

    .stDownloadButton > button {
        background: var(--accent);
        color: white; border: 0; border-radius: 12px;
        font-weight: 600;
        box-shadow: 0 4px 14px -4px rgba(31, 157, 85, 0.4);
    }
    .stDownloadButton > button:hover {
        background: #157f43;
        transform: translateY(-1px);
    }

    /* ----- Tabs ----- */
    div[data-baseweb="tab-list"] {
        background: white !important;
        border-radius: 18px !important;
        padding: 0.5rem !important;
        border: 1px solid var(--slate-200) !important;
        gap: 0.45rem !important;
        box-shadow: var(--shadow-sm);
        margin-bottom: 1.4rem;
        flex-wrap: wrap;
        display: flex;
    }

    div[data-baseweb="tab"] {
        border-radius: 12px !important;
        padding: 0.65rem 1.25rem !important;
        font-weight: 600 !important;
        color: var(--slate-600) !important;
        background: var(--slate-50) !important;
        border: 1px solid var(--slate-200) !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
        white-space: nowrap;
        min-height: 42px;
        display: inline-flex !important;
        align-items: center !important;
    }

    div[data-baseweb="tab"]:hover {
        background: var(--brand-50) !important;
        color: var(--brand-700) !important;
        border-color: var(--brand-300) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(124, 58, 237, 0.10);
    }

    div[data-baseweb="tab"][aria-selected="true"] {
        background: var(--ink) !important;
        color: white !important;
        border-color: transparent !important;
        box-shadow: 0 6px 18px -4px rgba(26, 21, 53, 0.35) !important;
        transform: translateY(-1px);
    }

    div[data-baseweb="tab"][aria-selected="true"]:hover {
        filter: brightness(1.06);
    }

    div[data-baseweb="tab"] [data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        font-size: 0.92rem !important;
        line-height: 1 !important;
        color: inherit !important;
    }

    /* Cacher la barre d'highlight par défaut de BaseWeb */
    div[data-baseweb="tab-highlight"] {
        display: none !important;
    }
    div[data-baseweb="tab-border"] {
        display: none !important;
    }

    /* ----- Inputs ----- */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        border-radius: 10px !important;
        border: 1px solid var(--slate-200) !important;
        transition: all 0.15s;
    }
    .stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
        border-color: var(--brand-500) !important;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.12) !important;
    }
    div[data-baseweb="select"] > div {
        border-radius: 10px !important;
        border-color: var(--slate-200) !important;
    }

    /* ----- Cards (st.container border=True) — sélecteurs très spécifiques ----- */
    /* Force le fond BLANC sur le bordered container et tous ses enfants directs */
    section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stVerticalBlockBorderWrapper"],
    .st-emotion-cache-wpz2dm,
    [class*="st-emotion-cache-wpz2dm"] {
        background: #FFFFFF !important;
        background-color: #FFFFFF !important;
        background-image: none !important;
        border: 1px solid var(--line) !important;
        border-radius: 22px !important;
        padding: 1.6rem 1.8rem !important;
        box-shadow: var(--shadow-md) !important;
    }
    /* Les divs internes du container doivent être transparents pour que le blanc s'affiche */
    div[data-testid="stVerticalBlockBorderWrapper"] > div,
    div[data-testid="stVerticalBlockBorderWrapper"] > div > div,
    div[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlock"] {
        background: transparent !important;
        background-color: transparent !important;
    }

    /* Param cards (nichées dans des stColumn) : fond violet pâle pour différenciation */
    section[data-testid="stMain"] [data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stColumn"] .st-emotion-cache-wpz2dm,
    [data-testid="stColumn"] [class*="st-emotion-cache-wpz2dm"] {
        background: var(--bg) !important;
        background-color: var(--bg) !important;
        border-radius: 12px !important;
        padding: 0.9rem 1rem !important;
        box-shadow: none !important;
        border: 1px solid var(--line) !important;
    }

    /* Champs (text input, multiselect, textarea, slider) : fond violet pâle = ancien bg */
    section[data-testid="stMain"] .stTextInput input,
    section[data-testid="stMain"] .stTextArea textarea,
    section[data-testid="stMain"] .stNumberInput input {
        background: var(--bg-alt) !important;
        background-color: var(--bg-alt) !important;
        border: 1px solid var(--line) !important;
        border-radius: 10px !important;
    }
    section[data-testid="stMain"] div[data-baseweb="select"] > div:first-child {
        background: var(--bg-alt) !important;
        background-color: var(--bg-alt) !important;
        border: 1px solid var(--line) !important;
        border-radius: 10px !important;
    }
    section[data-testid="stMain"] div[data-baseweb="select"] > div:first-child:hover {
        border-color: var(--brand-400) !important;
    }
    section[data-testid="stMain"] .stTextInput input:focus,
    section[data-testid="stMain"] .stTextArea textarea:focus {
        border-color: var(--brand-500) !important;
        background: white !important;
        background-color: white !important;
        box-shadow: 0 0 0 3px var(--brand-100) !important;
    }

    /* ----- Panel de progression (style template Oui Allo) ----- */
    .progress-panel {
        background: var(--ink);
        color: white;
        border-radius: 24px;
        padding: 1.6rem 1.85rem;
        margin: 1rem 0 1.5rem 0;
        position: relative;
        overflow: hidden;
        box-shadow: var(--shadow-md);
    }
    .progress-panel::before {
        content: '';
        position: absolute;
        top: -50%; right: -10%;
        width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(107, 95, 255, 0.25) 0%, transparent 60%);
        pointer-events: none;
    }
    .pp-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1.3rem;
        position: relative;
    }
    .pp-title-wrap {
        display: flex; align-items: center; gap: 14px;
    }
    .pp-pulse {
        width: 10px; height: 10px;
        border-radius: 50%;
        background: #6EE7B7;
        box-shadow: 0 0 0 0 rgba(110, 231, 183, 0.7);
        animation: oa-pulse 1.6s infinite;
        flex-shrink: 0;
    }
    @keyframes oa-pulse {
        0% { box-shadow: 0 0 0 0 rgba(110, 231, 183, 0.7); }
        70% { box-shadow: 0 0 0 12px rgba(110, 231, 183, 0); }
        100% { box-shadow: 0 0 0 0 rgba(110, 231, 183, 0); }
    }
    .pp-title h3 {
        font-family: var(--font-display);
        font-size: 1.45rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: white;
        margin: 0;
    }
    .pp-meta {
        font-size: 0.82rem;
        color: rgba(255,255,255,0.65);
        margin-top: 2px;
    }
    .pp-stats {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.5rem;
        margin-bottom: 1.3rem;
        position: relative;
    }
    .pp-label {
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(255,255,255,0.5);
        font-weight: 600;
        margin-bottom: 6px;
    }
    .pp-value {
        font-family: var(--font-display);
        font-size: 1.95rem;
        font-weight: 600;
        letter-spacing: -0.02em;
        line-height: 1;
        color: white;
    }
    .pp-sm {
        font-size: 0.82rem;
        font-weight: 500;
        color: rgba(255,255,255,0.55);
        margin-left: 4px;
        font-family: var(--font-body);
        letter-spacing: 0;
    }
    .pp-bar {
        height: 6px;
        background: rgba(255,255,255,0.1);
        border-radius: 999px;
        overflow: hidden;
        margin-bottom: 0.85rem;
        position: relative;
    }
    .pp-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #6B5FFF 0%, #8B7FFF 100%);
        border-radius: 999px;
        position: relative;
        transition: width 0.4s ease;
    }
    .pp-bar-fill::after {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%);
        animation: oa-shimmer 1.8s infinite;
    }
    @keyframes oa-shimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    .pp-log {
        font-size: 0.76rem;
        color: rgba(255,255,255,0.55);
        font-family: 'SF Mono', Monaco, monospace;
        position: relative;
        line-height: 1.5;
    }
    .pp-log .check { color: #6EE7B7; }
    .pp-log .arrow { color: rgba(255,255,255,0.8); }

    /* ----- Dataframes ----- */
    .stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid var(--slate-200); }

    /* ----- Form card (Oui Allo) ----- */
    .form-card-anchor {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 1.8rem;
        box-shadow: var(--shadow-md);
        margin-bottom: 1.8rem;
    }
    .form-card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1.3rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid var(--line);
    }
    .form-card-title {
        font-family: var(--font-display);
        font-size: 1.4rem;
        font-weight: 600;
        color: var(--ink);
        letter-spacing: -0.01em;
        margin: 0;
    }
    .form-card-subtitle {
        color: var(--ink-mute);
        font-size: 0.82rem;
        margin-top: 2px;
    }

    /* Param cards (3 colonnes) */
    .param-card {
        background: var(--bg);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 1rem 1.1rem;
    }
    .param-card h4 {
        font-family: var(--font-body) !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        color: var(--ink);
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.005em;
    }

    /* Multiselect tags violets */
    [data-baseweb="select"] [data-baseweb="tag"] {
        background: var(--brand-600) !important;
        color: white !important;
        border-radius: 999px !important;
        font-weight: 500;
    }
    [data-baseweb="select"] [data-baseweb="tag"] span,
    [data-baseweb="select"] [data-baseweb="tag"] svg {
        color: white !important;
        fill: white !important;
    }

    /* Segmented control / radio horizontal */
    div[data-baseweb="radio"] > div[role="radiogroup"] {
        display: inline-flex;
        background: var(--bg-alt);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 4px;
        gap: 2px;
    }
    div[data-baseweb="radio"] label {
        background: transparent;
        padding: 7px 14px !important;
        border-radius: 8px;
        font-size: 0.85rem !important;
        color: var(--ink-mute) !important;
        cursor: pointer;
        margin: 0 !important;
        transition: all 0.15s;
    }
    div[data-baseweb="radio"] label:has(input:checked) {
        background: white;
        color: var(--ink) !important;
        font-weight: 600;
        box-shadow: 0 1px 3px rgba(26,21,53,0.08), 0 0 0 1px var(--line);
    }
    /* st.segmented_control (Streamlit 1.36+) */
    div[data-testid="stSegmentedControl"] {
        background: var(--bg-alt);
        border: 1px solid var(--line);
        border-radius: 12px;
        padding: 4px;
    }
    div[data-testid="stSegmentedControl"] button {
        background: transparent !important;
        color: var(--ink-mute) !important;
        border: 0 !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    div[data-testid="stSegmentedControl"] button[aria-checked="true"] {
        background: white !important;
        color: var(--ink) !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 3px rgba(26,21,53,0.08) !important;
    }

    /* Estimate block */
    .estimate-num {
        font-family: var(--font-display);
        font-size: 1.8rem;
        font-weight: 600;
        color: var(--ink);
        line-height: 1;
        letter-spacing: -0.01em;
    }
    .estimate-label {
        font-size: 0.78rem;
        color: var(--ink-mute);
        margin-top: 2px;
    }

    /* ----- Empty state ----- */
    .empty-state {
        text-align: center; padding: 3.5rem 1rem;
        background: white;
        border: 1px dashed var(--brand-200);
        border-radius: 20px;
        color: var(--slate-500);
        box-shadow: var(--shadow-sm);
    }
    .empty-state .icon { font-size: 3.2rem; margin-bottom: 0.5rem; }
    .empty-state h3 { color: var(--slate-800); margin: 0.5rem 0; font-weight: 700; }

    /* "How it works" steps cards in empty state */
    .steps-grid {
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 1rem; margin-top: 2rem;
    }
    @media (max-width: 768px) { .steps-grid { grid-template-columns: 1fr; } }
    .step-card {
        background: white; padding: 1.4rem 1.2rem;
        border-radius: 16px; border: 1px solid var(--slate-200);
        text-align: left; box-shadow: var(--shadow-sm);
        transition: all 0.2s;
    }
    .step-card:hover { box-shadow: var(--shadow-md); transform: translateY(-3px); border-color: var(--brand-200); }
    .step-card .step-num {
        width: 36px; height: 36px;
        background: linear-gradient(135deg, #6d28d9, #8b5cf6);
        color: white; border-radius: 999px;
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 1rem;
        box-shadow: 0 6px 14px rgba(124, 58, 237, 0.28);
        margin-bottom: 0.8rem;
    }
    .step-card h4 { font-size: 1rem; margin: 0 0 0.35rem 0; color: var(--slate-900); }
    .step-card p { color: var(--slate-600); font-size: 0.88rem; line-height: 1.5; margin: 0; }

    /* ----- Toast styling ----- */
    [data-testid="stToast"] {
        border-radius: 12px !important;
        box-shadow: var(--shadow-lg) !important;
    }

    /* ----- Status box ----- */
    [data-testid="stStatusWidget"] details {
        background: white; border: 1px solid var(--slate-200);
        border-radius: 14px; box-shadow: var(--shadow-sm);
    }

    /* Retire le padding sur les conteneurs internes Streamlit qui ajoutent un gap parasite */
    .st-emotion-cache-31q013,
    .st-emotion-cache-153zoqf,
    [class*="st-emotion-cache-31q013"],
    [class*="st-emotion-cache-153zoqf"] {
        padding: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }

    /* ----- Hide Streamlit chrome ----- */
    #MainMenu, footer, [data-testid="stToolbar"], .stDeployButton {
        display: none !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: auto !important;
    }

    /* ----- Sidebar entièrement masquée (template Oui Allo : topbar à la place) ----- */
    section[data-testid="stSidebar"],
    [data-testid="stSidebar"],
    [data-testid="stSidebarHeader"],
    [data-testid="stLogoSpacer"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: none !important;
        width: 0 !important;
        min-width: 0 !important;
    }
    /* Le main prend toute la largeur */
    section[data-testid="stMain"] {
        margin-left: 0 !important;
    }

    /* ----- TOPBAR (style template Oui Allo) ----- */
    .topbar {
        background: var(--surface);
        border-bottom: 1px solid var(--line);
        padding: 14px 32px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin: -1.4rem -2.4rem 2rem -2.4rem;  /* compense le padding du main */
        position: sticky;
        top: 0;
        z-index: 50;
    }
    .topbar-brand {
        display: flex; align-items: center; gap: 14px;
    }
    .topbar-brand img {
        height: 36px; width: auto; display: block;
        mix-blend-mode: multiply;
    }
    .topbar-sub {
        color: var(--ink-mute);
        font-size: 0.82rem;
        font-weight: 500;
        padding-left: 14px;
        border-left: 1px solid var(--line-strong);
        letter-spacing: 0.01em;
    }
    .topbar-right {
        display: flex; align-items: center; gap: 14px;
    }
    .topbar-quota {
        display: flex; align-items: center; gap: 8px;
        font-size: 0.82rem;
        color: var(--ink-soft);
        padding: 6px 14px;
        background: var(--brand-50);
        border-radius: 999px;
    }
    .topbar-quota-dot {
        width: 6px; height: 6px; border-radius: 50%;
        background: var(--accent);
    }
    .topbar-quota strong { color: var(--ink); font-weight: 600; }

    /* ----- Table prospects (style template, HTML custom) ----- */
    .ouiallo-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
        background: var(--surface);
    }
    .ouiallo-table thead th {
        background: var(--surface);
        text-align: left;
        padding: 12px 16px;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ink-mute);
        border-bottom: 1px solid var(--line);
        white-space: nowrap;
    }
    .ouiallo-table thead th:first-child { padding-left: 24px; }
    .ouiallo-table thead th:last-child { padding-right: 24px; }
    .ouiallo-table tbody td {
        padding: 14px 16px;
        border-bottom: 1px solid var(--line);
        vertical-align: middle;
    }
    .ouiallo-table tbody td:first-child { padding-left: 24px; }
    .ouiallo-table tbody td:last-child { padding-right: 24px; }
    .ouiallo-table tbody tr { transition: background 0.1s ease; }
    .ouiallo-table tbody tr:hover { background: var(--brand-50); }
    .ouiallo-table tbody tr:last-child td { border-bottom: none; }

    .oa-cell-name {
        font-weight: 600;
        color: var(--ink);
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .oa-cell-name-meta {
        font-size: 0.7rem;
        color: var(--ink-mute);
        font-weight: 400;
        margin-top: 2px;
    }
    .oa-avatar {
        width: 32px; height: 32px;
        border-radius: 8px;
        background: var(--brand-100);
        color: var(--brand-700);
        display: grid; place-items: center;
        font-weight: 600;
        font-size: 0.78rem;
        flex-shrink: 0;
        font-family: var(--font-display);
    }
    .oa-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        white-space: nowrap;          /* empêche "TVA manquante" de passer à la ligne */
        line-height: 1;
    }
    .oa-badge-success { background: var(--accent-soft); color: #0F6B36; }
    .oa-badge-warn    { background: var(--warn-soft); color: var(--warn); }
    .oa-badge-neutral { background: var(--bg-alt); color: var(--ink-soft); }
    .oa-badge-primary { background: var(--brand-100); color: var(--brand-700); }
    .oa-cell-phone {
        font-variant-numeric: tabular-nums;
        color: var(--ink);
        font-weight: 500;
    }
    .oa-cell-vat {
        font-variant-numeric: tabular-nums;
        color: var(--ink-soft);
        font-family: 'SF Mono', Monaco, monospace;
        font-size: 0.74rem;
    }
    .oa-cell-link {
        color: var(--brand-700);
        text-decoration: none;
        font-weight: 500;
    }
    .oa-cell-link:hover { text-decoration: underline; }
    .oa-score {
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .oa-score-bar {
        display: inline-block;            /* obligatoire pour qu'un <span> respecte width */
        width: 60px;
        height: 5px;
        border-radius: 3px;
        background: var(--line);
        overflow: hidden;
        vertical-align: middle;
    }
    .oa-score-bar-fill {
        display: block;                    /* le fill prend sa width depuis l'inline-block parent */
        height: 100%;
        border-radius: 3px;
        transition: width 0.3s ease;
    }
    .oa-score-text {
        display: inline-block;
        font-size: 0.78rem;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        min-width: 22px;
        text-align: right;
        vertical-align: middle;
    }

    /* Card wrapper pour la table */
    .oa-results-card {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 24px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
    }
    .oa-results-head {
        padding: 1.4rem 1.6rem 1rem 1.6rem;
        border-bottom: 1px solid var(--line);
    }
    .oa-results-title {
        font-family: var(--font-display);
        font-size: 1.4rem;
        font-weight: 600;
        color: var(--ink);
        letter-spacing: -0.01em;
        margin: 0;
    }
    .oa-results-title em {
        font-style: italic;
        color: var(--brand-700);
    }
    .oa-results-summary {
        font-size: 0.82rem;
        color: var(--ink-mute);
        margin-top: 4px;
    }
    .oa-filters-bar {
        padding: 0.9rem 1.6rem;
        background: var(--bg-alt);
        border-bottom: 1px solid var(--line);
    }
    .oa-table-foot {
        padding: 1rem 1.6rem;
        background: var(--surface);
        border-top: 1px solid var(--line);
        font-size: 0.82rem;
        color: var(--ink-mute);
    }

    /* ----- Logo Oui Allo dans la sidebar ----- */
    .sidebar-logo {
        display: flex;
        justify-content: center;
        padding: 0.4rem 0 1rem 0;
        margin-bottom: 0.6rem;
        border-bottom: 1px solid var(--slate-200);
    }
    .sidebar-logo + div [data-testid="stImage"] img {
        max-width: 200px !important;
        height: auto !important;
    }
    [data-testid="stSidebar"] [data-testid="stImage"] {
        display: flex;
        justify-content: center;
    }
    [data-testid="stSidebar"] [data-testid="stImage"] img {
        max-width: 200px;
        height: auto;
    }
</style>
"""

st.markdown(TAILWIND_CDN + CUSTOM_CSS, unsafe_allow_html=True)


DISPLAY_COLUMNS = [
    "Rang Google", "Nom", "Catégorie", "Localité", "Téléphone", "Email pro",
    "Dirigeant(s)", "Numéro TVA", "Numéro BCE", "Date de création",
    "Note Google", "Site web", "Comptes annuels (BNB)", "Fiche CompanyWeb",
    "Lien Google Maps", "Déjà vue",
]


STATUS_STYLES = {
    "À appeler":         ("#6d28d9", "#ede9fe", "circle-dot"),
    "Déjà appelé":       ("#047857", "#d1fae5", "check-circle"),
    "À rappeler":        ("#b45309", "#fef3c7", "clock"),
    "Ne plus rappeler":  ("#b91c1c", "#fee2e2", "ban"),
}


def _status_chip_html(status: str) -> str:
    fg, bg, icon_name = STATUS_STYLES.get(status, ("#475569", "#f1f5f9", "circle-dot"))
    label = status or "À appeler"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:{bg};color:{fg};padding:3px 10px;'
        f'border-radius:999px;font-size:0.75rem;font-weight:600;letter-spacing:0.01em;">'
        f'{lucide(icon_name, 12, fg, 2.2)}<span>{label}</span></span>'
    )


def _rank_badge_html(rank) -> str:
    if rank == 1:
        return ('<span style="display:inline-flex;align-items:center;gap:5px;'
                'background:linear-gradient(135deg,#fbbf24,#f59e0b);'
                'color:white;padding:3px 11px;border-radius:8px;font-weight:700;'
                'font-size:0.78rem;box-shadow:0 2px 6px rgba(245,158,11,0.35);">'
                + lucide("trophy", 12, "white", 2.4) + '<span>N°1</span></span>')
    if rank == 2:
        return ('<span style="display:inline-flex;align-items:center;gap:5px;'
                'background:linear-gradient(135deg,#cbd5e1,#94a3b8);'
                'color:white;padding:3px 11px;border-radius:8px;font-weight:700;'
                'font-size:0.78rem;box-shadow:0 2px 6px rgba(148,163,184,0.35);">'
                + lucide("medal", 12, "white", 2.4) + '<span>N°2</span></span>')
    if rank:
        return (f'<span style="background:#e2e8f0;color:#475569;padding:3px 10px;'
                f'border-radius:8px;font-weight:600;font-size:0.78rem;">N°{rank}</span>')
    return ""


def _as_dict(b) -> dict:
    """Accepte Business ou dict et renvoie un dict avec toutes les clés utiles."""
    if isinstance(b, dict):
        return b
    d = b.to_dict()
    try:
        from storage import dedup_key as _dk
        d["dedup_key"] = _dk(b)
    except Exception:
        d["dedup_key"] = None
    return d


def _render_ai_briefing_section(biz: dict) -> None:
    """Affiche/génère le briefing IA pré-appel pour la fiche en cours."""
    dedup = biz.get("dedup_key")
    cached = get_briefing(dedup) if dedup else None
    BRAND = "#7c3aed"

    def _render_briefing_card(b: dict, generated_at: str = None):
        opps = "".join(
            f"<li style='margin:0.2rem 0;'>{_safe_html(o)}</li>"
            for o in (b.get("opportunities") or [])[:5]
        )
        tps = "".join(
            f"<li style='margin:0.2rem 0;'>{_safe_html(t)}</li>"
            for t in (b.get("talking_points") or [])[:5]
        )
        synthesis = _safe_html(b.get("synthesis") or "")
        opener = _safe_html(b.get("opener") or "")
        ts_html = (f"<div style='font-size:0.72rem;color:#94a3b8;margin-top:0.5rem;'>"
                   f"Généré le {generated_at}</div>" if generated_at else "")

        # HTML compacte sans indentation pour que Streamlit ne l'interprète pas comme un bloc de code Markdown
        html = (
            f'<div style="background:linear-gradient(135deg,#ede9fe 0%,#f5f3ff 100%);'
            f'border:1px solid #ddd6fe;border-radius:14px;padding:1.05rem 1.2rem;'
            f'margin:0.8rem 0 1rem 0;box-shadow:0 4px 12px rgba(124,58,237,0.08);">'
            f'<div style="display:flex;align-items:center;gap:7px;font-weight:700;'
            f'color:{BRAND};font-size:0.82rem;text-transform:uppercase;'
            f'letter-spacing:0.05em;margin-bottom:0.55rem;">'
            f'{lucide("zap", 15, BRAND, 2.4)}<span>Briefing IA pré-appel</span></div>'
            f'<div style="color:#1e293b;font-size:0.95rem;font-weight:600;'
            f'margin-bottom:0.7rem;line-height:1.5;">{synthesis}</div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;'
            f'margin-bottom:0.7rem;">'
            f'<div><div style="font-weight:700;color:#6d28d9;font-size:0.75rem;'
            f'text-transform:uppercase;letter-spacing:0.03em;margin-bottom:0.3rem;">'
            f'Opportunités identifiées</div>'
            f'<ul style="font-size:0.85rem;color:#334155;padding-left:1.15rem;'
            f'margin:0;line-height:1.45;">{opps}</ul></div>'
            f'<div><div style="font-weight:700;color:#6d28d9;font-size:0.75rem;'
            f'text-transform:uppercase;letter-spacing:0.03em;margin-bottom:0.3rem;">'
            f'Accroches commerciales</div>'
            f'<ul style="font-size:0.85rem;color:#334155;padding-left:1.15rem;'
            f'margin:0;line-height:1.45;">{tps}</ul></div></div>'
            f'<div style="background:white;border-left:3px solid {BRAND};'
            f'padding:0.55rem 0.8rem;border-radius:6px;font-style:italic;'
            f'color:#1e293b;font-size:0.9rem;line-height:1.5;">« {opener} »</div>'
            f'{ts_html}</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    if not ai_is_configured():
        st.info(
            "Configure `OPENAI_API_KEY` ou `ANTHROPIC_API_KEY` dans `.env` pour activer "
            "le briefing IA pré-appel.",
            icon=":material/info:",
        )
        return

    # Placeholder mis à jour en place — évite st.rerun() qui ferme le modal
    briefing_slot = st.empty()
    if cached:
        with briefing_slot.container():
            _render_briefing_card(cached, cached.get("_generated_at"))

    col_a, col_b = st.columns([3, 1])
    with col_a:
        if not cached:
            st.caption(f"Provider IA : {ai_provider_label()}")
    with col_b:
        button_label = "Régénérer" if cached else "Générer le briefing"
        button_type = "secondary" if cached else "primary"
        if st.button(button_label, key=f"gen_{dedup}",
                     type=button_type, width="stretch"):
            with st.spinner("Génération du briefing IA… (~5 s)"):
                res = generate_briefing(biz)
            if res["ok"]:
                save_briefing(dedup, res["briefing"])
                fresh = dict(res["briefing"])
                fresh["_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                # Remplace le contenu du placeholder sans fermer le modal
                with briefing_slot.container():
                    _render_briefing_card(fresh, fresh["_generated_at"])
            else:
                st.error(res["message"])


def _safe_html(s) -> str:
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _emit_html(html_string: str) -> None:
    """Émet du HTML brut SANS sanitization.

    Utilisé pour la fiche détail premium (rendue dans @st.dialog) où
    st.markdown sanitize parfois agressivement (notamment les classes
    CSS personnalisées dans certains contextes modaux), cassant les
    styles `.bd-*`. st.html (Streamlit 1.33+) passe le HTML tel quel
    sans aucune transformation.
    """
    try:
        st.html(html_string)
    except AttributeError:
        # Fallback pour Streamlit < 1.33
        st.markdown(html_string, unsafe_allow_html=True)


def _score_color(score: int) -> tuple[str, str]:
    """Renvoie (couleur principale, couleur de fond) selon le score."""
    if score >= 80:
        return ("#059669", "#d1fae5")
    if score >= 60:
        return ("#b45309", "#fef3c7")
    return ("#b91c1c", "#fee2e2")


def _severity_icon_html(severity: str) -> str:
    """Petite icône SVG colorée selon la sévérité."""
    if severity == "ok":
        return lucide("check-circle", 14, "#059669", 2.2)
    if severity == "warning":
        return lucide("alert-triangle", 14, "#d97706", 2.2)
    return lucide("x", 14, "#dc2626", 2.5)


def _render_findings_list(findings: list[dict]) -> str:
    rows = []
    for f in findings:
        icon = _severity_icon_html(f["severity"])
        title = _safe_html(f.get("title") or "")
        detail = _safe_html(f.get("detail") or "")
        reco = _safe_html(f.get("recommendation") or "")
        detail_html = (f'<div style="font-size:0.78rem;color:#64748b;'
                       f'margin-top:0.15rem;line-height:1.4;">{detail}</div>'
                       if detail else "")
        reco_html = (f'<div style="font-size:0.76rem;color:#7c3aed;'
                     f'margin-top:0.15rem;font-style:italic;line-height:1.4;">'
                     f'→ {reco}</div>' if reco else "")
        rows.append(
            f'<li style="margin:0.45rem 0;padding-left:0.25rem;'
            f'list-style:none;display:flex;gap:7px;align-items:flex-start;">'
            f'<span style="flex-shrink:0;margin-top:2px;">{icon}</span>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-size:0.84rem;font-weight:600;color:#1e293b;">{title}</div>'
            f'{detail_html}{reco_html}'
            f'</div></li>'
        )
    return f'<ul style="padding:0;margin:0;">{"".join(rows)}</ul>'


def _render_audit_subcard(label: str, score: int, findings: list[dict], icon_name: str) -> str:
    fg, bg = _score_color(score)
    findings_html = _render_findings_list(findings)
    return (
        f'<div style="background:white;border:1px solid #e2e8f0;border-radius:14px;'
        f'padding:1rem 1.1rem;box-shadow:0 1px 3px rgba(15,23,42,0.04);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:0.7rem;border-bottom:1px solid #f1f5f9;padding-bottom:0.55rem;">'
        f'<div style="display:flex;align-items:center;gap:6px;font-weight:700;'
        f'font-size:0.82rem;color:#0f172a;text-transform:uppercase;'
        f'letter-spacing:0.04em;">'
        f'{lucide(icon_name, 16, "#7c3aed", 2.2)}<span>{label}</span></div>'
        f'<div style="background:{bg};color:{fg};padding:3px 11px;'
        f'border-radius:999px;font-size:0.82rem;font-weight:800;">{score}/100</div>'
        f'</div>'
        f'{findings_html}'
        f'</div>'
    )


def _render_audit_card(audit: dict, generated_at: str = None) -> str:
    web = audit.get("website", {})
    gmb = audit.get("gmb", {})
    global_score = audit.get("global_score", 0)
    fg, bg = _score_color(global_score)
    ts_html = (f'<div style="font-size:0.72rem;color:#94a3b8;margin-top:0.6rem;'
               f'text-align:right;">Audit du {generated_at}</div>'
               if generated_at else "")

    web_card = _render_audit_subcard(
        "Site web", web.get("score", 0), web.get("findings", []), "globe",
    )
    gmb_card = _render_audit_subcard(
        "Google Business Profile", gmb.get("score", 0), gmb.get("findings", []), "map-pin",
    )

    return (
        f'<div style="background:linear-gradient(135deg,#fef3c7 0%,#fff7ed 100%);'
        f'border:1px solid #fed7aa;border-radius:14px;padding:1.05rem 1.2rem;'
        f'margin:0.8rem 0 1rem 0;box-shadow:0 4px 12px rgba(217,119,6,0.08);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:0.8rem;">'
        f'<div style="display:flex;align-items:center;gap:7px;font-weight:700;'
        f'color:#b45309;font-size:0.82rem;text-transform:uppercase;'
        f'letter-spacing:0.05em;">'
        f'{lucide("scan-line", 16, "#b45309", 2.4) if "scan-line" in LUCIDE_PATHS else lucide("search", 16, "#b45309", 2.4)}'
        f'<span>Audit SEO + Google Business</span></div>'
        f'<div style="background:{bg};color:{fg};padding:5px 14px;'
        f'border-radius:999px;font-size:0.95rem;font-weight:800;">'
        f'Score global {global_score}/100</div>'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0.85rem;">'
        f'{web_card}{gmb_card}'
        f'</div>'
        f'{ts_html}'
        f'</div>'
    )


def _render_seo_audit_section(biz: dict) -> None:
    """Affiche/lance l'audit SEO complet (site web + GMB)."""
    dedup = biz.get("dedup_key")
    cached = get_seo_audit(dedup) if dedup else None

    audit_slot = st.empty()
    if cached:
        with audit_slot.container():
            st.markdown(_render_audit_card(cached, cached.get("_generated_at")),
                        unsafe_allow_html=True)

    col_a, col_b = st.columns([3, 1])
    with col_b:
        button_label = "Régénérer l'audit" if cached else "Lancer l'audit SEO"
        button_type = "secondary" if cached else "primary"
        if st.button(button_label, key=f"audit_{dedup}",
                     type=button_type, width="stretch"):
            with st.spinner("Audit SEO + Google Business en cours… (~3 s)"):
                res = run_full_audit(biz)
            save_seo_audit(dedup, res)
            res["_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            with audit_slot.container():
                st.markdown(_render_audit_card(res, res["_generated_at"]),
                            unsafe_allow_html=True)


def _render_audit_seo_block(biz: dict, safe_key: str) -> None:
    """Bloc audit SEO sous l'iframe : bouton stylé + résultats inline en dessous.

    Layout : un bouton « Lancer l'audit SEO du site » indigo-900 (style
    audit-cta de la maquette) suivi des résultats juste en dessous quand
    l'audit est généré ou en cache.
    """
    dedup = biz.get("dedup_key")
    cached = get_seo_audit(dedup) if dedup else None

    # Header de section pour une présentation claire et organisée
    st.markdown(
        '<div style="margin-top: 0.8rem; margin-bottom: 0.8rem; '
        'padding: 0 0.2rem; display: flex; align-items: center; gap: 8px;">'
        '<div style="width: 6px; height: 6px; border-radius: 999px; '
        'background: #E8A838; box-shadow: 0 0 0 3px rgba(232, 168, 56, 0.25);"></div>'
        '<div style="font-size: 0.78rem; font-weight: 700; '
        'letter-spacing: 0.08em; text-transform: uppercase; '
        'color: #3425AF;">Audit SEO du site web</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Bouton stylé qui matche l'audit-cta de la maquette (indigo-900 + dot or).
    # Scopé via st.container(key="bd-audit-cta") pour la CSS ciblée
    # (.st-key-bd-audit-cta dans _BUSINESS_DETAIL_CSS).
    with st.container(key="bd-audit-cta"):
        button_label = ("Régénérer l'audit SEO" if cached
                        else "Lancer l'audit SEO du site")
        if st.button(button_label, key=f"bd_run_audit_{safe_key}",
                     width="stretch", type="primary"):
            with st.spinner("Audit SEO + Google Business en cours… (~3 s)"):
                res = run_full_audit(biz)
            save_seo_audit(dedup, res)
            res["_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            cached = res  # Affichage immédiat
            st.rerun()  # Rafraîchit pour montrer les résultats en bas

    # Affichage des résultats juste sous le bouton (organisé, cohérent).
    if cached:
        st.markdown(
            _render_audit_card(cached, cached.get("_generated_at")),
            unsafe_allow_html=True,
        )


@st.dialog("Détails de l'entreprise", width="large")
def show_business_details(biz: dict) -> None:
    """Vue détaillée premium d'une fiche prospect (design Oui Allo).

    ARCHITECTURE NOUVELLE — RENDU EN IFRAME :
    Après plusieurs tentatives infructueuses d'injecter le CSS dans le
    portal @st.dialog (Streamlit/BaseWeb a des styles avec une spécificité
    trop élevée qui écrasaient même mes !important), on bascule sur
    `st.components.v1.html()` qui rend le HTML dans un iframe isolé.
    L'iframe = document totalement séparé → aucune interférence Streamlit,
    le design matche pixel-perfect la maquette fiche-entreprise.html.

    Trade-off : les boutons interactifs (Appeler, changer Statut, lancer
    l'audit SEO) doivent rester en widgets Streamlit natifs AU-DESSUS de
    l'iframe (un clic dans un iframe ne peut pas appeler du code Python).
    Les interactions internes à la fiche (changer d'onglet, ouvrir un
    accordéon) sont gérées par vanilla JS embarqué dans l'iframe.
    """
    from streamlit.components.v1 import html as _components_html

    safe_key = (biz.get("dedup_key") or "_no").replace(":", "_").replace("|", "_")
    phone = biz.get("phone")
    status = biz.get("call_status") or "À appeler"
    website = biz.get("website")

    # ─────────────── ACTION ROW NATIVE (au-dessus de l'iframe) ───────────────
    # Deux actions principales : Appeler (Ringover) + Changer statut.
    # L'audit SEO est rendu DESSOUS l'iframe (voir plus bas) pour que les
    # résultats apparaissent juste après le bouton, comme demandé.
    a1, a2 = st.columns([1, 2])
    with a1:
        disabled = not phone or not is_configured()
        if st.button(
            ":material/call: Appeler maintenant",
            key=f"bd_call_{safe_key}", type="primary", width="stretch",
            disabled=disabled,
            help=("Click-to-call Ringover" if not disabled else
                  ("Pas de numéro" if not phone else "RINGOVER_API_KEY manquante")),
        ):
            res = click_to_call(phone)
            st.toast(res['message'],
                     icon=":material/call_made:" if res["ok"] else ":material/error:")

    with a2:
        status_key = f"bd_status_{safe_key}"
        if status_key not in st.session_state:
            st.session_state[status_key] = status

        def _on_status_change(_k=status_key, _d=biz.get("dedup_key")):
            new_val = st.session_state[_k]
            if _d and not _d.startswith("_no_"):
                update_call_fields(_d, call_status=new_val)
                st.toast(f"Statut : {new_val}", icon=":material/save:")

        st.selectbox(
            "Statut",
            CALL_STATUSES,
            index=CALL_STATUSES.index(status) if status in CALL_STATUSES else 0,
            key=status_key,
            on_change=_on_status_change,
            label_visibility="collapsed",
        )

    # ─────────────── AUDIT SEO : trigger Streamlit caché ─────────────────
    # Le bouton VISIBLE est dans l'iframe (sous l'URL du site). Son onclick
    # JS accède au DOM parent (iframe est same-origin via allow-same-origin)
    # et clique ce bouton Streamlit caché, qui déclenche l'audit côté Python.
    # CSS hide via .st-key-bd-hidden-audit-run (cf. _BUSINESS_DETAIL_CSS).
    dedup = biz.get("dedup_key")
    cached_audit = get_seo_audit(dedup) if dedup and website else None
    if website:
        with st.container(key="bd-hidden-audit-run"):
            if st.button("RUN_AUDIT_INTERNAL",
                         key=f"bd_run_audit_hidden_{safe_key}"):
                with st.spinner("Audit SEO + Google Business en cours… (~3 s)"):
                    res = run_full_audit(biz)
                save_seo_audit(dedup, res)
                res["_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                cached_audit = res  # reflet immédiat sans attendre rerun
                st.rerun()

    # ─────────────── FICHE VISUELLE EN IFRAME (pixel-perfect maquette) ───────
    visual_html = _build_detail_visual_html(biz, cached_audit=cached_audit)
    # Hauteur fixée : l'iframe ne peut pas auto-fit son contenu. 1500px
    # couvre toutes les fiches (action bar + score + contact + dirigeants
    # + 3 onglets full content). scrolling=True au cas où.
    _components_html(visual_html, height=1500, scrolling=True)


# ===========================================================================
# BUILDER DU HTML IFRAME — fiche détail visuelle pixel-perfect
# ===========================================================================
# Génère un document HTML standalone qui réplique exactement la maquette
# fiche-entreprise.html, avec les données de l'entreprise substituées.
# Rendu via st.components.v1.html() dans un iframe isolé → zéro interférence
# avec le CSS de Streamlit/BaseWeb.

def _build_audit_summary_compact_html(audit: dict) -> str:
    """Affichage compact de l'audit SEO pour la sidebar iframe.

    Volontairement minimal (le user veut peu d'infos, prompt détaillé à venir) :
    - Score global en pill colorée
    - Sub-scores web + gmb sur une ligne
    - Date de génération en très petit
    """
    global_score = audit.get("global_score", 0) or 0
    web_score = (audit.get("web") or {}).get("score", 0) or 0
    gmb_score = (audit.get("gmb") or {}).get("score", 0) or 0
    ts = audit.get("_generated_at", "") or ""

    # Couleur du pill selon score
    if global_score >= 80:
        bg, fg = "#E6F7EE", "#0F9D58"   # vert
    elif global_score >= 60:
        bg, fg = "#FFF6E5", "#B5740A"   # ambre
    else:
        bg, fg = "#FDECEC", "#D33B3B"   # rouge

    return f'''
        <div style="margin-top: 12px; padding: 12px 14px; background: var(--cream); border-radius: 11px; border: 1px solid var(--ink-100);">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 8px;">
            <div style="font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-500);">Audit SEO</div>
            <div style="background: {bg}; color: {fg}; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;">{global_score}/100</div>
          </div>
          <div style="display: flex; gap: 14px; font-size: 11px; color: var(--ink-700);">
            <div><span style="color: var(--ink-400);">Web</span> <strong style="color: var(--ink-900);">{web_score}</strong></div>
            <div><span style="color: var(--ink-400);">GMB</span> <strong style="color: var(--ink-900);">{gmb_score}</strong></div>
          </div>
          {f'<div style="margin-top: 6px; font-size: 10px; color: var(--ink-400);">Généré le {_safe_html(ts)}</div>' if ts else ''}
        </div>'''


def _build_detail_visual_html(biz: dict, cached_audit: dict | None = None) -> str:
    """Construit le document HTML complet pour l'iframe de fiche détail.

    Args:
        biz: dict de l'entreprise
        cached_audit: audit SEO en cache à embedder dans la sidebar (sous l'URL),
                      None si pas encore généré
    """
    import re as _re
    from datetime import datetime as _dt

    # ─── Données de base ───
    name = _safe_html(biz.get("name") or "—")
    rank = biz.get("google_rank")
    status = biz.get("call_status") or "À appeler"
    legal_form = _safe_html(biz.get("legal_form") or "")
    category = _safe_html(biz.get("category") or "")
    city = _safe_html(biz.get("city") or biz.get("locality") or "")
    rating = biz.get("rating")
    reviews_count = biz.get("reviews_count") or 0
    phone = biz.get("phone") or ""
    email = biz.get("email") or ""
    website = biz.get("website") or ""
    address = biz.get("address") or ""
    postal = biz.get("postal_code") or ""
    locality = biz.get("locality") or biz.get("city") or ""

    # Ancienneté calculée
    cd = biz.get("creation_date") or ""
    age = None
    year_created = None
    m = _re.search(r"(\d{4})", str(cd))
    if m:
        year_created = int(m.group(1))
        age = max(0, _dt.now().year - year_created)

    # AI provider label
    try:
        ai_label = ai_provider_label()
    except Exception:
        ai_label = "non configuré"

    # ─── Subtitle ───
    sub_parts = [s for s in [legal_form, category, f"{city}, BE" if city else ""] if s]
    subtitle = " · ".join(sub_parts)

    # ─── Pulse dot couleur selon statut ───
    pulse_color = "var(--red-600)" if status == "À rappeler" else "var(--amber-700)"

    # ─── Rank badge ───
    rank_html = ""
    if rank:
        suffix = "er" if rank == 1 else "e"
        rank_html = f'''
        <div class="rank-badge">
          <svg viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
          Prospect N°{rank}{suffix}
        </div>'''

    # ─── Score panel ───
    score_html = ""
    if rating or age is not None:
        rating_block = ""
        if rating:
            try:
                rint = int(round(float(rating)))
                stars = "★" * rint + "☆" * (5 - rint)
            except (ValueError, TypeError):
                stars = ""
            rating_block = f'''
            <div class="score-block">
              <div class="score-block__label">Réputation Google</div>
              <div class="score-block__value">{_safe_html(rating)} <small>/5</small></div>
              <div class="stars">{stars}</div>
              <div class="reviews-count">{reviews_count} avis</div>
            </div>'''
        age_block = ""
        if age is not None:
            age_block = f'''
            <div class="score-block">
              <div class="score-block__label">Ancienneté</div>
              <div class="score-block__value">{age} <small>ans</small></div>
              <div class="reviews-count" style="margin-top: 16px;">depuis {year_created}</div>
            </div>'''
        if rating_block or age_block:
            score_html = f'<div class="score-panel">{rating_block}{age_block}</div>'

    # ─── Contact items ───
    arrow_svg = '<span class="contact-item__action"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg></span>'
    contact_items = []
    if phone:
        contact_items.append(f'''
        <a href="tel:{_safe_html(phone)}" class="contact-item">
          <span class="contact-item__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>
            </svg>
          </span>
          <div class="contact-item__main">
            <div class="contact-item__label">Téléphone</div>
            <div class="contact-item__value">{_safe_html(phone)}</div>
          </div>
          {arrow_svg}
        </a>''')
    if email:
        contact_items.append(f'''
        <a href="mailto:{_safe_html(email)}" class="contact-item">
          <span class="contact-item__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
              <polyline points="22,6 12,13 2,6"/>
            </svg>
          </span>
          <div class="contact-item__main">
            <div class="contact-item__label">Email</div>
            <div class="contact-item__value">{_safe_html(email)}</div>
          </div>
          {arrow_svg}
        </a>''')

    website_block = ""
    if website:
        url_display = website.replace("https://", "").replace("http://", "").rstrip("/")
        # ─── Bouton audit-cta : onclick clique le bouton Streamlit caché ───
        button_label = "Régénérer l'audit SEO" if cached_audit else "Lancer l'audit SEO du site"
        audit_button_html = f'''
          <button onclick="(function(){{var b=window.parent.document.querySelector('.st-key-bd-hidden-audit-run button');if(b){{b.click();}}else{{console.error('hidden audit btn not found');}}}})()" class="audit-cta" type="button">
            <span class="audit-cta__accent"></span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            {button_label}
          </button>'''

        # ─── Affichage compact de l'audit (sous le bouton, si cache) ───
        # Minimal volontairement : score pill global + 2 sub-scores web/gmb.
        # Le détail viendra avec le nouveau prompt utilisateur.
        audit_summary_html = ""
        if cached_audit:
            audit_summary_html = _build_audit_summary_compact_html(cached_audit)

        website_block = f'''
        <div class="website-block">
          <a href="{_safe_html(website)}" target="_blank" class="website-block__main">
            <span class="website-block__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="2" y1="12" x2="22" y2="12"/>
                <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/>
              </svg>
            </span>
            <div class="website-block__info">
              <div class="website-block__label">Site web</div>
              <div class="website-block__url">{_safe_html(url_display)}</div>
            </div>
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--ink-400);"><path d="M7 17L17 7M7 7h10v10"/></svg>
          </a>
          {audit_button_html}
          {audit_summary_html}
        </div>'''

    address_block = ""
    if address:
        full_addr = _safe_html(address)
        if postal and locality and postal not in str(address):
            full_addr = f"{_safe_html(address)}, {_safe_html(postal)} {_safe_html(locality)}"
        # Encode address for Google Maps URL
        gmaps_query = website.replace(' ', '+') if False else _safe_html(address).replace(' ', '+')
        address_block = f'''
        <a href="https://www.google.com/maps/search/?api=1&query={gmaps_query}" target="_blank" class="contact-item">
          <span class="contact-item__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
              <circle cx="12" cy="10" r="3"/>
            </svg>
          </span>
          <div class="contact-item__main">
            <div class="contact-item__label">Adresse</div>
            <div class="contact-item__value">{full_addr}</div>
          </div>
          {arrow_svg}
        </a>'''

    contact_list_html = (
        '<div class="contact-list">'
        + "".join(contact_items)
        + website_block
        + address_block
        + '</div>'
    )

    # ─── Dirigeants ───
    managers_str = (biz.get("managers") or "").strip()
    dirigeants_html = ""
    if managers_str:
        names = [n.strip() for n in _re.split(r"[,;\n]+", managers_str) if n.strip()]
        rows = []
        for full_name in names[:8]:
            parts = full_name.split()
            if len(parts) >= 2:
                initials = (parts[0][:1] + parts[-1][:1]).upper()
            else:
                initials = full_name[:2].upper()
            # LinkedIn search URL
            linkedin_query = _safe_html(full_name).replace(' ', '%20')
            rows.append(f'''
            <div class="admin-row">
              <div class="admin-avatar">{_safe_html(initials)}</div>
              <div class="admin-info">
                <div class="admin-name">{_safe_html(full_name)}</div>
                <div class="admin-role">Administrateur</div>
              </div>
              <a href="https://www.linkedin.com/search/results/people/?keywords={linkedin_query}" target="_blank" class="admin-action" title="Rechercher sur LinkedIn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="11" cy="11" r="8"/>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
              </a>
            </div>''')
        dirigeants_html = f'''
        <div class="card admins-card">
          <div class="admins-card__title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
            </svg>
            Dirigeants
          </div>
          {"".join(rows)}
        </div>'''

    # ─── Eval panel : Santé financière + Présence locale + Signaux ───
    BCE_STATUS = biz.get("bce_status") or "Actif"

    fin_rows = []
    if biz.get("establishments_count"):
        fin_rows.append((
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4"/></svg>',
            'Établissements actifs',
            str(biz["establishments_count"]),
        ))
    if biz.get("creation_date"):
        fin_rows.append((
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
            'Activité depuis',
            _safe_html(biz["creation_date"]),
        ))
    fin_rows.append((
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        'Statut BCE',
        f'<span class="status-pill" style="background: var(--green-50); color: var(--green-600);">{_safe_html(BCE_STATUS)}</span>',
    ))
    if biz.get("nbb_revenue"):
        fin_rows.append(('', "Chiffre d'affaires", _safe_html(biz["nbb_revenue"])))
    if biz.get("nbb_equity"):
        fin_rows.append(('', "Fonds propres", _safe_html(biz["nbb_equity"])))
    if biz.get("nbb_employees"):
        fin_rows.append(('', "Effectif", _safe_html(biz["nbb_employees"])))

    fin_rows_html = "".join(
        f'<div class="stat-row"><span class="stat-row__label">{icon}{label}</span><span class="stat-row__value">{value}</span></div>'
        for icon, label, value in fin_rows
    )

    fin_links = []
    if biz.get("nbb_url"):
        fin_links.append(f'''
        <a href="{_safe_html(biz["nbb_url"])}" target="_blank" class="ext-link">
          <span class="ext-link__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg></span>
          <div class="ext-link__main">
            <div class="ext-link__title">Comptes annuels BNB</div>
            <div class="ext-link__sub">Banque Nationale de Belgique</div>
          </div>
          <span class="ext-link__arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17L17 7M7 7h10v10"/></svg></span>
        </a>''')
    if biz.get("companyweb_url"):
        fin_links.append(f'''
        <a href="{_safe_html(biz["companyweb_url"])}" target="_blank" class="ext-link">
          <span class="ext-link__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path d="M20 8v6M23 11h-6"/></svg></span>
          <div class="ext-link__main">
            <div class="ext-link__title">Fiche CompanyWeb</div>
            <div class="ext-link__sub">Score crédit & indicateurs</div>
          </div>
          <span class="ext-link__arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17L17 7M7 7h10v10"/></svg></span>
        </a>''')

    # ─── Localisation rows ───
    loc_rows = []
    if locality or city:
        city_label = (locality or city) + (f" ({postal})" if postal else "")
        loc_rows.append((
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>',
            "Ville",
            _safe_html(city_label),
        ))
    loc_rows.append((
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/></svg>',
        "Pays", "Belgique",
    ))
    if category:
        loc_rows.append((
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
            "Catégorie Google", _safe_html(category),
        ))

    loc_rows_html = "".join(
        f'<div class="stat-row"><span class="stat-row__label">{icon}{label}</span><span class="stat-row__value">{value}</span></div>'
        for icon, label, value in loc_rows
    )

    gmaps_link = ""
    if biz.get("gmaps_url"):
        gmaps_link = f'''
        <a href="{_safe_html(biz["gmaps_url"])}" target="_blank" class="ext-link">
          <span class="ext-link__icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg></span>
          <div class="ext-link__main">
            <div class="ext-link__title">Voir sur Google Maps</div>
            <div class="ext-link__sub">Localisation, photos & itinéraire</div>
          </div>
          <span class="ext-link__arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M7 17L17 7M7 7h10v10"/></svg></span>
        </a>'''

    # ─── Signaux qualifiants ───
    nace_str = biz.get("nace_activities") or ""
    nace_count = len([e for e in _re.split(r"[;\n]+", nace_str) if e.strip()])
    sig_data = []
    if reviews_count:
        avis_qual = 'Activité visible' if reviews_count >= 10 else 'Peu d’avis'
        sig_data.append(("Volume d'avis", f"{reviews_count} avis · {avis_qual}"))
    if age is not None:
        sig_data.append(("Ancienneté",
                        f"{age} ans · {'Activité stable' if age >= 3 else 'Récente'}"))
    if website:
        sig_data.append(("Site web actif",
                        '<span style="color: var(--green-600);">Oui · digitalement présent</span>'))
    else:
        sig_data.append(("Site web",
                        '<span style="color: var(--red-600);">Pas de site · opportunité</span>'))
    if nace_count > 0:
        sig_data.append(("Diversification",
                        f"{nace_count} activité{'s' if nace_count > 1 else ''} NACE"))

    sig_rows_html = "".join(
        f'<div class="data-row"><span class="data-row__label">{label}</span><span class="data-row__value">{value}</span></div>'
        for label, value in sig_data
    )

    # ─── Identité légale : data rows ───
    legal_rows = []
    if biz.get("vat_number"):
        legal_rows.append(("Numéro TVA", f'<span class="data-row__value mono">{_safe_html(biz["vat_number"])}</span>'))
    if biz.get("bce_number"):
        legal_rows.append(("Numéro BCE", f'<span class="data-row__value mono">{_safe_html(biz["bce_number"])}</span>'))
    if biz.get("legal_form"):
        legal_rows.append(("Forme juridique", _safe_html(biz["legal_form"])))
    if biz.get("creation_date"):
        legal_rows.append(("Date de création", _safe_html(biz["creation_date"])))
    if biz.get("capital"):
        legal_rows.append(("Capital", _safe_html(biz["capital"])))
    legal_rows_html = "".join(
        f'<div class="data-row"><span class="data-row__label">{label}</span><div>{value}</div></div>'
        if 'class="data-row__value' in str(value)
        else f'<div class="data-row"><span class="data-row__label">{label}</span><span class="data-row__value">{value}</span></div>'
        for label, value in legal_rows
    )

    # ─── NACE chips ───
    nace_chips_html = ""
    if nace_str:
        entries = [e.strip() for e in _re.split(r"[;\n]+", nace_str) if e.strip()]
        chips = []
        for entry in entries:
            m = _re.match(r"^\s*([\d.]+)\s*[-–]?\s*(.*)$", entry)
            if m:
                code, label = m.group(1), m.group(2).strip()
            else:
                code, label = "", entry
            chips.append(
                f'<div class="nace-chip" style="padding: 12px 14px; font-size: 13px;">'
                + (f'<span class="nace-chip__code">{_safe_html(code)}</span>' if code else "")
                + f'<span>{_safe_html(label)}</span></div>'
            )
        nace_chips_html = (
            '<div style="display: flex; flex-direction: column; gap: 10px;">'
            + "".join(chips)
            + '</div>'
        )

    # ─── Historique tab content ───
    last_call = biz.get("last_call_at")
    callback = biz.get("callback_date")
    notes = (biz.get("call_notes") or "").strip()
    has_history = bool(last_call or callback or notes)
    if not has_history:
        history_html = f'''
        <div class="eval-card">
          <div class="empty-state">
            <div class="empty-state__icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>
              </svg>
            </div>
            <div class="empty-state__title serif">Aucun appel pour l'instant</div>
            <div class="empty-state__text">L'historique d'appels, notes et rappels apparaîtra ici dès le premier contact avec {name}.</div>
          </div>
        </div>'''
    else:
        history_html = f'''
        <div class="eval-card">
          <div class="data-grid">
            <div class="data-row"><span class="data-row__label">Dernier appel</span><span class="data-row__value">{_safe_html(last_call) or "—"}</span></div>
            <div class="data-row"><span class="data-row__label">Rappel prévu</span><span class="data-row__value">{_safe_html(callback) or "—"}</span></div>
          </div>
          {f'<div style="margin-top:16px;padding:14px;background:var(--cream);border-radius:11px;font-size:13px;color:var(--ink-700);"><strong>Notes :</strong><br>{_safe_html(notes)}</div>' if notes else ''}
        </div>'''

    # ─── Document HTML complet ───
    # NOTE : CSS DIRECTEMENT issu de fiche-entreprise.html (la maquette).
    # Pas de modifications, pas de préfixes, pas de !important — l'iframe
    # garantit l'isolation complète.
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --indigo-900: #1A0E5C; --indigo-700: #3425AF; --indigo-600: #4F3FF0;
    --indigo-500: #6B5CFF; --indigo-100: #EAE7FF; --indigo-50: #F5F4FF;
    --cream: #FBF9F4; --paper: #FFFFFF;
    --ink-900: #0E0B2E; --ink-700: #2C2A4A; --ink-500: #6B6890;
    --ink-400: #8C8AAE; --ink-200: #E3E1F0; --ink-100: #EFEDF7;
    --gold: #E8A838; --green-600: #0F9D58; --green-50: #E6F7EE;
    --red-600: #D33B3B; --red-50: #FDECEC; --amber-50: #FFF6E5;
    --amber-700: #B5740A;
    --shadow-sm: 0 1px 2px rgba(26, 14, 92, 0.04);
    --shadow-md: 0 4px 16px rgba(26, 14, 92, 0.06);
    --shadow-lg: 0 12px 40px rgba(26, 14, 92, 0.08);
    --radius-lg: 16px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--cream); color: var(--ink-900);
    font-size: 14px; line-height: 1.5; min-height: 100vh;
    -webkit-font-smoothing: antialiased;
  }}
  .serif {{ font-family: 'Fraunces', Georgia, serif; letter-spacing: -0.02em; }}
  .mono {{ font-family: 'JetBrains Mono', monospace; }}

  .action-bar {{
    position: sticky; top: 0; z-index: 50;
    background: rgba(251, 249, 244, 0.85);
    backdrop-filter: saturate(180%) blur(20px);
    -webkit-backdrop-filter: saturate(180%) blur(20px);
    border-bottom: 1px solid var(--ink-200);
  }}
  .action-bar__inner {{
    max-width: 1320px; margin: 0 auto;
    padding: 14px 32px;
    display: grid; grid-template-columns: 1fr auto auto;
    gap: 24px; align-items: center;
  }}
  .breadcrumb {{ display: flex; align-items: center; gap: 10px; color: var(--ink-500); font-size: 13px; }}
  .breadcrumb svg {{ width: 12px; height: 12px; }}
  .tracking-strip {{ display: flex; gap: 8px; align-items: center; padding: 6px 14px; background: var(--paper); border: 1px solid var(--ink-200); border-radius: 999px; }}
  .tracking-cell {{ display: flex; flex-direction: column; padding: 2px 14px; border-right: 1px solid var(--ink-100); min-width: 90px; }}
  .tracking-cell:last-child {{ border-right: none; }}
  .tracking-cell__label {{ font-size: 9.5px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-400); }}
  .tracking-cell__value {{ font-size: 13px; font-weight: 600; color: var(--ink-900); display: flex; align-items: center; gap: 6px; }}
  .pulse-dot {{ width: 7px; height: 7px; border-radius: 999px; background: var(--amber-700); position: relative; }}
  .pulse-dot::before {{ content: ''; position: absolute; inset: -3px; border-radius: 999px; background: var(--amber-700); opacity: .3; animation: pulse 2s ease-out infinite; }}
  @keyframes pulse {{ 0% {{ transform: scale(.9); opacity: .4; }} 100% {{ transform: scale(1.8); opacity: 0; }} }}

  .actions {{ display: flex; gap: 8px; }}
  .btn {{ display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; border-radius: 10px; font-family: inherit; font-size: 13px; font-weight: 600; border: none; cursor: pointer; transition: all .2s ease; white-space: nowrap; text-decoration: none; }}
  .btn svg {{ width: 15px; height: 15px; }}
  .btn--primary {{ background: var(--indigo-900); color: white; }}
  .btn--primary:hover {{ background: var(--indigo-700); transform: translateY(-1px); box-shadow: 0 6px 20px rgba(52, 37, 175, 0.3); }}
  .btn--ghost {{ background: var(--paper); color: var(--ink-900); border: 1px solid var(--ink-200); }}
  .btn--ghost:hover {{ border-color: var(--indigo-600); color: var(--indigo-700); }}
  .btn--icon {{ width: 38px; padding: 0; height: 38px; justify-content: center; }}
  .btn--call {{ background: var(--green-600); color: white; }}
  .btn--call:hover {{ background: #0a8049; transform: translateY(-1px); box-shadow: 0 6px 20px rgba(15, 157, 88, 0.3); }}

  .shell {{ max-width: 1320px; margin: 0 auto; padding: 32px; display: grid; grid-template-columns: 380px 1fr; gap: 32px; align-items: start; }}
  .sidebar {{ position: sticky; top: 90px; display: flex; flex-direction: column; gap: 16px; }}
  .card {{ background: var(--paper); border-radius: var(--radius-lg); border: 1px solid var(--ink-100); box-shadow: var(--shadow-sm); overflow: hidden; }}

  .identity-card {{ padding: 28px 28px 24px; position: relative; }}
  .identity-card::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, var(--indigo-600), var(--indigo-500), var(--gold)); }}
  .rank-badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; background: linear-gradient(135deg, #FFF1CC, #FFE4A3); color: #8A5A0A; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.02em; margin-bottom: 14px; }}
  .rank-badge svg {{ width: 12px; height: 12px; }}
  .company-name {{ font-family: 'Fraunces', Georgia, serif; font-size: 30px; font-weight: 600; letter-spacing: -0.025em; line-height: 1.1; color: var(--ink-900); margin-bottom: 6px; }}
  .company-form {{ font-size: 13px; color: var(--ink-500); margin-bottom: 18px; }}

  .score-panel {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 16px; margin: 0 -8px 18px; background: linear-gradient(135deg, var(--indigo-50) 0%, #F0EDFF 100%); border-radius: 14px; }}
  .score-block {{ text-align: center; }}
  .score-block__label {{ font-size: 9.5px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--indigo-700); margin-bottom: 6px; opacity: .8; }}
  .score-block__value {{ font-family: 'Fraunces', serif; font-size: 26px; font-weight: 600; color: var(--indigo-900); letter-spacing: -0.02em; display: flex; align-items: baseline; justify-content: center; gap: 3px; }}
  .score-block__value small {{ font-size: 13px; color: var(--ink-500); font-weight: 500; }}
  .reviews-count {{ font-size: 11px; color: var(--ink-500); margin-top: 2px; }}
  .stars {{ color: var(--gold); letter-spacing: 1px; font-size: 12px; }}

  .contact-list {{ display: flex; flex-direction: column; gap: 2px; }}
  .contact-item {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; color: var(--ink-700); font-size: 13px; border-bottom: 1px solid var(--ink-100); text-decoration: none; transition: color .15s; }}
  .contact-item:last-child {{ border-bottom: none; }}
  .contact-item:hover {{ color: var(--indigo-700); }}
  .contact-item__icon {{ width: 32px; height: 32px; flex-shrink: 0; border-radius: 9px; background: var(--indigo-50); color: var(--indigo-700); display: grid; place-items: center; }}
  .contact-item__icon svg {{ width: 15px; height: 15px; }}
  .contact-item__main {{ flex: 1; min-width: 0; }}
  .contact-item__label {{ font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-400); margin-bottom: 1px; }}
  .contact-item__value {{ color: var(--ink-900); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .contact-item__action {{ color: var(--ink-400); opacity: 0; transition: opacity .2s; }}
  .contact-item:hover .contact-item__action {{ opacity: 1; }}

  .website-block {{ padding: 14px 0; border-bottom: 1px solid var(--ink-100); }}
  .website-block__main {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px; color: var(--ink-700); text-decoration: none; transition: color .15s; }}
  .website-block__main:hover {{ color: var(--indigo-700); }}
  .website-block__icon {{ width: 32px; height: 32px; flex-shrink: 0; border-radius: 9px; background: var(--indigo-50); color: var(--indigo-700); display: grid; place-items: center; }}
  .website-block__icon svg {{ width: 15px; height: 15px; }}
  .website-block__info {{ flex: 1; min-width: 0; }}
  .website-block__label {{ font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-400); margin-bottom: 1px; }}
  .website-block__url {{ color: var(--ink-900); font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .audit-cta {{ display: inline-flex; align-items: center; gap: 7px; padding: 8px 14px; background: var(--indigo-900); color: white; border: none; border-radius: 9px; font-family: inherit; font-size: 12px; font-weight: 600; cursor: pointer; text-decoration: none; transition: all .2s; width: 100%; justify-content: center; }}
  .audit-cta:hover {{ background: var(--indigo-700); transform: translateY(-1px); box-shadow: 0 4px 14px rgba(52, 37, 175, 0.25); }}
  .audit-cta svg {{ width: 13px; height: 13px; }}
  .audit-cta__accent {{ width: 6px; height: 6px; border-radius: 999px; background: var(--gold); box-shadow: 0 0 0 3px rgba(232, 168, 56, 0.25); }}

  .admins-card {{ padding: 20px 24px; }}
  .admins-card__title {{ display: flex; align-items: center; gap: 8px; font-size: 10.5px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--indigo-700); margin-bottom: 14px; }}
  .admins-card__title svg {{ width: 14px; height: 14px; }}
  .admin-row {{ display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--ink-100); }}
  .admin-row:last-child {{ border-bottom: none; }}
  .admin-avatar {{ width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, var(--indigo-600), var(--indigo-500)); color: white; display: grid; place-items: center; font-family: 'Fraunces', serif; font-size: 14px; font-weight: 600; flex-shrink: 0; }}
  .admin-info {{ flex: 1; min-width: 0; }}
  .admin-name {{ font-size: 13.5px; font-weight: 600; color: var(--ink-900); margin-bottom: 1px; }}
  .admin-role {{ font-size: 11px; color: var(--ink-500); }}
  .admin-action {{ color: var(--ink-400); background: transparent; border: none; padding: 6px; cursor: pointer; border-radius: 6px; transition: all .15s; }}
  .admin-action:hover {{ color: var(--indigo-700); background: var(--indigo-50); }}
  .admin-action svg {{ width: 14px; height: 14px; display: block; }}

  .ai-footer {{ padding: 14px 28px; background: var(--indigo-50); border-top: 1px solid var(--ink-100); display: flex; align-items: center; gap: 10px; font-size: 11px; color: var(--ink-500); }}
  .ai-dot {{ width: 6px; height: 6px; border-radius: 999px; background: var(--indigo-600); box-shadow: 0 0 0 3px var(--indigo-100); }}

  .main {{ display: flex; flex-direction: column; gap: 20px; min-width: 0; }}
  .tabs {{ display: flex; gap: 4px; padding: 6px; background: var(--paper); border-radius: 14px; border: 1px solid var(--ink-100); box-shadow: var(--shadow-sm); width: fit-content; }}
  .tab {{ padding: 9px 18px; background: transparent; border: none; border-radius: 9px; font-family: inherit; font-size: 13px; font-weight: 600; color: var(--ink-500); cursor: pointer; transition: all .2s; display: inline-flex; align-items: center; gap: 8px; }}
  .tab svg {{ width: 15px; height: 15px; }}
  .tab:hover {{ color: var(--ink-900); }}
  .tab.is-active {{ background: var(--indigo-900); color: white; }}
  .tab-badge {{ display: inline-flex; align-items: center; justify-content: center; min-width: 18px; height: 18px; padding: 0 5px; background: var(--indigo-100); color: var(--indigo-700); border-radius: 999px; font-size: 10px; font-weight: 700; }}
  .tab.is-active .tab-badge {{ background: rgba(255,255,255,0.2); color: white; }}

  .panel {{ display: none; flex-direction: column; gap: 16px; }}
  .panel.is-active {{ display: flex; }}

  .accordion {{ background: var(--paper); border-radius: var(--radius-lg); border: 1px solid var(--ink-100); box-shadow: var(--shadow-sm); overflow: hidden; }}
  .acc-header {{ width: 100%; padding: 20px 24px; background: transparent; border: none; text-align: left; cursor: pointer; display: flex; align-items: center; gap: 14px; font-family: inherit; transition: background .15s; }}
  .acc-header:hover {{ background: var(--cream); }}
  .acc-icon {{ width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; flex-shrink: 0; }}
  .acc-icon svg {{ width: 18px; height: 18px; }}
  .acc-icon--indigo {{ background: var(--indigo-50); color: var(--indigo-700); }}
  .acc-icon--gold {{ background: var(--amber-50); color: var(--amber-700); }}
  .acc-icon--green {{ background: var(--green-50); color: var(--green-600); }}
  .acc-titles {{ flex: 1; min-width: 0; }}
  .acc-title {{ font-size: 15px; font-weight: 600; color: var(--ink-900); margin-bottom: 2px; }}
  .acc-subtitle {{ font-size: 12px; color: var(--ink-500); }}
  .acc-chevron {{ width: 32px; height: 32px; border-radius: 10px; background: var(--ink-100); color: var(--ink-500); display: grid; place-items: center; transition: transform .25s; flex-shrink: 0; }}
  .acc-chevron svg {{ width: 14px; height: 14px; }}
  .accordion.is-open .acc-chevron {{ transform: rotate(180deg); background: var(--indigo-100); color: var(--indigo-700); }}
  .acc-body {{ max-height: 0; overflow: hidden; transition: max-height .35s ease; }}
  .accordion.is-open .acc-body {{ max-height: 1000px; }}
  .acc-body-inner {{ padding: 0 24px 24px; border-top: 1px dashed var(--ink-200); margin-top: 4px; padding-top: 20px; }}

  .data-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px 24px; }}
  .data-row {{ display: flex; flex-direction: column; gap: 3px; padding-bottom: 12px; border-bottom: 1px solid var(--ink-100); }}
  .data-row__label {{ font-size: 10px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-400); }}
  .data-row__value {{ font-size: 14px; color: var(--ink-900); font-weight: 500; }}
  .data-row__value.mono {{ font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--indigo-700); }}
  .nace-chip {{ display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; background: var(--indigo-50); color: var(--indigo-700); border-radius: 7px; font-size: 12px; font-weight: 500; }}
  .nace-chip__code {{ font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 600; color: var(--indigo-900); }}

  .ext-link {{ display: flex; align-items: center; gap: 14px; padding: 14px 16px; background: var(--cream); border-radius: 11px; text-decoration: none; border: 1px solid var(--ink-100); transition: all .2s; }}
  .ext-link + .ext-link {{ margin-top: 10px; }}
  .ext-link:hover {{ border-color: var(--indigo-600); background: var(--indigo-50); transform: translateX(2px); }}
  .ext-link__icon {{ width: 36px; height: 36px; border-radius: 9px; background: var(--paper); color: var(--indigo-700); display: grid; place-items: center; border: 1px solid var(--ink-200); }}
  .ext-link__icon svg {{ width: 17px; height: 17px; }}
  .ext-link__main {{ flex: 1; }}
  .ext-link__title {{ font-size: 13px; font-weight: 600; color: var(--ink-900); margin-bottom: 1px; }}
  .ext-link__sub {{ font-size: 11px; color: var(--ink-500); }}
  .ext-link__arrow {{ color: var(--ink-400); }}
  .ext-link__arrow svg {{ width: 16px; height: 16px; }}

  .eval-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  .eval-card {{ background: var(--paper); border: 1px solid var(--ink-100); border-radius: var(--radius-lg); padding: 22px; box-shadow: var(--shadow-sm); }}
  .eval-card--full {{ grid-column: 1 / -1; }}
  .eval-card__header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }}
  .eval-card__icon {{ width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; }}
  .eval-card__icon svg {{ width: 16px; height: 16px; }}
  .eval-card__title {{ font-size: 14px; font-weight: 600; color: var(--ink-900); }}
  .eval-card__sub {{ font-size: 11px; color: var(--ink-500); }}
  .stat-row {{ display: flex; align-items: center; justify-content: space-between; padding: 11px 0; border-bottom: 1px solid var(--ink-100); }}
  .stat-row:last-child {{ border-bottom: none; }}
  .stat-row__label {{ font-size: 12.5px; color: var(--ink-500); display: flex; align-items: center; gap: 8px; }}
  .stat-row__label svg {{ width: 14px; height: 14px; color: var(--ink-400); }}
  .stat-row__value {{ font-size: 13px; font-weight: 600; color: var(--ink-900); }}

  .empty-state {{ text-align: center; padding: 60px 30px; color: var(--ink-500); }}
  .empty-state__icon {{ width: 60px; height: 60px; margin: 0 auto 16px; background: var(--indigo-50); color: var(--indigo-700); border-radius: 18px; display: grid; place-items: center; }}
  .empty-state__icon svg {{ width: 26px; height: 26px; }}
  .empty-state__title {{ font-family: 'Fraunces', serif; font-size: 18px; color: var(--ink-900); margin-bottom: 6px; }}
  .empty-state__text {{ font-size: 13px; max-width: 320px; margin: 0 auto; }}
  .status-pill {{ display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; background: var(--indigo-100); color: var(--indigo-700); border-radius: 999px; font-size: 11px; font-weight: 600; }}

  @media (max-width: 1100px) {{
    .shell {{ grid-template-columns: 1fr; }}
    .sidebar {{ position: static; }}
    .action-bar__inner {{ grid-template-columns: 1fr; gap: 12px; }}
    .tracking-strip {{ overflow-x: auto; }}
  }}
  @media (max-width: 640px) {{
    .shell {{ padding: 16px; gap: 16px; }}
    .action-bar__inner {{ padding: 12px 16px; }}
    .data-grid {{ grid-template-columns: 1fr; }}
    .eval-grid {{ grid-template-columns: 1fr; }}
    .company-name {{ font-size: 24px; }}
  }}
</style>
</head>
<body>

<div class="action-bar">
  <div class="action-bar__inner">
    <div class="breadcrumb">
      <span>Prospects</span>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      <span>{city}</span>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>
      <span style="color: var(--ink-900); font-weight: 500;">{name}</span>
    </div>

    <div class="tracking-strip">
      <div class="tracking-cell">
        <span class="tracking-cell__label">Statut</span>
        <span class="tracking-cell__value">
          <span class="pulse-dot" style="background: {pulse_color};"></span>
          {_safe_html(status)}
        </span>
      </div>
      <div class="tracking-cell">
        <span class="tracking-cell__label">Dernier appel</span>
        <span class="tracking-cell__value" style="color: var(--ink-400);">{_safe_html(biz.get("last_call_at") or "—")}</span>
      </div>
      <div class="tracking-cell">
        <span class="tracking-cell__label">Rappel</span>
        <span class="tracking-cell__value" style="color: var(--ink-400);">{_safe_html(biz.get("callback_date") or "—")}</span>
      </div>
    </div>

    <div class="actions">
      {f'<a href="tel:{_safe_html(phone)}" class="btn btn--call" title="Appeler maintenant"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/></svg>Appeler</a>' if phone else ''}
      <button class="btn btn--ghost btn--icon" title="Plus d&#39;actions"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg></button>
    </div>
  </div>
</div>

<div class="shell">
  <aside class="sidebar">
    <div class="card">
      <div class="identity-card">
        {rank_html}
        <h1 class="company-name">{name}</h1>
        {f'<p class="company-form">{subtitle}</p>' if subtitle else ''}
        {score_html}
        {contact_list_html}
      </div>
      <div class="ai-footer">
        <span class="ai-dot"></span>
        <span>Enrichissement IA · <strong style="color: var(--ink-700);">{_safe_html(ai_label)}</strong></span>
      </div>
    </div>
    {dirigeants_html}
  </aside>

  <main class="main">
    <div class="tabs" role="tablist">
      <button class="tab is-active" data-panel="evaluation" role="tab">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        Évaluation
      </button>
      <button class="tab" data-panel="identite" role="tab">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4"/>
        </svg>
        Identité légale
      </button>
      <button class="tab" data-panel="historique" role="tab">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
        </svg>
        Historique
      </button>
    </div>

    <section class="panel is-active" id="panel-evaluation">
      <div class="eval-grid">
        <div class="eval-card">
          <div class="eval-card__header">
            <div class="eval-card__icon" style="background: var(--green-50); color: var(--green-600);">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
              </svg>
            </div>
            <div>
              <div class="eval-card__title">Santé financière</div>
              <div class="eval-card__sub">Sources officielles BNB</div>
            </div>
          </div>
          {fin_rows_html}
          {f'<div style="margin-top: 16px;">{"".join(fin_links)}</div>' if fin_links else ''}
        </div>

        <div class="eval-card">
          <div class="eval-card__header">
            <div class="eval-card__icon" style="background: var(--amber-50); color: var(--amber-700);">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/>
              </svg>
            </div>
            <div>
              <div class="eval-card__title">Présence locale</div>
              <div class="eval-card__sub">Localisation & catégorie</div>
            </div>
          </div>
          {loc_rows_html}
          {f'<div style="margin-top: 16px;">{gmaps_link}</div>' if gmaps_link else ''}
        </div>

        <div class="eval-card eval-card--full">
          <div class="eval-card__header">
            <div class="eval-card__icon" style="background: var(--indigo-50); color: var(--indigo-700);">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="9 11 12 14 22 4"/>
                <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
              </svg>
            </div>
            <div>
              <div class="eval-card__title">Signaux qualifiants</div>
              <div class="eval-card__sub">Pourquoi ce prospect mérite votre attention</div>
            </div>
          </div>
          <div class="data-grid">{sig_rows_html}</div>
        </div>
      </div>
    </section>

    <section class="panel" id="panel-identite">
      <div class="accordion is-open">
        <button class="acc-header" aria-expanded="true">
          <span class="acc-icon acc-icon--indigo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4"/></svg>
          </span>
          <div class="acc-titles">
            <div class="acc-title">Données légales & immatriculation</div>
            <div class="acc-subtitle">TVA, BCE, forme juridique</div>
          </div>
          <span class="acc-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg></span>
        </button>
        <div class="acc-body"><div class="acc-body-inner"><div class="data-grid">{legal_rows_html}</div></div></div>
      </div>

      {f'''<div class="accordion is-open">
        <button class="acc-header" aria-expanded="true">
          <span class="acc-icon acc-icon--indigo">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          </span>
          <div class="acc-titles">
            <div class="acc-title">Codes d'activité NACE</div>
            <div class="acc-subtitle">{nace_count} code(s) enregistré(s)</div>
          </div>
          <span class="acc-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg></span>
        </button>
        <div class="acc-body"><div class="acc-body-inner">{nace_chips_html}</div></div>
      </div>''' if nace_chips_html else ''}
    </section>

    <section class="panel" id="panel-historique">{history_html}</section>
  </main>
</div>

<script>
  // Tab switching
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
  tabs.forEach(tab => {{
    tab.addEventListener('click', () => {{
      const target = tab.dataset.panel;
      tabs.forEach(t => t.classList.remove('is-active'));
      panels.forEach(p => p.classList.remove('is-active'));
      tab.classList.add('is-active');
      document.getElementById('panel-' + target).classList.add('is-active');
    }});
  }});

  // Accordion toggle
  document.querySelectorAll('.accordion').forEach(acc => {{
    const header = acc.querySelector('.acc-header');
    header.addEventListener('click', () => {{
      acc.classList.toggle('is-open');
      header.setAttribute('aria-expanded', acc.classList.contains('is-open'));
    }});
  }});
</script>

</body>
</html>"""


# ===========================================================================
# CSS injection (once per session)
# ===========================================================================

_BUSINESS_DETAIL_CSS = """
<style>
/* Google Fonts via @import (les <link> ne sont pas whitelistés par le
   sanitizer Markdown de Streamlit — toute la balise <link> ferait
   échouer le rendu et le CSS serait affiché en texte brut). */
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

.bd-root {
  --bd-indigo-900: #1A0E5C !important;
  --bd-indigo-700: #3425AF !important;
  --bd-indigo-600: #4F3FF0 !important;
  --bd-indigo-500: #6B5CFF !important;
  --bd-indigo-100: #EAE7FF !important;
  --bd-indigo-50: #F5F4FF !important;
  --bd-cream: #FBF9F4 !important;
  --bd-paper: #FFFFFF !important;
  --bd-ink-900: #0E0B2E !important;
  --bd-ink-700: #2C2A4A !important;
  --bd-ink-500: #6B6890 !important;
  --bd-ink-400: #8C8AAE !important;
  --bd-ink-200: #E3E1F0 !important;
  --bd-ink-100: #EFEDF7 !important;
  --bd-gold: #E8A838 !important;
  --bd-green-600: #0F9D58 !important;
  --bd-green-50: #E6F7EE !important;
  --bd-amber-50: #FFF6E5 !important;
  --bd-amber-700: #B5740A !important;
  font-family: 'Inter', system-ui, sans-serif !important;
  color: var(--bd-ink-900) !important;
  font-size: 14px !important;
}
.bd-root .bd-serif { font-family: 'Fraunces', Georgia, serif !important; letter-spacing: -0.02em !important; }
.bd-root .bd-mono  { font-family: 'JetBrains Mono', monospace !important; }

/* ========== ACTION BAR ========== */
.bd-root .bd-action-bar{
  background: rgba(251, 249, 244, 0.92) !important;
  backdrop-filter: saturate(180%) blur(20px) !important;
  -webkit-backdrop-filter: saturate(180%) blur(20px) !important;
  border: 1px solid var(--bd-ink-200) !important;
  border-radius: 14px !important;
  padding: 14px 22px !important;
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  gap: 24px !important;
  margin-bottom: 14px !important;
  flex-wrap: wrap !important;
}
.bd-root .bd-breadcrumb{
  display: flex !important; align-items: center !important; gap: 10px !important;
  color: var(--bd-ink-500) !important; font-size: 13px !important;
}
.bd-root .bd-breadcrumb .bd-current{
  color: var(--bd-ink-900) !important; font-weight: 600 !important;
}
.bd-root .bd-tracking-strip{
  display: flex !important; gap: 8px !important; align-items: center !important;
  padding: 6px 14px !important;
  background: var(--bd-paper) !important;
  border: 1px solid var(--bd-ink-200) !important;
  border-radius: 999px !important;
}
.bd-root .bd-tcell{
  display: flex !important; flex-direction: column !important;
  padding: 2px 14px !important;
  border-right: 1px solid var(--bd-ink-100) !important;
  min-width: 90px !important;
}
.bd-root .bd-tcell:last-child{ border-right: none !important; }
.bd-root .bd-tcell-label{
  font-size: 9.5px !important; font-weight: 600 !important; letter-spacing: 0.1em !important;
  text-transform: uppercase !important; color: var(--bd-ink-400) !important;
}
.bd-root .bd-tcell-value{
  font-size: 13px !important; font-weight: 600 !important; color: var(--bd-ink-900) !important;
  display: flex !important; align-items: center !important; gap: 6px !important;
}
.bd-root .bd-pulse{
  width: 7px !important; height: 7px !important; border-radius: 999px !important;
  background: var(--bd-amber-700) !important; position: relative !important;
}
.bd-root .bd-pulse::before{
  content: '' !important; position: absolute !important; inset: -3px !important;
  border-radius: 999px !important; background: var(--bd-amber-700) !important;
  opacity: .3 !important; animation: bd-pulse 2s ease-out infinite !important;
}
@keyframes bd-pulse {
  0% { transform: scale(.9) !important; opacity: .4 !important; }
  100% { transform: scale(1.8) !important; opacity: 0 !important; }
}

/* ========== IDENTITY CARD ========== */
.bd-root .bd-card{
  background: var(--bd-paper) !important;
  border-radius: 16px !important;
  border: 1px solid var(--bd-ink-100) !important;
  box-shadow: 0 4px 16px rgba(26, 14, 92, 0.06) !important;
  overflow: hidden !important;
  margin-bottom: 16px !important;
}
.bd-root .bd-identity{ padding: 28px 28px 24px !important; position: relative !important; }
.bd-root .bd-identity::before{
  content: '' !important; position: absolute !important; top: 0 !important; left: 0 !important; right: 0 !important;
  height: 4px !important;
  background: linear-gradient(90deg, var(--bd-indigo-600), var(--bd-indigo-500), var(--bd-gold)) !important;
}
.bd-root .bd-rank-badge{
  display: inline-flex !important; align-items: center !important; gap: 6px !important;
  padding: 5px 11px !important;
  background: linear-gradient(135deg, #FFF1CC, #FFE4A3) !important;
  color: #8A5A0A !important;
  border-radius: 999px !important; font-size: 11px !important; font-weight: 700 !important;
  letter-spacing: 0.02em !important; margin-bottom: 14px !important;
}
.bd-root .bd-company-name{
  font-family: 'Fraunces', Georgia, 'Times New Roman', serif !important;
  font-size: 30px !important; font-weight: 600 !important; letter-spacing: -0.025em !important;
  line-height: 1.1 !important; color: var(--bd-ink-900) !important; margin-bottom: 6px !important;
}
.bd-root .bd-company-form{
  font-size: 13px !important; color: var(--bd-ink-500) !important; margin-bottom: 18px !important;
}

/* Score panel */
.bd-root .bd-score-panel{
  display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 12px !important;
  padding: 16px !important;
  margin: 0 -8px 18px !important;
  background: linear-gradient(135deg, var(--bd-indigo-50) 0%, #F0EDFF 100%) !important;
  border-radius: 14px !important;
}
.bd-root .bd-score-block{ text-align: center !important; }
.bd-root .bd-score-label{
  font-size: 9.5px !important; font-weight: 600 !important; letter-spacing: 0.1em !important;
  text-transform: uppercase !important; color: var(--bd-indigo-700) !important;
  margin-bottom: 6px !important; opacity: .8 !important;
}
.bd-root .bd-score-value{
  font-family: 'Fraunces', Georgia, serif !important; font-size: 26px !important; font-weight: 600 !important;
  color: var(--bd-indigo-900) !important; letter-spacing: -0.02em !important;
  display: flex !important; align-items: baseline !important; justify-content: center !important; gap: 3px !important;
}
.bd-root .bd-score-value small{ font-size: 13px !important; color: var(--bd-ink-500) !important; font-weight: 500 !important; }
.bd-root .bd-stars{ color: var(--bd-gold) !important; letter-spacing: 1px !important; font-size: 12px !important; }
.bd-root .bd-reviews-count{ font-size: 11px !important; color: var(--bd-ink-500) !important; margin-top: 2px !important; }

/* Contact list */
.bd-root .bd-contact-list{ display: flex !important; flex-direction: column !important; gap: 0 !important; }
.bd-root .bd-contact-item{
  display: flex !important; align-items: center !important; gap: 12px !important;
  padding: 10px 0 !important;
  color: var(--bd-ink-700) !important; font-size: 13px !important;
  border-bottom: 1px solid var(--bd-ink-100) !important;
  text-decoration: none !important; transition: color .15s !important;
}
.bd-root .bd-contact-item:last-child{ border-bottom: none !important; }
.bd-root .bd-contact-item:hover{ color: var(--bd-indigo-700) !important; }
.bd-root .bd-icon-pill{
  width: 32px !important; height: 32px !important; flex-shrink: 0 !important;
  border-radius: 9px !important;
  background: var(--bd-indigo-50) !important;
  color: var(--bd-indigo-700) !important;
  display: grid !important; place-items: center !important;
}
.bd-root .bd-icon-pill svg{ width: 15px !important; height: 15px !important; }
.bd-root .bd-contact-main{ flex: 1 !important; min-width: 0 !important; }
.bd-root .bd-contact-label{
  font-size: 10px !important; font-weight: 600 !important; letter-spacing: 0.08em !important;
  text-transform: uppercase !important; color: var(--bd-ink-400) !important; margin-bottom: 1px !important;
}
.bd-root .bd-contact-value{
  color: var(--bd-ink-900) !important; font-weight: 500 !important;
  overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important;
}

/* Website block */
.bd-root .bd-website-block{ padding: 14px 0 !important; border-bottom: 1px solid var(--bd-ink-100) !important; }
.bd-root .bd-website-main{
  display: flex !important; align-items: center !important; gap: 12px !important; margin-bottom: 12px !important;
  color: var(--bd-ink-700) !important; text-decoration: none !important;
}
.bd-root .bd-website-main:hover{ color: var(--bd-indigo-700) !important; }
.bd-root .bd-website-info{ flex: 1 !important; min-width: 0 !important; }
.bd-root .bd-website-url{
  color: var(--bd-ink-900) !important; font-weight: 500 !important;
  overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important;
}

/* AI footer in identity card */
.bd-root .bd-ai-footer{
  padding: 14px 28px !important;
  background: var(--bd-indigo-50) !important;
  border-top: 1px solid var(--bd-ink-100) !important;
  display: flex !important; align-items: center !important; gap: 10px !important;
  font-size: 11px !important; color: var(--bd-ink-500) !important;
}
.bd-root .bd-ai-dot{
  width: 6px !important; height: 6px !important; border-radius: 999px !important;
  background: var(--bd-indigo-600) !important;
  box-shadow: 0 0 0 3px var(--bd-indigo-100) !important;
}

/* Dirigeants card */
.bd-root .bd-admins{ padding: 20px 24px !important; }
.bd-root .bd-admins-title{
  display: flex !important; align-items: center !important; gap: 8px !important;
  font-size: 10.5px !important; font-weight: 700 !important; letter-spacing: 0.1em !important;
  text-transform: uppercase !important; color: var(--bd-indigo-700) !important;
  margin-bottom: 14px !important;
}
.bd-root .bd-admin-row{
  display: flex !important; align-items: center !important; gap: 12px !important;
  padding: 10px 0 !important;
  border-bottom: 1px solid var(--bd-ink-100) !important;
}
.bd-root .bd-admin-row:last-child{ border-bottom: none !important; }
.bd-root .bd-admin-avatar{
  width: 36px !important; height: 36px !important; border-radius: 50% !important;
  background: linear-gradient(135deg, var(--bd-indigo-600), var(--bd-indigo-500)) !important;
  color: white !important;
  display: grid !important; place-items: center !important;
  font-family: 'Fraunces', Georgia, serif !important; font-size: 14px !important; font-weight: 600 !important;
  flex-shrink: 0 !important;
}
.bd-root .bd-admin-name{ font-size: 13.5px !important; font-weight: 600 !important; color: var(--bd-ink-900) !important; margin-bottom: 1px !important; }
.bd-root .bd-admin-role{ font-size: 11px !important; color: var(--bd-ink-500) !important; }

/* ========== EVAL CARDS ========== */
.bd-root .bd-eval-grid{
  display: grid !important; grid-template-columns: 1fr 1fr !important; gap: 14px !important;
}
.bd-root .bd-eval-card{
  background: var(--bd-paper) !important; border: 1px solid var(--bd-ink-100) !important;
  border-radius: 16px !important; padding: 22px !important;
  box-shadow: 0 1px 2px rgba(26, 14, 92, 0.04) !important;
}
.bd-root .bd-eval-card--full{ grid-column: 1 / -1 !important; }
.bd-root .bd-eval-head{ display: flex !important; align-items: center !important; gap: 10px !important; margin-bottom: 16px !important; }
.bd-root .bd-eval-icon{
  width: 34px !important; height: 34px !important; border-radius: 10px !important;
  display: grid !important; place-items: center !important;
}
.bd-root .bd-eval-icon svg{ width: 16px !important; height: 16px !important; }
.bd-root .bd-eval-title{ font-size: 14px !important; font-weight: 600 !important; color: var(--bd-ink-900) !important; }
.bd-root .bd-eval-sub{ font-size: 11px !important; color: var(--bd-ink-500) !important; }

.bd-root .bd-stat-row{
  display: flex !important; align-items: center !important; justify-content: space-between !important;
  padding: 11px 0 !important;
  border-bottom: 1px solid var(--bd-ink-100) !important;
}
.bd-root .bd-stat-row:last-child{ border-bottom: none !important; }
.bd-root .bd-stat-label{ font-size: 12.5px !important; color: var(--bd-ink-500) !important; display: flex !important; align-items: center !important; gap: 8px !important; }
.bd-root .bd-stat-value{ font-size: 13px !important; font-weight: 600 !important; color: var(--bd-ink-900) !important; }

.bd-root .bd-status-pill{
  display: inline-flex !important; align-items: center !important; gap: 6px !important;
  padding: 5px 11px !important;
  background: var(--bd-indigo-100) !important; color: var(--bd-indigo-700) !important;
  border-radius: 999px !important; font-size: 11px !important; font-weight: 600 !important;
}
.bd-root .bd-pill-green{ background: var(--bd-green-50) !important; color: var(--bd-green-600) !important; }

/* Ext link */
.bd-root .bd-ext-link{
  display: flex !important; align-items: center !important; gap: 14px !important;
  padding: 14px 16px !important;
  background: var(--bd-cream) !important;
  border-radius: 11px !important;
  text-decoration: none !important;
  border: 1px solid var(--bd-ink-100) !important;
  transition: all .2s !important;
  margin-top: 10px !important;
}
.bd-root .bd-ext-link:hover{
  border-color: var(--bd-indigo-600) !important;
  background: var(--bd-indigo-50) !important;
  transform: translateX(2px) !important;
}
.bd-root .bd-ext-icon{
  width: 36px !important; height: 36px !important; border-radius: 9px !important;
  background: var(--bd-paper) !important; color: var(--bd-indigo-700) !important;
  display: grid !important; place-items: center !important;
  border: 1px solid var(--bd-ink-200) !important;
}
.bd-root .bd-ext-main{ flex: 1 !important; }
.bd-root .bd-ext-title{ font-size: 13px !important; font-weight: 600 !important; color: var(--bd-ink-900) !important; margin-bottom: 1px !important; }
.bd-root .bd-ext-sub{ font-size: 11px !important; color: var(--bd-ink-500) !important; }

/* Data grid (NACE / legal) */
.bd-root .bd-data-grid{ display: grid !important; grid-template-columns: repeat(2, 1fr) !important; gap: 14px 24px !important; }
.bd-root .bd-data-row{
  display: flex !important; flex-direction: column !important; gap: 3px !important;
  padding-bottom: 12px !important;
  border-bottom: 1px solid var(--bd-ink-100) !important;
}
.bd-root .bd-data-label{
  font-size: 10px !important; font-weight: 600 !important; letter-spacing: 0.08em !important;
  text-transform: uppercase !important; color: var(--bd-ink-400) !important;
}
.bd-root .bd-data-value{ font-size: 14px !important; color: var(--bd-ink-900) !important; font-weight: 500 !important; }
.bd-root .bd-mono{ font-family: 'JetBrains Mono', monospace !important; font-size: 13px !important; color: var(--bd-indigo-700) !important; }

.bd-root .bd-nace-chip{
  display: inline-flex !important; align-items: center !important; gap: 8px !important;
  padding: 12px 14px !important;
  background: var(--bd-indigo-50) !important; color: var(--bd-indigo-700) !important;
  border-radius: 7px !important; font-size: 13px !important; font-weight: 500 !important;
  margin-bottom: 10px !important;
}
.bd-root .bd-nace-code{
  font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important;
  font-weight: 600 !important; color: var(--bd-indigo-900) !important;
}

/* Empty state */
.bd-root .bd-empty{
  text-align: center !important; padding: 60px 30px !important; color: var(--bd-ink-500) !important;
}
.bd-root .bd-empty-icon{
  width: 60px !important; height: 60px !important; margin: 0 auto 16px !important;
  background: var(--bd-indigo-50) !important; color: var(--bd-indigo-700) !important;
  border-radius: 18px !important; display: grid !important; place-items: center !important;
}
.bd-root .bd-empty-icon svg{ width: 26px !important; height: 26px !important; }
.bd-root .bd-empty-title{
  font-family: 'Fraunces', Georgia, serif !important; font-size: 18px !important;
  color: var(--bd-ink-900) !important; margin-bottom: 6px !important;
}
.bd-root .bd-empty-text{ font-size: 13px !important; max-width: 360px !important; margin: 0 auto 20px !important; }

/* ========== OVERRIDES STREAMLIT NATIFS ========== */
/* Appliqués globalement : la maquette « Oui Allo » devient le design system
 * de tous les tabs et expanders de l'app (cohérent, ils en gagnent en classe).
 * Pas de side-effect indésirable — les tabs natifs étaient ternes par défaut.
 */

/* Tabs : pill design (fond paper, items pill indigo-900 actif) */
[data-baseweb="tab-list"] {
  background: var(--bd-paper, #fff) !important;
  padding: 6px !important;
  border: 1px solid var(--bd-ink-100, #EFEDF7) !important;
  border-radius: 14px !important;
  box-shadow: 0 1px 2px rgba(26, 14, 92, 0.04) !important;
  gap: 4px !important;
  width: fit-content !important;
}
[data-baseweb="tab-list"] [data-baseweb="tab-border"] { display: none !important; }
[data-baseweb="tab-list"] [data-baseweb="tab-highlight"] { display: none !important; }
[data-baseweb="tab-list"] button[data-baseweb="tab"] {
  background: transparent !important;
  border: none !important;
  border-radius: 9px !important;
  padding: 9px 18px !important;
  font-family: 'Inter', system-ui, sans-serif !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  color: var(--bd-ink-500, #6B6890) !important;
  transition: all .2s !important;
  margin: 0 !important;
  height: auto !important;
}
[data-baseweb="tab-list"] button[data-baseweb="tab"]:hover {
  color: var(--bd-ink-900, #0E0B2E) !important;
}
[data-baseweb="tab-list"] button[data-baseweb="tab"][aria-selected="true"] {
  background: var(--bd-indigo-900, #1A0E5C) !important;
  color: white !important;
}

/* Expanders : carte arrondie, header padding confortable, chevron indigo */
[data-testid="stExpander"] {
  background: var(--bd-paper, #fff) !important;
  border-radius: 16px !important;
  border: 1px solid var(--bd-ink-100, #EFEDF7) !important;
  box-shadow: 0 1px 2px rgba(26, 14, 92, 0.04) !important;
  overflow: hidden !important;
  margin-bottom: 14px !important;
}
[data-testid="stExpander"] details > summary {
  padding: 16px 22px !important;
  font-family: 'Inter', system-ui, sans-serif !important;
  background: transparent !important;
  transition: background .15s !important;
}
[data-testid="stExpander"] details > summary p,
[data-testid="stExpander"] details > summary span {
  font-size: 15px !important;
  font-weight: 600 !important;
  color: var(--bd-ink-900, #0E0B2E) !important;
}
[data-testid="stExpander"] details > summary:hover {
  background: var(--bd-cream, #FBF9F4) !important;
}
[data-testid="stExpander"] [data-testid="stExpanderToggleIcon"] {
  color: var(--bd-indigo-700, #3425AF) !important;
}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
  padding: 16px 22px 22px !important;
  border-top: 1px dashed var(--bd-ink-200, #E3E1F0) !important;
}

/* Trigger AUDIT caché : container 100% invisible mais le bouton existe dans
   le DOM pour que le JS de l'iframe puisse le cliquer via document.querySelector.
   On utilise visibility:hidden + width/height 0 plutôt que display:none —
   certains navigateurs/Streamlit ignorent les clicks sur display:none. */
.st-key-bd-hidden-audit-run {
  position: absolute !important;
  left: -9999px !important;
  width: 1px !important;
  height: 1px !important;
  overflow: hidden !important;
}

/* CTA Audit SEO : bouton indigo-900 (scopé via st.container key="bd-audit-cta") */
.st-key-bd-audit-cta [data-testid="stButton"] > button,
[data-testid="stContainer"][class*="bd-audit-cta"] [data-testid="stButton"] > button {
  background: var(--bd-indigo-900, #1A0E5C) !important;
  color: white !important;
  border: none !important;
  border-radius: 9px !important;
  font-family: 'Inter', system-ui, sans-serif !important;
  font-size: 12px !important;
  font-weight: 600 !important;
  padding: 10px 14px !important;
  width: 100% !important;
  transition: all .2s !important;
}
.st-key-bd-audit-cta [data-testid="stButton"] > button:hover,
[data-testid="stContainer"][class*="bd-audit-cta"] [data-testid="stButton"] > button:hover {
  background: var(--bd-indigo-700, #3425AF) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 14px rgba(52, 37, 175, 0.25) !important;
}

/* CTA Appeler : bouton vert (scopé via st.container key="bd-call-cta") */
.st-key-bd-call-cta [data-testid="stButton"] > button {
  background: var(--bd-green-600, #0F9D58) !important;
  color: white !important;
  border: none !important;
  border-radius: 10px !important;
  font-family: 'Inter', system-ui, sans-serif !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  padding: 10px 18px !important;
  transition: all .2s !important;
}
.st-key-bd-call-cta [data-testid="stButton"] > button:hover {
  background: #0a8049 !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 20px rgba(15, 157, 88, 0.3) !important;
}
.st-key-bd-call-cta [data-testid="stButton"] > button:disabled {
  background: var(--bd-ink-200, #E3E1F0) !important;
  color: var(--bd-ink-500, #6B6890) !important;
  transform: none !important;
  box-shadow: none !important;
  cursor: not-allowed !important;
}
</style>
"""


# NB : _BUSINESS_DETAIL_CSS est injecté au NIVEAU PAGE (top-level, après
# _init_state()) plutôt que dans show_business_details(). Raison :
# st.markdown('<style>') placé dans une colonne Streamlit est scopé au DOM
# de cette colonne — au prochain rerun (clic sur une autre fiche), la
# colonne disparaît et le style avec elle. Page-level = permanent.


# ===========================================================================
# Action bar (breadcrumb + tracking strip)
# ===========================================================================

def _render_action_bar(biz: dict) -> None:
    """Sticky action bar avec breadcrumb + 3 cellules de tracking."""
    name = _safe_html(biz.get("name") or "Entreprise")
    city = _safe_html(biz.get("city") or biz.get("locality") or "—")
    status = biz.get("call_status") or "À appeler"
    last_call = biz.get("last_call_at") or "—"
    callback = biz.get("callback_date") or "—"

    # Pulse dot rouge si "À rappeler" (urgence), sinon ambre par défaut
    pulse_color = "#D33B3B" if status == "À rappeler" else "#B5740A"

    html = (
        '<div class="bd-root">'
        '<div class="bd-action-bar">'
        '<div class="bd-breadcrumb">'
        '<span>Prospects</span>'
        '<span>›</span>'
        f'<span>{city}</span>'
        '<span>›</span>'
        f'<span class="bd-current">{name}</span>'
        '</div>'
        '<div class="bd-tracking-strip">'
        '<div class="bd-tcell">'
        '<span class="bd-tcell-label">Statut</span>'
        '<span class="bd-tcell-value">'
        f'<span class="bd-pulse" style="background:{pulse_color};"></span>'
        f'{_safe_html(status)}</span></div>'
        '<div class="bd-tcell">'
        '<span class="bd-tcell-label">Dernier appel</span>'
        f'<span class="bd-tcell-value" style="color:#8C8AAE;">{_safe_html(last_call)}</span>'
        '</div>'
        '<div class="bd-tcell">'
        '<span class="bd-tcell-label">Rappel</span>'
        f'<span class="bd-tcell-value" style="color:#8C8AAE;">{_safe_html(callback)}</span>'
        '</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    _emit_html(html)


def _render_action_row(biz: dict) -> None:
    """Boutons Streamlit interactifs (Appeler + sélecteur statut)."""
    safe_key = (biz.get("dedup_key") or "_no").replace(":", "_").replace("|", "_")
    phone = biz.get("phone")
    status = biz.get("call_status") or "À appeler"

    a1, a2, _ = st.columns([2, 3, 7])
    with a1:
        # Scoped container → la règle CSS .st-key-bd-call-cta s'applique
        with st.container(key="bd-call-cta"):
            disabled = not phone or not is_configured()
            if st.button(
                "Appeler maintenant",
                key=f"bd_call_{safe_key}",
                width="stretch",
                disabled=disabled,
                help=("Click-to-call Ringover" if not disabled else
                      ("Pas de numéro" if not phone else "RINGOVER_API_KEY manquante")),
            ):
                res = click_to_call(phone)
                st.toast(res['message'],
                         icon=":material/call_made:" if res["ok"] else ":material/error:")
    with a2:
        status_key = f"bd_status_{safe_key}"
        if status_key not in st.session_state:
            st.session_state[status_key] = status

        def _on_change(_k=status_key, _d=biz.get("dedup_key")):
            new_val = st.session_state[_k]
            if _d and not _d.startswith("_no_"):
                update_call_fields(_d, call_status=new_val)
                st.toast(f"Statut : {new_val}", icon=":material/save:")

        st.selectbox(
            "Statut",
            CALL_STATUSES,
            index=CALL_STATUSES.index(status) if status in CALL_STATUSES else 0,
            key=status_key,
            on_change=_on_change,
            label_visibility="collapsed",
        )


# ===========================================================================
# Sidebar : identity card + dirigeants
# ===========================================================================

_ICON_PHONE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 '
    '19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 '
    '012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 '
    '006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>'
    '</svg>'
)
_ICON_MAIL = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>'
    '<polyline points="22,6 12,13 2,6"/></svg>'
)
_ICON_GLOBE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>'
    '<path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 '
    '01-4-10 15.3 15.3 0 014-10z"/></svg>'
)
_ICON_PIN = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">'
    '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>'
    '<circle cx="12" cy="10" r="3"/></svg>'
)
_ICON_TROPHY = (  # rank badge "Prospect N°X"
    '<svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">'
    '<path d="M6 9H4.5a2.5 2.5 0 010-5H6m12 5h1.5a2.5 2.5 0 000-5H18m-12 '
    '0v9a6 6 0 0012 0V4M8 22h8m-4-4v4" stroke="currentColor" stroke-width="2" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>'
)
_ICON_USERS = (  # dirigeants
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" width="14" height="14">'
    '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>'
    '<circle cx="9" cy="7" r="4"/>'
    '<path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>'
)
_ICON_TRENDING_UP = (  # santé financière
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" width="16" height="16">'
    '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>'
    '<polyline points="17 6 23 6 23 12"/></svg>'
)
_ICON_MAP_PIN_LARGE = (  # présence locale
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" width="16" height="16">'
    '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>'
    '<circle cx="12" cy="10" r="3"/></svg>'
)
_ICON_CHECK_BOX = (  # signaux qualifiants
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" width="16" height="16">'
    '<polyline points="9 11 12 14 22 4"/>'
    '<path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>'
)
_ICON_PHONE_LARGE = (  # empty state historique (64px)
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" width="26" height="26">'
    '<path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 '
    '19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 '
    '012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 '
    '006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z"/>'
    '</svg>'
)
_ICON_STAR = (  # rank badge
    '<svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12">'
    '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 '
    '5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>'
)


def _render_sidebar_identity(biz: dict) -> None:
    """Identity card de la sidebar : badge rang + nom + score + contact list."""
    name = _safe_html(biz.get("name") or "—")
    rank = biz.get("google_rank")
    form = _safe_html(biz.get("legal_form") or "")
    cat = _safe_html(biz.get("category") or "")
    city = _safe_html(biz.get("city") or biz.get("locality") or "")

    subtitle_parts = [s for s in [form, cat, f"{city}, BE" if city else ""] if s]
    subtitle = " · ".join(subtitle_parts)

    rating = biz.get("rating")
    reviews_count = biz.get("reviews_count") or 0

    # Calcul ancienneté à partir de creation_date (format "DD/MM/YYYY" ou "YYYY-MM-DD")
    annee_creation = None
    age = None
    cd = biz.get("creation_date") or ""
    import re as _re
    m = _re.search(r"(\d{4})", str(cd))
    if m:
        annee_creation = int(m.group(1))
        from datetime import datetime as _dt
        age = max(0, _dt.now().year - annee_creation)

    # ─── Construction HTML ───
    rank_html = ""
    if rank:
        suffix = "er" if rank == 1 else "e"
        rank_html = (
            f'<div class="bd-rank-badge">{_ICON_STAR}Prospect N°{rank}{suffix}</div>'
        )

    # Score panel
    score_html = ""
    if rating or age is not None:
        rating_block = ""
        if rating:
            try:
                stars = "★" * int(round(float(rating))) + "☆" * (5 - int(round(float(rating))))
            except (ValueError, TypeError):
                stars = ""
            rating_block = (
                '<div class="bd-score-block">'
                '<div class="bd-score-label">Réputation Google</div>'
                f'<div class="bd-score-value">{_safe_html(rating)} <small>/5</small></div>'
                f'<div class="bd-stars">{stars}</div>'
                f'<div class="bd-reviews-count">{reviews_count} avis</div>'
                '</div>'
            )
        age_block = ""
        if age is not None:
            age_block = (
                '<div class="bd-score-block">'
                '<div class="bd-score-label">Ancienneté</div>'
                f'<div class="bd-score-value">{age} <small>ans</small></div>'
                f'<div class="bd-reviews-count" style="margin-top:16px;">'
                f'depuis {annee_creation}</div>'
                '</div>'
            )
        if rating_block or age_block:
            score_html = (
                '<div class="bd-score-panel">'
                + rating_block + age_block +
                '</div>'
            )

    # Contact list
    contact_items = []
    phone = biz.get("phone")
    if phone:
        contact_items.append(
            f'<a href="tel:{_safe_html(phone)}" class="bd-contact-item">'
            f'<span class="bd-icon-pill">{_ICON_PHONE}</span>'
            '<div class="bd-contact-main">'
            '<div class="bd-contact-label">Téléphone</div>'
            f'<div class="bd-contact-value">{_safe_html(phone)}</div>'
            '</div></a>'
        )
    email = biz.get("email")
    if email:
        contact_items.append(
            f'<a href="mailto:{_safe_html(email)}" class="bd-contact-item">'
            f'<span class="bd-icon-pill">{_ICON_MAIL}</span>'
            '<div class="bd-contact-main">'
            '<div class="bd-contact-label">Email</div>'
            f'<div class="bd-contact-value">{_safe_html(email)}</div>'
            '</div></a>'
        )

    # Website block (avec bouton audit SEO juste après via Streamlit)
    website = biz.get("website")
    website_block = ""
    if website:
        url_display = website.replace("https://", "").replace("http://", "").rstrip("/")
        website_block = (
            '<div class="bd-website-block">'
            f'<a href="{_safe_html(website)}" target="_blank" class="bd-website-main">'
            f'<span class="bd-icon-pill">{_ICON_GLOBE}</span>'
            '<div class="bd-website-info">'
            '<div class="bd-contact-label">Site web</div>'
            f'<div class="bd-website-url">{_safe_html(url_display)}</div>'
            '</div></a>'
            '</div>'
        )

    # Adresse
    address = biz.get("address")
    address_block = ""
    if address:
        full_addr = address
        postal = biz.get("postal_code")
        locality = biz.get("locality") or biz.get("city")
        if postal and locality and postal not in str(address):
            full_addr = f"{address}, {postal} {locality}"
        address_block = (
            '<a href="#" class="bd-contact-item">'
            f'<span class="bd-icon-pill">{_ICON_PIN}</span>'
            '<div class="bd-contact-main">'
            '<div class="bd-contact-label">Adresse</div>'
            f'<div class="bd-contact-value">{_safe_html(full_addr)}</div>'
            '</div></a>'
        )

    contact_list_html = (
        '<div class="bd-contact-list">'
        + "".join(contact_items)
        + website_block
        + address_block +
        '</div>'
    )

    # AI footer
    ai_label = "non configurée"
    try:
        ai_label = ai_provider_label()
    except Exception:
        pass
    ai_footer = (
        '<div class="bd-ai-footer">'
        '<span class="bd-ai-dot"></span>'
        f'<span>Enrichissement IA · <strong style="color:#2C2A4A;">{_safe_html(ai_label)}</strong></span>'
        '</div>'
    )

    full_card = (
        '<div class="bd-root">'
        '<div class="bd-card">'
        '<div class="bd-identity">'
        + rank_html +
        f'<h1 class="bd-company-name">{name}</h1>'
        + (f'<p class="bd-company-form">{subtitle}</p>' if subtitle else '')
        + score_html
        + contact_list_html +
        '</div>'
        + ai_footer +
        '</div></div>'
    )
    _emit_html(full_card)

    # Bouton "Lancer l'audit SEO" en widget Streamlit natif (interactif)
    # Scopé via st.container key → règle CSS .st-key-bd-audit-cta s'applique
    if website:
        safe_key = (biz.get("dedup_key") or "_no").replace(":", "_").replace("|", "_")
        with st.container(key="bd-audit-cta"):
            if st.button(
                "Lancer l'audit SEO du site",
                key=f"bd_audit_{safe_key}",
                width="stretch",
            ):
                st.session_state[f"bd_audit_open_{safe_key}"] = True

        if st.session_state.get(f"bd_audit_open_{safe_key}"):
            with st.expander("Résultats audit SEO", expanded=True):
                _render_seo_audit_section(biz)


def _render_sidebar_dirigeants(biz: dict) -> None:
    """Carte Dirigeants avec avatars (initiales)."""
    managers_str = (biz.get("managers") or "").strip()
    if not managers_str:
        return

    # Split sur virgule / point-virgule / saut de ligne
    import re as _re
    names = [n.strip() for n in _re.split(r"[,;\n]+", managers_str) if n.strip()]
    if not names:
        return

    rows = []
    for full_name in names[:8]:  # max 8 dirigeants affichés
        # Initiales : 2 premières lettres de prénom + nom
        parts = full_name.split()
        if len(parts) >= 2:
            initials = (parts[0][:1] + parts[-1][:1]).upper()
        else:
            initials = full_name[:2].upper()
        rows.append(
            '<div class="bd-admin-row">'
            f'<div class="bd-admin-avatar">{_safe_html(initials)}</div>'
            '<div style="flex:1;min-width:0;">'
            f'<div class="bd-admin-name">{_safe_html(full_name)}</div>'
            '<div class="bd-admin-role">Administrateur</div>'
            '</div></div>'
        )

    html = (
        '<div class="bd-root">'
        '<div class="bd-card bd-admins">'
        f'<div class="bd-admins-title">{_ICON_USERS}<span>Dirigeants</span></div>'
        + "".join(rows) +
        '</div></div>'
    )
    _emit_html(html)


# ===========================================================================
# Main : 3 tabs (Évaluation / Identité légale / Historique)
# ===========================================================================

def _render_eval_panel(biz: dict) -> None:
    """Onglet Évaluation : briefing IA + 3 eval-cards (financier, local, signaux)."""
    # Briefing IA en premier (action principale du commercial)
    _render_ai_briefing_section(biz)

    # 3 eval-cards
    BCE_STATUS = "Actif" if (biz.get("bce_status") or "").lower() in ("", "actif", "active") else (biz.get("bce_status") or "—")

    # Carte 1 : Santé financière
    fin_rows = []
    if biz.get("establishments_count"):
        fin_rows.append(("🏢 Établissements actifs", str(biz["establishments_count"])))
    if biz.get("creation_date"):
        fin_rows.append(("⏱ Activité depuis", _safe_html(biz["creation_date"])))
    fin_rows.append(("✓ Statut BCE", f'<span class="bd-status-pill bd-pill-green">{_safe_html(BCE_STATUS)}</span>'))
    if biz.get("nbb_revenue"):
        fin_rows.append(("💰 Chiffre d'affaires", _safe_html(biz["nbb_revenue"])))
    if biz.get("nbb_equity"):
        fin_rows.append(("💼 Fonds propres", _safe_html(biz["nbb_equity"])))
    if biz.get("nbb_employees"):
        fin_rows.append(("👥 Effectif", _safe_html(biz["nbb_employees"])))

    fin_html = (
        '<div class="bd-eval-card">'
        '<div class="bd-eval-head">'
        f'<div class="bd-eval-icon" style="background:#E6F7EE;color:#0F9D58;">{_ICON_TRENDING_UP}</div>'
        '<div><div class="bd-eval-title">Santé financière</div>'
        '<div class="bd-eval-sub">Sources officielles BNB</div></div>'
        '</div>'
        + "".join(
            f'<div class="bd-stat-row"><span class="bd-stat-label">{label}</span>'
            f'<span class="bd-stat-value">{value}</span></div>'
            for label, value in fin_rows
        )
    )
    if biz.get("nbb_url"):
        fin_html += (
            f'<a href="{_safe_html(biz["nbb_url"])}" target="_blank" class="bd-ext-link">'
            '<span class="bd-ext-icon">📄</span>'
            '<div class="bd-ext-main">'
            '<div class="bd-ext-title">Comptes annuels BNB</div>'
            '<div class="bd-ext-sub">Banque Nationale de Belgique</div></div></a>'
        )
    if biz.get("companyweb_url"):
        fin_html += (
            f'<a href="{_safe_html(biz["companyweb_url"])}" target="_blank" class="bd-ext-link">'
            '<span class="bd-ext-icon">📊</span>'
            '<div class="bd-ext-main">'
            '<div class="bd-ext-title">Fiche CompanyWeb</div>'
            '<div class="bd-ext-sub">Score crédit & indicateurs</div></div></a>'
        )
    fin_html += '</div>'

    # Carte 2 : Présence locale
    loc_rows = []
    if biz.get("locality") or biz.get("city"):
        city_label = biz.get("locality") or biz.get("city")
        if biz.get("postal_code"):
            city_label = f"{city_label} ({biz['postal_code']})"
        loc_rows.append(("📍 Ville", _safe_html(city_label)))
    loc_rows.append(("🌍 Pays", "Belgique"))
    if biz.get("category"):
        loc_rows.append(("🗂 Catégorie Google", _safe_html(biz["category"])))
    if biz.get("hours"):
        loc_rows.append(("🕐 Horaires", _safe_html(biz["hours"][:60] + ("…" if len(biz["hours"]) > 60 else ""))))

    loc_html = (
        '<div class="bd-eval-card">'
        '<div class="bd-eval-head">'
        f'<div class="bd-eval-icon" style="background:#FFF6E5;color:#B5740A;">{_ICON_MAP_PIN_LARGE}</div>'
        '<div><div class="bd-eval-title">Présence locale</div>'
        '<div class="bd-eval-sub">Localisation & catégorie</div></div>'
        '</div>'
        + "".join(
            f'<div class="bd-stat-row"><span class="bd-stat-label">{label}</span>'
            f'<span class="bd-stat-value">{value}</span></div>'
            for label, value in loc_rows
        )
    )
    if biz.get("gmaps_url"):
        loc_html += (
            f'<a href="{_safe_html(biz["gmaps_url"])}" target="_blank" class="bd-ext-link">'
            '<span class="bd-ext-icon">🗺</span>'
            '<div class="bd-ext-main">'
            '<div class="bd-ext-title">Voir sur Google Maps</div>'
            '<div class="bd-ext-sub">Localisation, photos & itinéraire</div></div></a>'
        )
    loc_html += '</div>'

    # Carte 3 : Signaux qualifiants (full width)
    nace_count = len((biz.get("nace_activities") or "").split(";"))
    nace_count = max(1, nace_count) if biz.get("nace_activities") else 0
    reviews = biz.get("reviews_count") or 0
    website_ok = bool(biz.get("website"))

    signaux_data = []
    if reviews:
        avis_label = "Activité visible" if reviews >= 10 else "Peu d'avis"
        signaux_data.append(("Volume d'avis", f"{reviews} avis · {avis_label}"))
    # Age (re-calculé)
    cd = biz.get("creation_date") or ""
    import re as _re
    m = _re.search(r"(\d{4})", str(cd))
    if m:
        from datetime import datetime as _dt
        age = max(0, _dt.now().year - int(m.group(1)))
        stab = "Activité stable" if age >= 3 else "Récente"
        signaux_data.append(("Ancienneté", f"{age} ans · {stab}"))
    if website_ok:
        signaux_data.append(("Site web actif", '<span style="color:#0F9D58;">Oui · digitalement présent</span>'))
    else:
        signaux_data.append(("Site web", '<span style="color:#D33B3B;">Pas de site · opportunité</span>'))
    if nace_count > 0:
        signaux_data.append(("Diversification", f"{nace_count} activité{'s' if nace_count > 1 else ''} NACE"))

    signaux_html = (
        '<div class="bd-eval-card bd-eval-card--full">'
        '<div class="bd-eval-head">'
        f'<div class="bd-eval-icon" style="background:#F5F4FF;color:#3425AF;">{_ICON_CHECK_BOX}</div>'
        '<div><div class="bd-eval-title">Signaux qualifiants</div>'
        '<div class="bd-eval-sub">Pourquoi ce prospect mérite votre attention</div></div>'
        '</div>'
        '<div class="bd-data-grid">'
        + "".join(
            f'<div class="bd-data-row"><span class="bd-data-label">{label}</span>'
            f'<span class="bd-data-value">{value}</span></div>'
            for label, value in signaux_data
        ) +
        '</div></div>'
    )

    _emit_html(
        '<div class="bd-root"><div class="bd-eval-grid">'
        + fin_html + loc_html + signaux_html +
        '</div></div>'
    )


def _render_legal_panel(biz: dict) -> None:
    """Onglet Identité légale : 3 expanders (données, NACE, sources)."""
    with st.expander("Données légales & immatriculation", expanded=True):
        rows = []
        if biz.get("vat_number"):
            rows.append(("Numéro TVA", f'<span class="bd-mono">{_safe_html(biz["vat_number"])}</span>'))
        if biz.get("bce_number"):
            rows.append(("Numéro BCE", f'<span class="bd-mono">{_safe_html(biz["bce_number"])}</span>'))
        if biz.get("legal_form"):
            rows.append(("Forme juridique", _safe_html(biz["legal_form"])))
        if biz.get("creation_date"):
            rows.append(("Date de création", _safe_html(biz["creation_date"])))
        if biz.get("capital"):
            rows.append(("Capital", _safe_html(biz["capital"])))
        if rows:
            _emit_html(
                '<div class="bd-root"><div class="bd-data-grid">'
                + "".join(
                    f'<div class="bd-data-row"><span class="bd-data-label">{label}</span>'
                    f'<span class="bd-data-value">{value}</span></div>'
                    for label, value in rows
                )
                + '</div></div>'
            )
        else:
            st.caption("Aucune donnée légale disponible.")

    with st.expander("Codes d'activité NACE", expanded=True):
        nace = (biz.get("nace_activities") or "").strip()
        if nace:
            # Format attendu : "43.410 - Travaux de couverture; 41.002 - Construction..."
            import re as _re
            entries = [e.strip() for e in _re.split(r"[;\n]+", nace) if e.strip()]
            chips = []
            for entry in entries:
                m = _re.match(r"^\s*([\d.]+)\s*[-–]?\s*(.*)$", entry)
                if m:
                    code, label = m.group(1), m.group(2).strip()
                else:
                    code, label = "", entry
                chips.append(
                    '<div class="bd-nace-chip">'
                    + (f'<span class="bd-nace-code">{_safe_html(code)}</span>' if code else "")
                    + f'<span>{_safe_html(label)}</span></div>'
                )
            _emit_html(
                '<div class="bd-root">'
                + "".join(chips) +
                '</div>'
            )
        else:
            st.caption("Aucun code NACE renseigné.")

    if biz.get("nbb_url") or biz.get("companyweb_url"):
        with st.expander("Sources officielles", expanded=False):
            html_parts = ['<div class="bd-root">']
            if biz.get("nbb_url"):
                html_parts.append(
                    f'<a href="{_safe_html(biz["nbb_url"])}" target="_blank" class="bd-ext-link">'
                    '<span class="bd-ext-icon">📄</span>'
                    '<div class="bd-ext-main">'
                    '<div class="bd-ext-title">Comptes annuels BNB</div>'
                    '<div class="bd-ext-sub">consult.cbso.nbb.be</div></div></a>'
                )
            if biz.get("companyweb_url"):
                html_parts.append(
                    f'<a href="{_safe_html(biz["companyweb_url"])}" target="_blank" class="bd-ext-link">'
                    '<span class="bd-ext-icon">📊</span>'
                    '<div class="bd-ext-main">'
                    '<div class="bd-ext-title">Fiche CompanyWeb</div>'
                    '<div class="bd-ext-sub">companyweb.be</div></div></a>'
                )
            html_parts.append('</div>')
            _emit_html("".join(html_parts))


def _render_history_panel(biz: dict) -> None:
    """Onglet Historique : notes + métriques OU empty state."""
    last_call = biz.get("last_call_at")
    callback = biz.get("callback_date")
    notes = (biz.get("call_notes") or "").strip()
    has_history = bool(last_call or callback or notes)

    if not has_history:
        name = _safe_html(biz.get("name") or "cette entreprise")
        _emit_html(
            '<div class="bd-root"><div class="bd-eval-card">'
            '<div class="bd-empty">'
            f'<div class="bd-empty-icon">{_ICON_PHONE_LARGE}</div>'
            '<div class="bd-empty-title">Aucun appel pour l\'instant</div>'
            f'<div class="bd-empty-text">L\'historique d\'appels, notes et rappels '
            f'apparaîtra ici dès le premier contact avec {name}.</div>'
            '</div></div></div>'
        )
        return

    cn1, cn2, cn3 = st.columns(3)
    cn1.metric("Statut", biz.get("call_status") or "À appeler")
    cn2.metric("Dernier appel", last_call or "—")
    cn3.metric("Rappel prévu", callback or "—")
    if notes:
        st.info(notes, icon=":material/sticky_note_2:")


def render_business_card(biz: dict, key_suffix: str = "") -> None:
    """Rend une carte entreprise avec actions (appeler, détails, changer le statut)."""
    rank = biz.get("google_rank")
    status = biz.get("call_status") or "À appeler"
    dedup = biz.get("dedup_key") or f"_no_{key_suffix}"
    safe_key = dedup.replace(":", "_").replace("|", "_").replace(" ", "_")

    with st.container(border=True):
        # En-tête : nom + badges
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:0.6rem;'>"
            f"<div style='font-weight:700;font-size:1.02rem;line-height:1.3;color:#0f172a;'>"
            f"{biz.get('name') or '—'}</div>"
            f"<div style='white-space:nowrap;'>{_rank_badge_html(rank)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        cat = biz.get("category") or ""
        loc = biz.get("locality") or biz.get("city") or ""
        sub = " · ".join([s for s in [cat, loc] if s])
        if sub:
            st.caption(sub)

        st.markdown(_status_chip_html(status), unsafe_allow_html=True)

        # Bloc d'infos compactes
        BRAND = "#7c3aed"
        GOLD = "#f59e0b"
        lines = []
        if biz.get("phone"):
            lines.append(
                f"{lucide('phone', 14, BRAND)} "
                f"<a href='tel:{biz['phone']}' style='color:#0f172a;text-decoration:none;'>{biz['phone']}</a>"
            )
        if biz.get("email"):
            lines.append(
                f"{lucide('mail', 14, BRAND)} "
                f"<a href='mailto:{biz['email']}' style='color:#0f172a;text-decoration:none;'>{biz['email']}</a>"
            )
        if biz.get("vat_number"):
            lines.append(
                f"{lucide('briefcase', 14, BRAND)} "
                f"<code style='font-size:0.8rem;'>{biz['vat_number']}</code>"
            )
        if biz.get("managers"):
            mgr = biz['managers'][:60] + ("…" if len(biz['managers']) > 60 else "")
            lines.append(f"{lucide('users', 14, BRAND)} {mgr}")
        if biz.get("rating"):
            lines.append(
                f"{lucide('star', 14, GOLD)} <strong>{biz['rating']}</strong> "
                f"<span style='color:#64748b;'>({biz.get('reviews_count') or 0} avis)</span>"
            )
        if lines:
            st.markdown(
                "<div style='font-size:0.85rem;line-height:1.85;color:#334155;'>"
                + "<br>".join(lines) + "</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

        # Actions
        b1, b2 = st.columns(2)
        with b1:
            phone = biz.get("phone")
            call_disabled = not phone or not is_configured()
            if st.button(
                "Appeler",
                key=f"call_{safe_key}",
                width="stretch",
                disabled=call_disabled,
                help="Click-to-call Ringover" if not call_disabled else
                     ("Pas de numéro" if not phone else "Configure RINGOVER_API_KEY"),
            ):
                res = click_to_call(phone)
                if res["ok"]:
                    st.toast(res['message'], icon=":material/call_made:")
                else:
                    st.toast(res['message'], icon=":material/error:")
        with b2:
            if st.button("Détails", key=f"det_{safe_key}", width="stretch"):
                show_business_details(biz)

        # Changement de statut (selectbox)
        status_key = f"st_{safe_key}"
        if status_key not in st.session_state:
            st.session_state[status_key] = status

        def _on_status_change(_k=status_key, _d=dedup):
            new_val = st.session_state[_k]
            if _d and not _d.startswith("_no_"):
                update_call_fields(_d, call_status=new_val)
                st.toast(f"Statut : {new_val}", icon=":material/save:")

        st.selectbox(
            "Statut",
            CALL_STATUSES,
            index=CALL_STATUSES.index(status) if status in CALL_STATUSES else 0,
            key=status_key,
            on_change=_on_status_change,
            label_visibility="collapsed",
        )


def render_card_grid(businesses: list[dict], columns: int = 3, key_prefix: str = "") -> None:
    if not businesses:
        return
    cols = st.columns(columns)
    for i, biz in enumerate(businesses):
        with cols[i % columns]:
            render_business_card(biz, key_suffix=f"{key_prefix}_{i}")


def _init_state():
    defaults = {
        "results": [], "dropped": [], "skipped": [], "log": [],
        "last_run": None,
        "last_search_id": None,
        "selected_search_id": None,
        # Champs vides par défaut : l'utilisateur démarre toujours sur un
        # formulaire propre. Évite les recherches involontaires sur les villes
        # / métiers laissés là par accident.
        "preset_query": "",
        "preset_cities": "",
        "scrape_state": init_scrape_state(),
        # Cache des variantes IA par métier custom (évite de re-appeler l'API
        # à chaque rerun Streamlit). Reset au refresh complet de l'app.
        "ai_variants_cache": {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()

# ===========================================================================
# CSS premium fiche détail — injecté AU NIVEAU PAGE (pas dans une colonne)
# ===========================================================================
# Le CSS DOIT être injecté à ce niveau (top-level) et PAS dans
# show_business_details() — sinon il finit scopé au DOM de la colonne du
# bouton « Détails » qui a été cliqué, et disparaît au prochain clic sur
# une autre fiche.
#
# On utilise _emit_html (qui wrappe st.html avec fallback) car le sanitizer
# de markdown escape certaines balises et peut afficher le CSS en texte brut.
# st.html() injecte le HTML tel quel sans sanitization.
#
# Conséquence : les overrides Streamlit (tabs/expanders) s'appliquent
# globalement à toute l'app, ce qui est volontaire (design system cohérent).
_emit_html(_BUSINESS_DETAIL_CSS)


# ===========================================================================
# TOPBAR (logo + sub + quota) — style template Oui Allo
# ===========================================================================
import base64 as _b64

_logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")
_logo_html = ""
if os.path.exists(_logo_path):
    with open(_logo_path, "rb") as _f:
        _logo_b64 = _b64.b64encode(_f.read()).decode("ascii")
    _logo_html = f'<img src="data:image/png;base64,{_logo_b64}" alt="Oui Allo" />'
else:
    _logo_html = (
        '<span style="font-family:var(--font-display);font-size:1.4rem;'
        'font-weight:700;color:var(--brand-600);">Oui Allo</span>'
    )

_stats = history_stats()

st.markdown(
    f'<header class="topbar">'
    f'<div class="topbar-brand">{_logo_html}'
    f'<span class="topbar-sub">Prospection B2B</span></div>'
    f'<div class="topbar-right">'
    f'<div class="topbar-quota">'
    f'<span class="topbar-quota-dot"></span>'
    f'Base prospects · <strong>{_stats.get("businesses", 0)}</strong>&nbsp;entreprises'
    f'</div></div>'
    f'</header>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <section class="hero">
        <div class="hero-text">
            <span class="eyebrow">Génération de prospects</span>
            <h1>Construis une liste de prospects <em>qualifiée</em>, en quelques minutes.</h1>
            <p>Lance une recherche par métier sur les communes ciblées. Les fiches enrichies —
            coordonnées, site, numéro de TVA — sont exportables au format Ringover en un clic.</p>
        </div>
        <div class="hero-stats">
            <div>
                <div class="hero-stat-label">Recherches</div>
                <div class="hero-stat-value">{_stats.get('searches', 0)}</div>
            </div>
            <div>
                <div class="hero-stat-label">Prospects en base</div>
                <div class="hero-stat-value">{_stats.get('businesses', 0)}</div>
            </div>
            <div>
                <div class="hero-stat-label">Avec TVA</div>
                <div class="hero-stat-value">{_stats.get('with_vat', 0)}</div>
            </div>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)


# ===========================================================================
# FORM CARD (card blanche centrale, style Oui Allo)
# ===========================================================================
with st.container(border=True):
    st.markdown(
        '<div class="form-card-header">'
        '<div>'
        '<div class="form-card-title">Nouvelle recherche</div>'
        '<div class="form-card-subtitle">Définis les métiers, les zones et les options d\'enrichissement.</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # --- MÉTIERS (multi) ---
    COMMON_METIERS = [
        "opticien", "audioprothésiste", "orthopédiste", "ostéopathe",
        "dentiste", "kinésithérapeute", "pharmacie",
        "plombier", "électricien", "chauffagiste", "menuisier",
        "garage automobile", "carrosserie",
        "restaurant", "boulangerie", "boucherie", "fleuriste",
        "coiffeur", "esthéticienne", "salon de beauté",
        "avocat", "comptable", "notaire", "agent immobilier",
    ]
    selected_metiers = st.multiselect(
        "Métiers ciblés",
        options=sorted(set(COMMON_METIERS)),
        default=[],
        placeholder="Choisis un ou plusieurs métiers (ou tape pour chercher)…",
        help="Chaque métier déclenche une recherche sur chaque commune. "
             "Pour un métier non listé, ajoute-le dans le champ Métier(s) personnalisé(s) ci-dessous.",
    )
    custom_metiers_raw = st.text_input(
        "Métier(s) personnalisé(s) (séparés par virgule)",
        value="",
        placeholder="ex : magasin de vélos, salle de sport, traiteur",
    )
    custom_metiers = [m.strip() for m in custom_metiers_raw.split(",") if m.strip()]
    metiers_base = list(dict.fromkeys(selected_metiers + custom_metiers))  # dédup, ordre conservé

    # Toggle : étendre chaque métier avec ses synonymes (ex. opticien → lunetterie,
    # magasin de lunettes, optique). Multiplie le rendement Google Maps mais aussi
    # le temps de scrape.
    use_synonyms = st.toggle(
        "Inclure les variantes du métier (recommandé)",
        value=True,
        help="Pour chaque métier, lance aussi les recherches sur ses synonymes "
             "(ex. opticien → lunetterie, magasin de lunettes…). Multiplie typiquement "
             "le nombre de prospects trouvés par 2-3.",
    )

    # Variantes statiques (dict METIER_SYNONYMS) pour les métiers connus
    metiers_static = expand_metier_synonyms(metiers_base, enabled=use_synonyms)

    # ── Variantes IA pour les métiers PERSONNALISÉS (non présents dans le dict) ──
    # Si l'utilisateur a tapé un métier custom et que le toggle est ON, on
    # propose un bouton "Proposer des variantes IA". Les variantes générées
    # sont mises en cache (st.session_state.ai_variants_cache) pour ne pas
    # re-appeler l'API à chaque rerun. L'user peut éditer/cocher/décocher.
    custom_with_no_static_variants = [
        m for m in custom_metiers
        if expand_metier_synonyms([m], enabled=True) == [m]  # 1 seule = pas de synonymes dans le dict
    ]

    ai_extra_variants: list[str] = []
    if use_synonyms and custom_with_no_static_variants:
        with st.container(border=True):
            st.markdown(
                "<div style='font-size:0.82rem;font-weight:600;margin-bottom:6px;'>"
                "Variantes IA pour vos métiers personnalisés</div>",
                unsafe_allow_html=True,
            )
            ai_ok = ai_synonyms.is_configured()
            if not ai_ok:
                st.caption(
                    "ℹ Aucune clé IA configurée (OPENAI_API_KEY ou ANTHROPIC_API_KEY). "
                    "Les métiers personnalisés seront scrapés tels quels, sans variantes."
                )
            for m in custom_with_no_static_variants:
                cache_key = m.lower().strip()
                cached = st.session_state.ai_variants_cache.get(cache_key)
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**« {m} »**", help=f"Métier personnalisé : {m}")
                with c2:
                    if st.button(
                        ("Régénérer" if cached else "Proposer"),
                        key=f"ai_var_{cache_key}",
                        disabled=not ai_ok,
                        width="stretch",
                    ):
                        with st.spinner(f"Génération variantes pour « {m} »…"):
                            res = ai_synonyms.suggest_variants(m)
                        if res["ok"]:
                            st.session_state.ai_variants_cache[cache_key] = res["variants"]
                            cached = res["variants"]
                        else:
                            st.error(f"Échec : {res['message']}")

                if cached:
                    # Pré-sélection : toutes les variantes cochées par défaut
                    state_sel_key = f"ai_var_sel_{cache_key}"
                    if state_sel_key not in st.session_state:
                        st.session_state[state_sel_key] = list(cached)
                    sel = st.multiselect(
                        f"Variantes pour « {m} » (décocher pour exclure)",
                        options=cached,
                        default=st.session_state[state_sel_key],
                        key=state_sel_key,
                        label_visibility="collapsed",
                    )
                    # Métier d'origine ajouté ailleurs (déjà dans metiers_base)
                    # → on ne garde ici que les VARIANTES (≠ métier d'origine)
                    extra = [v for v in sel if v.lower() != m.lower()]
                    ai_extra_variants.extend(extra)

    # Concaténation finale : statiques + IA (avec dédup case-insensitive
    # tout en conservant l'ordre d'apparition)
    metiers = list(metiers_static)
    seen_lower = {v.lower() for v in metiers}
    for v in ai_extra_variants:
        if v.lower() not in seen_lower:
            seen_lower.add(v.lower())
            metiers.append(v)

    if use_synonyms and len(metiers) > len(metiers_base):
        st.caption(
            f"**{len(metiers_base)} métier(s) saisi(s)** → **{len(metiers)} requêtes** "
            f"après expansion synonymes : `{', '.join(metiers[:6])}"
            f"{('…' if len(metiers) > 6 else '')}`"
        )

    # --- ZONE DE PROSPECTION ---
    st.markdown("")
    st.markdown(
        '<div style="font-size:0.82rem;font-weight:600;color:var(--ink);margin-bottom:6px;">'
        'Zone de prospection</div>',
        unsafe_allow_html=True,
    )
    ZONE_MODES = ["Par arrondissement", "Par commune", "Par rayon"]
    try:
        zone_mode = st.segmented_control(
            "Mode",
            options=ZONE_MODES,
            default=None,  # aucun mode pré-sélectionné
            label_visibility="collapsed",
            key="zone_mode",
        )
    except AttributeError:
        zone_mode = st.radio(
            "Mode",
            options=ZONE_MODES,
            horizontal=True,
            label_visibility="collapsed",
            key="zone_mode",
        )

    cities: list[str] = []
    selected_arrondissements: list[str] = []
    if zone_mode == "Par arrondissement":
        arr_options: list[str] = []
        label_to_arr: dict[str, str] = {}
        for prov in PROVINCES:
            for name, info in ARRONDISSEMENTS.items():
                if info["province"] == prov:
                    label = f"{prov} · {name}  ({len(info['communes'])} communes)"
                    arr_options.append(label)
                    label_to_arr[label] = name

        selected_labels = st.multiselect(
            "Arrondissements à scraper",
            options=arr_options,
            default=[],
            placeholder="Tape une province ou un arrondissement…",
        )
        selected_arrondissements = [label_to_arr[lab] for lab in selected_labels]
        cities = expand_arrondissements_to_communes(selected_arrondissements)
        if cities:
            st.caption(
                f"**{len(selected_arrondissements)} arrondissement(s)** sélectionné(s) "
                f"· **{len(cities)} communes** au total"
            )
        else:
            st.caption("Aucun arrondissement sélectionné.")
    elif zone_mode == "Par commune":
        cities_raw = st.text_area(
            "Communes ciblées (une par ligne)",
            value=st.session_state.preset_cities,
            height=120,
            placeholder="Waterloo\nBraine-l'Alleud\nNivelles\nLa Hulpe\nHalle",
        )
        cities = [c.strip() for c in cities_raw.splitlines() if c.strip()]
        if cities:
            st.caption(f"**{len(cities)} commune(s)** ciblée(s)")
    elif zone_mode == "Par rayon":
        # Sélection d'une ville centrale + slider rayon → calcul Haversine
        # sur le dataset BELGIAN_COMMUNE_COORDS (~150 communes principales).
        # Les communes non géocodées (datasets manquants) ne peuvent pas être
        # incluses dans ce mode — bascule "Par commune" si besoin.
        known_communes = all_known_commune_names()
        r1, r2 = st.columns([2, 1])
        with r1:
            center_city = st.selectbox(
                "Ville centrale",
                options=[""] + known_communes,
                index=0,
                placeholder="Choisis une ville centrale…",
                help=f"{len(known_communes)} communes géolocalisées disponibles. "
                     "Pour une commune absente de la liste, utilise le mode « Par commune ».",
            )
        with r2:
            radius_km = st.slider(
                "Rayon (km)",
                min_value=2,
                max_value=50,
                value=10,
                step=1,
                help="Toutes les communes belges connues à moins de X km du centre.",
            )
        if center_city:
            in_radius = communes_within_radius(center_city, radius_km)
            cities = [name for name, _ in in_radius]
            if cities:
                preview = ", ".join(
                    f"{name} ({dist:.1f} km)" for name, dist in in_radius[:5]
                )
                more = f" + {len(cities) - 5} autres" if len(cities) > 5 else ""
                st.caption(
                    f"**{len(cities)} commune(s)** dans un rayon de "
                    f"{radius_km} km autour de **{center_city}** : {preview}{more}"
                )
            else:
                st.warning(
                    f"Aucune commune connue à moins de {radius_km} km de "
                    f"« {center_city} ». Augmente le rayon ou essaie une autre ville."
                )
        else:
            st.caption("Choisis une ville centrale pour calculer le rayon.")

    # --- PARAMÈTRES (3 cards) ---
    st.markdown("")
    p1, p2, p3 = st.columns(3)

    with p1:
        with st.container(border=True):
            st.markdown("**Enrichissement TVA**")
            do_vat = st.toggle("Activer l'enrichissement TVA", value=True, key="t_vat")
            st.caption("Sources :")
            do_website_vat = st.checkbox("Site web (mentions légales)",
                                          value=True, disabled=not do_vat, key="cb_web_vat")
            do_kbo = st.checkbox("Registre KBO / BCE",
                                  value=True, disabled=not do_vat, key="cb_kbo")
            do_bce = st.checkbox("Détail BCE (dirigeants, NACE)",
                                  value=True, disabled=not do_vat, key="cb_bce")

    with p2:
        with st.container(border=True):
            st.markdown("**Qualité des fiches**")
            strict_city = st.toggle("Filtrage strict par ville", value=True,
                                    help="Élimine les fiches hors de la ville recherchée.")
            exclude_seen = st.toggle("Exclure entreprises déjà trouvées", value=True,
                                      help="Ignore les fiches déjà présentes dans l'historique.")
            require_phone = st.checkbox("Téléphone obligatoire", value=False,
                                         help="N'inclut que les fiches avec un numéro.")

    with p3:
        with st.container(border=True):
            st.markdown("**Volumes & enrichissements**")
            unlimited = st.toggle("Tout récupérer (sans limite)", value=False,
                                  help="Scrape jusqu'à ce que Google Maps n'en montre plus.")
            if unlimited:
                max_per_city = 500
                st.caption("Limite Google ~120/commune")
            else:
                max_per_city = st.slider("Max par commune", 5, 100, 20, 5)
            do_fin = st.toggle("Données financières (BNB, CompanyWeb)", value=True)

    # --- AVANCÉ ---
    with st.expander("Paramètres avancés"):
        a1, a2 = st.columns(2)
        with a1:
            headless = st.checkbox("Navigateur invisible (headless)", value=True)
        with a2:
            workers = st.slider("Workers parallèles (enrichissement)", 1, 10, 6)

    # --- FOOTER : estimate + submit ---
    st.markdown("")
    nb_combos = len(metiers) * len(cities)
    cap = 30 if unlimited else min(max_per_city, 30)

    # Estimation réaliste sous forme de FOURCHETTE :
    # - haut (optimiste) : Google donne ~70 % du cap, peu de pertes
    # - bas (pessimiste) : ~30 % après filtre ville strict + dédup + filtre tél
    yield_high = 0.65 if strict_city else 0.80
    yield_low = 0.25 if strict_city else 0.40
    if require_phone:
        yield_high *= 0.85
        yield_low *= 0.85
    estimate_high = int(nb_combos * cap * yield_high)
    estimate_low = int(nb_combos * cap * yield_low)

    # Estimation temps : ~5-8 s par fiche scrapée (incluant l'enrichissement parallèle)
    raw_fiches = int(nb_combos * cap * 0.7)
    time_min = max(1, int(raw_fiches * 6 / 60))

    foot1, foot2 = st.columns([2, 1])
    with foot1:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;">'
            f'<div>'
            f'<div class="estimate-num">{estimate_low}–{estimate_high}</div>'
            f'<div class="estimate-label">prospects estimés · ~{time_min} min '
            f'· {len(metiers)} requête(s) × {len(cities)} commune(s) '
            f'<span style="opacity:0.6;">'
            f'({"strict" if strict_city else "tolérant"}'
            f'{", tel obligatoire" if require_phone else ""})</span></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    # État scrape en cours
    _scrape_active = st.session_state.scrape_state.get("active", False)

    with foot2:
        if _scrape_active:
            # Pendant un scrape, "Lancer" est remplacé par "Annuler"
            if st.button("Annuler la recherche", type="secondary",
                         width="stretch", key="cancel_btn"):
                request_cancel(st.session_state.scrape_state)
                st.rerun()
            run = False
        else:
            run = st.button(
                "Lancer la recherche", type="primary", width="stretch",
                disabled=not (metiers and cities),
            )

    # ⛔ Bandeau d'alerte "Google a bloqué l'IP" — rendu AVANT le panel de
    # progression pour être ultra-visible (rouge, en haut). Persiste tant que
    # state["google_blocked"] est True (peut être effacé en relançant un scrape
    # qui réussit, ce qui reset le flag dans init_scrape_state).
    google_block_slot = st.empty()

    # Panneau de progression — placé À L'INTÉRIEUR de la form-card, en dessous du bouton
    progress_slot = st.empty()

st.markdown("")


tab_results, tab_campaign, tab_dropped, tab_history, tab_help = st.tabs(
    ["Résultats", "Campagne d'appels", "Hors zone", "Historique", "Aide"]
)


def log(msg: str) -> None:
    st.session_state.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ===========================================================================
# Rendu du panel de progression à partir de st.session_state.scrape_state.
# Le thread écrit dans ce state, le main thread relit et rend l'UI à chaque
# rerun. Aucune logique de scraping ici.
# ===========================================================================

def _format_duration(started_at, ended_at=None) -> str:
    if not started_at:
        return ""
    end = ended_at or datetime.now()
    secs = int((end - started_at).total_seconds())
    mins, s = divmod(secs, 60)
    return f"{mins} min {s:02d} s" if mins else f"{s} s"


def _render_progress_panel(slot, state: dict) -> None:
    """Rend le panel sombre 'Recherche en cours' depuis le scrape_state."""
    # 2 compteurs distincts : villes (1 par commune) vs variantes (1 par
    # couple variante × ville). Ex : Waterloo × dentiste expansé en 4 →
    # cities = 1, variants = 4. La barre de progression utilise variants
    # (granularité la plus fine pour une animation fluide).
    cities_done = state.get("cities_done", 0)
    cities_total = max(state.get("cities_total", 1), 1)
    variants_done = state.get("variants_done", 0)
    variants_total = max(state.get("variants_total", 1), 1)
    pct = min(100, int(100 * variants_done / variants_total))
    prospects = state.get("prospects_found", 0)
    vat = state.get("vat_enriched", 0)
    last_log = _safe_html(state.get("last_log") or "")

    # ETA estimée sur la granularité variantes (plus précise que par ville)
    started = state.get("started_at")
    if started and variants_done > 0:
        elapsed = (datetime.now() - started).total_seconds()
        per_unit = elapsed / variants_done
        eta_sec = max(0, int(per_unit * (variants_total - variants_done)))
        eta_mins, eta_s = divmod(eta_sec, 60)
        eta_html = (f"{eta_mins}<span class='pp-sm'>min {eta_s:02d} s</span>"
                    if eta_mins else f"{eta_s}<span class='pp-sm'>sec</span>")
    else:
        eta_html = "<span class='pp-sm'>—</span>"

    phase_labels = {
        PHASE_SCRAPING: "Scraping Google Maps",
        PHASE_FILTERING: "Filtre ville",
        PHASE_DEDUP_SEEN: "Dédup historique",
        PHASE_ENRICHMENT: "Enrichissement TVA / BCE",
        PHASE_DEDUP_POST: "Dédup post-BCE",
        PHASE_SAVING: "Sauvegarde",
    }
    phase_text = phase_labels.get(state.get("phase"), "En cours")
    metiers = state.get("metiers") or []
    cities = state.get("cities") or []
    meta = (f"Phase : {phase_text} · Lancée il y a "
            f"{_format_duration(started)} · {len(cities)} ville(s) × "
            f"{len(metiers)} variante(s) métier")

    # 2 compteurs distincts : bruts (monotone) vs après filtres (décroît)
    brut = state.get("prospects_brut", 0)
    found_html = (
        f'<span class="pp-value">{prospects}</span>'
        if prospects == brut
        else f'<span class="pp-value">{prospects}</span>'
             f'<span class="pp-sm" style="color:rgba(255,255,255,0.55);">/ {brut} bruts</span>'
    )

    # ℹ Avertissement : les chiffres affichés pendant le scrape sont des
    # snapshots intermédiaires (prospects_brut grimpe, prospects_found et
    # variants_done évoluent, ETA est extrapolée). Les valeurs définitives
    # apparaissent dans le panel "Terminé" à la fin.
    estimation_banner = (
        '<div style="display:flex;align-items:center;gap:0.5rem;'
        'padding:0.55rem 0.85rem;margin:0.4rem 0 0.9rem;'
        'background:rgba(255,255,255,0.08);border-left:3px solid #FFC857;'
        'border-radius:6px;font-size:0.74rem;color:rgba(255,255,255,0.85);">'
        '<span style="font-size:0.95rem;">ℹ</span>'
        '<span><strong>Estimations en temps réel.</strong> Les compteurs et '
        'le temps restant évoluent à chaque étape — les valeurs définitives '
        's\'affichent à la fin de la recherche.</span>'
        '</div>'
    )

    slot.markdown(
        f'<section class="progress-panel">'
        f'<div class="pp-head"><div class="pp-title-wrap">'
        f'<span class="pp-pulse"></span>'
        f'<div class="pp-title"><h3>Recherche en cours</h3>'
        f'<div class="pp-meta">{meta}</div>'
        f'</div></div></div>'
        f'{estimation_banner}'
        f'<div class="pp-stats">'
        f'<div><div class="pp-label">Villes</div>'
        f'<div class="pp-value">{cities_done}<span class="pp-sm">/ {cities_total}</span></div></div>'
        f'<div><div class="pp-label">Variantes métier</div>'
        f'<div class="pp-value">{variants_done}<span class="pp-sm">/ {variants_total}</span></div></div>'
        f'<div><div class="pp-label">Prospects (après filtres)</div>'
        f'<div>{found_html}</div></div>'
        f'<div><div class="pp-label">Enrichissement TVA</div>'
        f'<div class="pp-value">{vat}<span class="pp-sm">/ {prospects}</span></div></div>'
        f'<div><div class="pp-label">Temps restant</div>'
        f'<div class="pp-value">{eta_html}</div></div>'
        f'</div>'
        f'<div class="pp-bar"><div class="pp-bar-fill" style="width:{pct}%;"></div></div>'
        f'<div class="pp-log"><span class="check">✓</span> {last_log}</div>'
        f'</section>',
        unsafe_allow_html=True,
    )


def _render_done_panel(slot, state: dict) -> None:
    """Panel vert 'Recherche terminée' avec breakdown détaillé des pertes."""
    cities_total = state.get("cities_total", 0)
    variants_total = state.get("variants_total", 0)
    brut = state.get("prospects_brut", 0)
    final = state.get("result_count", 0)
    vat = state.get("vat_enriched", 0)
    duration = _format_duration(state.get("started_at"), state.get("ended_at"))
    losses = state.get("losses") or {}

    # Construction de la breakdown des pertes (uniquement les non-nulles)
    LOSS_LABELS = {
        "city_filter": "hors zone (filtre ville)",
        "dedup_seen": "déjà connues (dédup historique)",
        "dedup_post_bce": "doublons BCE révélés après enrichissement",
        "dedup_intra": "chaînes (même BCE + même localité)",
        "phone_filter": "sans téléphone (filtre obligatoire)",
    }
    loss_lines = []
    for key, label in LOSS_LABELS.items():
        n = losses.get(key, 0)
        if n > 0:
            loss_lines.append(
                f'<div style="display:flex;justify-content:space-between;'
                f'padding:3px 0;font-size:0.78rem;">'
                f'<span style="color:rgba(255,255,255,0.7);">– {label}</span>'
                f'<span style="font-weight:600;">−{n}</span>'
                f'</div>'
            )
    loss_block = ""
    if loss_lines and brut > final:
        loss_block = (
            f'<div style="margin-top:1rem;padding-top:0.8rem;'
            f'border-top:1px solid rgba(255,255,255,0.18);">'
            f'<div style="font-size:0.7rem;letter-spacing:0.08em;'
            f'text-transform:uppercase;color:rgba(255,255,255,0.55);'
            f'font-weight:600;margin-bottom:0.5rem;">'
            f'Détail des {brut - final} fiches écartées</div>'
            + "".join(loss_lines) +
            f'</div>'
        )

    # Bloc d'erreurs de scrape (pliable, visible seulement si scrape_errors non vide)
    scrape_errors = state.get("scrape_errors") or []
    err_block = ""
    if scrape_errors:
        err_items = "".join(
            f'<li style="margin:0.25rem 0;font-family:SF Mono,Monaco,monospace;'
            f'font-size:0.74rem;color:rgba(255,255,255,0.75);">'
            f'{_safe_html(err)}</li>'
            for err in scrape_errors[:25]
        )
        more_note = (f'<div style="font-size:0.72rem;color:rgba(255,255,255,0.55);'
                     f'margin-top:0.4rem;">… et {len(scrape_errors) - 25} autres</div>'
                     if len(scrape_errors) > 25 else "")
        err_block = (
            f'<details style="margin-top:0.9rem;padding-top:0.8rem;'
            f'border-top:1px solid rgba(255,255,255,0.18);">'
            f'<summary style="cursor:pointer;font-size:0.72rem;letter-spacing:0.06em;'
            f'text-transform:uppercase;color:rgba(255,255,255,0.7);font-weight:600;">'
            f'⚠ {len(scrape_errors)} requête(s) en erreur (cliquer pour détails)'
            f'</summary>'
            f'<ul style="margin:0.6rem 0 0 1rem;padding:0;list-style:disc;">'
            f'{err_items}</ul>{more_note}'
            f'</details>'
        )

    slot.markdown(
        f'<section class="progress-panel" style="background:linear-gradient(135deg,#0F6B36,#1F9D55);">'
        f'<div class="pp-head"><div class="pp-title-wrap">'
        f'<span class="pp-pulse" style="background:#FFF;animation:none;box-shadow:none;"></span>'
        f'<div class="pp-title"><h3>Recherche terminée</h3>'
        f'<div class="pp-meta">{cities_total} ville(s) × {variants_total} variante(s) '
        f'en {duration} · {brut} bruts → <strong>{final} finaux</strong></div>'
        f'</div></div></div>'
        f'<div class="pp-stats">'
        f'<div><div class="pp-label">Villes</div>'
        f'<div class="pp-value">{cities_total}</div></div>'
        f'<div><div class="pp-label">Variantes métier</div>'
        f'<div class="pp-value">{variants_total}</div></div>'
        f'<div><div class="pp-label">Prospects finaux</div>'
        f'<div class="pp-value">{final}<span class="pp-sm">/ {brut} bruts</span></div></div>'
        f'<div><div class="pp-label">Enrichissement TVA</div>'
        f'<div class="pp-value">{vat}<span class="pp-sm">/ {final}</span></div></div>'
        f'<div><div class="pp-label">Statut</div>'
        f'<div class="pp-value" style="font-size:1.2rem;">✓ Terminé</div></div>'
        f'</div>'
        f'{loss_block}'
        f'{err_block}'
        f'</section>',
        unsafe_allow_html=True,
    )


# ===========================================================================
# Démarrage du thread de scrape (quand l'utilisateur clique « Lancer »)
# ===========================================================================
if run:
    if not metiers or not cities:
        st.error("Indique au moins un métier et une commune.")
    else:
        start_background_scrape(
            st.session_state.scrape_state,
            metiers=list(metiers),
            cities=list(cities),
            max_per_city=max_per_city,
            headless=headless,
            strict_city=strict_city,
            exclude_seen=exclude_seen,
            require_phone=require_phone,
            do_vat=do_vat,
            do_bce=do_bce,
            do_fin=do_fin,
            workers=workers,
        )
        # Rerun immédiat pour afficher le panel de progression
        st.rerun()


# ===========================================================================
# Lecture du scrape_state à CHAQUE rerun : affiche le panel approprié.
# Auto-refresh par polling (sleep + rerun) tant que le thread tourne.
# ===========================================================================
_scrape_state = st.session_state.scrape_state
_phase = _scrape_state.get("phase", "idle")

# ⛔ Bandeau Google block — rendu en premier, persiste après la fin du scrape
# tant que l'utilisateur n'a pas relancé une recherche (qui reset le flag).
if _scrape_state.get("google_blocked"):
    _block_reason = _safe_html(
        _scrape_state.get("google_blocked_reason") or "raison inconnue"
    )
    google_block_slot.markdown(
        '<section style="margin:0.6rem 0 1rem;padding:1rem 1.2rem;'
        'background:linear-gradient(135deg,#7F1D1D,#B91C1C);'
        'color:#FFF;border-radius:10px;'
        'box-shadow:0 4px 20px rgba(185,28,28,0.35);">'
        '<div style="display:flex;align-items:center;gap:0.6rem;'
        'margin-bottom:0.5rem;">'
        '<span style="font-size:1.4rem;">⛔</span>'
        '<strong style="font-size:1.05rem;">Google a bloqué les requêtes '
        'depuis votre adresse IP</strong></div>'
        f'<div style="font-size:0.85rem;opacity:0.95;margin-bottom:0.7rem;">'
        f'Le scraper a détecté un CAPTCHA ou une page <code>/sorry/</code> '
        f'Google. Détail : <em>{_block_reason}</em></div>'
        '<div style="font-size:0.8rem;opacity:0.92;line-height:1.55;">'
        '<strong>Solutions :</strong><br>'
        '• Changer d\'IP (VPN, redémarrer la box, basculer en 4G)<br>'
        '• Attendre 1 à 24 h pour que Google débanisse l\'IP<br>'
        '• Réduire le nombre de variantes métier (toggle « Inclure les '
        'variantes ») ou le nombre de villes par run<br>'
        '• Désactiver le mode <code>headless</code> pour faire le CAPTCHA '
        'manuellement une fois (option dans la sidebar)'
        '</div>'
        '</section>',
        unsafe_allow_html=True,
    )

if _scrape_state.get("active"):
    _render_progress_panel(progress_slot, _scrape_state)
    # Polling : on rafraîchit chaque 1.5 s tant que le thread tourne
    time.sleep(1.5)
    st.rerun()
elif _phase == PHASE_DONE:
    _render_done_panel(progress_slot, _scrape_state)
    # Auto-sélection du nouveau scrape dans l'onglet Résultats
    sid = _scrape_state.get("result_search_id")
    if sid and st.session_state.get("last_search_id") != sid:
        st.session_state.last_search_id = sid
        st.session_state.selected_search_id = sid
        st.session_state.last_run = _scrape_state.get("ended_at") or datetime.now()
elif _phase == PHASE_CANCELLED:
    progress_slot.warning("Recherche annulée par l'utilisateur.",
                          icon=":material/cancel:")
elif _phase == PHASE_ERROR and not _scrape_state.get("google_blocked"):
    # Si c'est une autre erreur (pas un Google block, déjà bannerisé ci-dessus)
    progress_slot.error(f"Erreur durant le scraping : {_scrape_state.get('error')}",
                        icon=":material/error:")


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
    all_searches = list_searches(100)

    if not all_searches:
        st.markdown(
            f"""
            <div class="empty-state">
                <div style="display:flex;justify-content:center;margin-bottom:0.6rem;">
                    <div style="width:64px;height:64px;border-radius:18px;
                                background:linear-gradient(135deg,#ede9fe,#ddd6fe);
                                display:flex;align-items:center;justify-content:center;
                                box-shadow:0 6px 16px rgba(124,58,237,0.15);">
                        {lucide("target", 32, "#7c3aed", 2)}
                    </div>
                </div>
                <h3>Prêt à prospecter</h3>
                <p>Configure ta recherche dans le panneau de gauche puis clique sur
                <strong>Lancer la recherche</strong>.</p>
            </div>

            <div class="steps-grid">
                <div class="step-card">
                    <div class="step-num">1</div>
                    <h4>Définis ta cible</h4>
                    <p>Saisis le métier (opticien, dentiste, garage…) et une liste de villes
                    dans le panneau de gauche.</p>
                </div>
                <div class="step-card">
                    <div class="step-num">2</div>
                    <h4>Lance le scraping</h4>
                    <p>Google Maps + BCE/KBO + sites web sont interrogés pour récupérer
                    n° TVA, dirigeants et données financières.</p>
                </div>
                <div class="step-card">
                    <div class="step-num">3</div>
                    <h4>Appelle tes prospects</h4>
                    <p>Push vers Ringover en un clic, click-to-call depuis chaque carte,
                    et suivi du statut (à appeler / à rappeler / déjà appelé).</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        with st.container(border=True):
            # ----------------------------------------------------------------
            # Sélecteur de scrape (historique)
            # ----------------------------------------------------------------
            def _fmt_search(s):
                cities_txt = (s["cities"] or "")[:50]
                return f"#{s['id']} · {s['query']} · {cities_txt} · {s['ran_at']} ({s['total']} fiches)"

            search_labels = {s["id"]: _fmt_search(s) for s in all_searches}
            ids = list(search_labels.keys())

            default_id = (st.session_state.selected_search_id
                          or st.session_state.last_search_id
                          or ids[0])
            if default_id not in ids:
                default_id = ids[0]
            default_idx = ids.index(default_id)

            chosen_id = st.selectbox(
                "Scrape affiché",
                options=ids,
                index=default_idx,
                format_func=lambda i: search_labels[i],
                key="scrape_selector",
            )
            st.session_state.selected_search_id = chosen_id

            search_meta = get_search(chosen_id) or {}
            _ran = search_meta.get("ran_at", "")
            _date_pretty = _ran
            try:
                _dt = datetime.strptime(_ran, "%Y-%m-%d %H:%M")
                _date_pretty = _dt.strftime("%d/%m/%Y à %H:%M")
            except Exception:
                pass

            _meta_bits = []
            if search_meta.get("query"):
                _meta_bits.append(f"{lucide('target', 12, '#7c3aed')} <strong>{search_meta['query']}</strong>")
            if search_meta.get("cities"):
                _cities = search_meta["cities"]
                if len(_cities) > 80:
                    _cities = _cities[:77] + "…"
                _meta_bits.append(f"{lucide('map-pin', 12, '#7c3aed')} {_cities}")
            if _date_pretty:
                _meta_bits.append(f"{lucide('calendar', 12, '#7c3aed')} {_date_pretty}")
            if search_meta.get("total"):
                _meta_bits.append(f"{lucide('bar-chart', 12, '#7c3aed')} {search_meta['total']} fiches")

            if _meta_bits:
                st.markdown(
                    "<div style='font-size:0.82rem;color:#64748b;margin:-0.2rem 0 0.6rem 0;'>"
                    + " · ".join(_meta_bits)
                    + "</div>",
                    unsafe_allow_html=True,
                )

            biz_dicts = get_search_businesses(chosen_id)

            # ----------------------------------------------------------------
            # Métriques (compactes)
            # ----------------------------------------------------------------
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Fiches", len(biz_dicts))
            c2.metric("Top 2 Google",
                      sum(1 for b in biz_dicts if (b.get("google_rank") or 0) and b["google_rank"] <= 2))
            c3.metric("Avec téléphone", sum(1 for b in biz_dicts if b.get("phone")))
            c4.metric("Avec TVA", sum(1 for b in biz_dicts if b.get("vat_number")))
            c5.metric("Avec dirigeant", sum(1 for b in biz_dicts if b.get("managers")))
            called = sum(1 for b in biz_dicts if b.get("call_status") == "Déjà appelé")
            c6.metric("Déjà appelé", called)

            # ----------------------------------------------------------------
            # BARRE D'ACTIONS (au-dessus des filtres, comme dans le template)
            # ----------------------------------------------------------------
            st.markdown("")
            ah1, ah2, ah3, ah4 = st.columns([3, 1, 1.2, 1])
            with ah1:
                st.markdown(
                    f'<div style="font-family:var(--font-display);font-size:1.35rem;'
                    f'font-weight:600;color:var(--ink);letter-spacing:-0.01em;">'
                    f'<em style="font-style:italic;color:var(--brand-700);">'
                    f'{len(biz_dicts)} prospects</em> qualifiés</div>',
                    unsafe_allow_html=True,
                )
            with ah2:
                from scraper.models import Business
                biz_objects = []
                for d in biz_dicts:
                    fields = {k: d.get(k) for k in Business.__dataclass_fields__ if k in d}
                    fields["name"] = d.get("name") or ""
                    biz_objects.append(Business(**fields))
                excel_bytes = to_excel_bytes(biz_objects)
                fname_xlsx = f"scrape_{chosen_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.download_button(
                    "Télécharger Excel",
                    data=excel_bytes, file_name=fname_xlsx,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width="stretch",
                    key=f"xlsx_{chosen_id}",
                )
            with ah3:
                csv_bytes = ringover_csv(biz_dicts)
                fname_csv = f"ringover_scrape_{chosen_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                st.download_button(
                    "Exporter pour Ringover",
                    data=csv_bytes, file_name=fname_csv,
                    mime="text/csv",
                    width="stretch",
                    key=f"csv_{chosen_id}",
                )
            with ah4:
                if st.button("Supprimer", width="stretch",
                             type="secondary", key=f"del_{chosen_id}",
                             help="Supprime ce scrape de l'historique (les entreprises restent en base)"):
                    delete_search(chosen_id)
                    st.session_state.selected_search_id = None
                    st.rerun()

            # ----------------------------------------------------------------
            # FILTRES CHIPS (style template) + barre de recherche
            # ----------------------------------------------------------------
            with_vat_count = sum(1 for b in biz_dicts if b.get("vat_number"))
            no_vat_count = sum(1 for b in biz_dicts if not b.get("vat_number"))
            with_web_count = sum(1 for b in biz_dicts if b.get("website"))
            no_web_count = sum(1 for b in biz_dicts if not b.get("website"))
            no_phone_count = sum(1 for b in biz_dicts if not b.get("phone"))
            top2_count = sum(1 for b in biz_dicts if (b.get("google_rank") or 0) and b["google_rank"] <= 2)

            filter_options = [
                f"Tous ({len(biz_dicts)})",
                f"Top 2 Google ({top2_count})",
                f"Avec TVA ({with_vat_count})",
                f"Sans TVA ({no_vat_count})",
                f"Avec site web ({with_web_count})",
                f"Sans site web ({no_web_count})",
                f"Sans téléphone ({no_phone_count})",
            ]
            fc1, fc2 = st.columns([3, 2])
            with fc1:
                try:
                    chip = st.pills(
                        "Filtre",
                        options=filter_options,
                        default=filter_options[0],
                        label_visibility="collapsed",
                        key=f"chip_{chosen_id}",
                    )
                except AttributeError:
                    chip = st.radio(
                        "Filtre", options=filter_options,
                        horizontal=True,
                        label_visibility="collapsed",
                        key=f"chip_{chosen_id}",
                    )
            with fc2:
                search_text = st.text_input(
                    "Rechercher",
                    placeholder="Rechercher par nom, ville ou TVA…",
                    label_visibility="collapsed",
                    key=f"search_{chosen_id}",
                )

            # Appliquer le filtre chip + recherche
            chip = chip or filter_options[0]
            if chip.startswith("Avec TVA"):
                filtered = [b for b in biz_dicts if b.get("vat_number")]
            elif chip.startswith("Sans TVA"):
                filtered = [b for b in biz_dicts if not b.get("vat_number")]
            elif chip.startswith("Avec site web"):
                filtered = [b for b in biz_dicts if b.get("website")]
            elif chip.startswith("Sans site web"):
                filtered = [b for b in biz_dicts if not b.get("website")]
            elif chip.startswith("Top 2 Google"):
                filtered = [b for b in biz_dicts if (b.get("google_rank") or 0) and b["google_rank"] <= 2]
            elif chip.startswith("Sans téléphone"):
                filtered = [b for b in biz_dicts if not b.get("phone")]
            else:
                filtered = list(biz_dicts)

            if search_text:
                s = search_text.lower()
                filtered = [b for b in filtered if any(
                    s in (b.get(f) or "").lower() if isinstance(b.get(f), str) else False
                    for f in ["name", "locality", "city", "category", "address", "managers", "vat_number", "phone"]
                )]

            # ----------------------------------------------------------------
            # TABLEAU (style template) avec pagination
            # ----------------------------------------------------------------
            if filtered:
                PAGE_SIZE = 25
                total_pages = max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
                page_key = f"results_page_{chosen_id}"
                current_page = min(st.session_state.get(page_key, 0), total_pages - 1)
                start = current_page * PAGE_SIZE
                end = min(start + PAGE_SIZE, len(filtered))
                page_items = filtered[start:end]

                # Score de complétude
                def _score(b: dict) -> int:
                    pts = 0
                    if b.get("phone"): pts += 25
                    if b.get("vat_number"): pts += 25
                    if b.get("website"): pts += 20
                    if b.get("managers"): pts += 15
                    try:
                        if b.get("rating") and float(b["rating"]) >= 4.0: pts += 10
                    except (TypeError, ValueError):
                        pass
                    if b.get("reviews_count") and int(b["reviews_count"]) >= 10: pts += 5
                    return min(pts, 100)

                def _status_label(b: dict) -> str:
                    if not b.get("phone"): return "Sans téléphone"
                    if not b.get("vat_number"): return "TVA manquante"
                    if not b.get("website"): return "Pas de site"
                    return "Complet"

                # ------------------------------------------------------------
                # Helpers d'affichage HTML (avatar, score bar, badges)
                # ------------------------------------------------------------
                def _initials(name: str) -> str:
                    words = [w for w in re.sub(r"[^A-Za-zÀ-ÿ ]", " ", name).split() if w]
                    if not words:
                        return "??"
                    if len(words) == 1:
                        return words[0][:2].upper()
                    return (words[0][0] + words[1][0]).upper()

                def _bar_color(s: int) -> str:
                    if s >= 85: return "var(--accent)"  # vert
                    if s >= 60: return "var(--warn)"    # ambre
                    return "var(--danger)"              # rouge

                def _bar_text_color(s: int) -> str:
                    if s >= 85: return "#0F6B36"
                    if s >= 60: return "var(--warn)"
                    return "var(--danger)"

                def _domain(url: str) -> str:
                    try:
                        from urllib.parse import urlparse
                        d = urlparse(url).netloc.replace("www.", "")
                        return d or url
                    except Exception:
                        return url

                # ------------------------------------------------------------
                # Tableau : chaque ligne est un st.columns avec bouton Appeler
                # ------------------------------------------------------------
                # Largeurs relatives des colonnes (sum = ~16)
                COL_W = [3.2, 1.4, 1.0, 1.4, 1.4, 1.4, 1.0, 1.0, 1.0]
                HEADERS = ["Entreprise", "Métier", "Commune", "Téléphone",
                           "TVA", "Site web", "Qualité", "Statut", "Action"]

                # Header
                hcols = st.columns(COL_W)
                for hc, htext in zip(hcols, HEADERS):
                    hc.markdown(
                        f'<div style="font-size:0.68rem;font-weight:600;letter-spacing:0.06em;'
                        f'text-transform:uppercase;color:var(--ink-mute);padding:8px 4px 8px 0;'
                        f'border-bottom:1px solid var(--line);">{htext}</div>',
                        unsafe_allow_html=True,
                    )

                for idx, b in enumerate(page_items):
                    name = (b.get("name") or "—").strip()
                    avatar = _initials(name)
                    meta = (b.get("address") or b.get("locality") or "").strip()
                    metier = (b.get("category") or (b.get("query") or "").split("/")[0].strip()) or "—"
                    commune = (b.get("locality") or b.get("city") or "—").strip()
                    phone = (b.get("phone") or "").strip()
                    vat = b.get("vat_number") or ""
                    website = (b.get("website") or "").strip()
                    score = _score(b)
                    score_color = _bar_color(score)
                    score_text_color = _bar_text_color(score)
                    status = _status_label(b)

                    rcols = st.columns(COL_W)

                    # 1) Entreprise (avatar + nom + meta)
                    rcols[0].markdown(
                        f'<div style="display:flex;align-items:center;gap:10px;padding:10px 0;'
                        f'border-bottom:1px solid var(--line);">'
                        f'<div class="oa-avatar">{_safe_html(avatar)}</div>'
                        f'<div style="min-width:0;"><div style="font-weight:600;color:var(--ink);'
                        f'font-size:0.85rem;line-height:1.25;">{_safe_html(name)}</div>'
                        f'<div style="font-size:0.7rem;color:var(--ink-mute);margin-top:2px;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_safe_html(meta)}</div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )
                    # 2) Métier
                    rcols[1].markdown(
                        f'<div style="padding:18px 0;border-bottom:1px solid var(--line);">'
                        f'<span class="oa-badge oa-badge-primary">{_safe_html(metier)}</span></div>',
                        unsafe_allow_html=True,
                    )
                    # 3) Commune
                    rcols[2].markdown(
                        f'<div style="padding:18px 0;border-bottom:1px solid var(--line);'
                        f'font-size:0.82rem;color:var(--ink);">{_safe_html(commune)}</div>',
                        unsafe_allow_html=True,
                    )
                    # 4) Téléphone (tel: link cliquable, ouvre Ringover desktop si installé)
                    if phone:
                        phone_html = (f'<a href="tel:{phone}" class="oa-cell-phone" '
                                      f'style="text-decoration:none;color:var(--ink);font-weight:500;">'
                                      f'{_safe_html(phone)}</a>')
                    else:
                        phone_html = '<span style="color:var(--ink-mute);font-size:0.74rem;">—</span>'
                    rcols[3].markdown(
                        f'<div style="padding:18px 0;border-bottom:1px solid var(--line);'
                        f'font-size:0.82rem;font-variant-numeric:tabular-nums;">{phone_html}</div>',
                        unsafe_allow_html=True,
                    )
                    # 5) TVA
                    vat_html = (f'<span class="oa-cell-vat">{vat}</span>' if vat
                                else '<span style="color:var(--ink-mute);font-size:0.74rem;">non trouvée</span>')
                    rcols[4].markdown(
                        f'<div style="padding:18px 0;border-bottom:1px solid var(--line);">'
                        f'{vat_html}</div>',
                        unsafe_allow_html=True,
                    )
                    # 6) Site web
                    if website:
                        web_html = (f'<a class="oa-cell-link" href="{website}" target="_blank" '
                                    f'rel="noopener" style="font-size:0.82rem;">{_domain(website)}</a>')
                    else:
                        web_html = '<span style="color:var(--ink-mute);font-size:0.74rem;">—</span>'
                    rcols[5].markdown(
                        f'<div style="padding:18px 0;border-bottom:1px solid var(--line);">{web_html}</div>',
                        unsafe_allow_html=True,
                    )
                    # 7) Qualité
                    rcols[6].markdown(
                        f'<div style="padding:18px 0;border-bottom:1px solid var(--line);">'
                        f'<span class="oa-score">'
                        f'<span class="oa-score-bar"><span class="oa-score-bar-fill" '
                        f'style="width:{score}%;background:{score_color};"></span></span>'
                        f'<span class="oa-score-text" style="color:{score_text_color};">{score}</span>'
                        f'</span></div>',
                        unsafe_allow_html=True,
                    )
                    # 8) Statut
                    if status == "Complet":
                        badge_class = "oa-badge-success"
                    elif status in ("TVA manquante", "Pas de site", "Sans téléphone"):
                        badge_class = "oa-badge-warn"
                    else:
                        badge_class = "oa-badge-neutral"
                    rcols[7].markdown(
                        f'<div style="padding:18px 0;border-bottom:1px solid var(--line);">'
                        f'<span class="oa-badge {badge_class}">{_safe_html(status)}</span></div>',
                        unsafe_allow_html=True,
                    )
                    # 9) Action : 📞 (Ringover) + ℹ️ (Détails)
                    with rcols[8]:
                        st.markdown(
                            '<div style="height:10px;"></div>',
                            unsafe_allow_html=True,
                        )
                        b1, b2 = st.columns([1, 1])
                        with b1:
                            if st.button(":material/phone:",
                                         key=f"call_row_{chosen_id}_{idx}",
                                         disabled=not phone or not is_configured(),
                                         type="primary",
                                         help="Appeler via Ringover" if (phone and is_configured())
                                              else ("Pas de numéro" if not phone
                                                    else "Configure RINGOVER_API_KEY"),
                                         width="stretch"):
                                res = click_to_call(phone)
                                if res["ok"]:
                                    st.toast(res["message"], icon=":material/call_made:")
                                else:
                                    st.toast(res["message"], icon=":material/error:")
                        with b2:
                            if st.button(":material/info:",
                                         key=f"info_row_{chosen_id}_{idx}",
                                         help="Voir les détails",
                                         width="stretch"):
                                show_business_details(b)
                        st.markdown(
                            '<div style="border-bottom:1px solid var(--line);'
                            'margin-top:6px;"></div>',
                            unsafe_allow_html=True,
                        )

                # ------------------------------------------------------------
                # PAGINATION (style template, pills compacts à droite)
                # ------------------------------------------------------------
                pf1, pf2 = st.columns([3, 2])
                with pf1:
                    st.markdown(
                        f'<div style="padding:0.6rem 0;color:var(--ink-mute);font-size:0.82rem;">'
                        f'Affichage <strong style="color:var(--ink);">{start + 1}–{end}</strong> '
                        f'sur <strong style="color:var(--ink);">{len(filtered)}</strong> prospects '
                        f'<span style="color:var(--ink-mute);">· page {current_page + 1} / {total_pages}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with pf2:
                    pcols = st.columns([1, 1, 2, 1, 1])
                    with pcols[0]:
                        if st.button("«", disabled=current_page == 0,
                                     key=f"first_{chosen_id}", width="stretch"):
                            st.session_state[page_key] = 0
                            st.rerun()
                    with pcols[1]:
                        if st.button("‹", disabled=current_page == 0,
                                     key=f"prev_{chosen_id}", width="stretch"):
                            st.session_state[page_key] = max(0, current_page - 1)
                            st.rerun()
                    with pcols[2]:
                        st.markdown(
                            f"<div style='text-align:center;padding-top:8px;font-weight:700;"
                            f"color:var(--ink);font-family:var(--font-display);'>"
                            f"{current_page + 1} / {total_pages}</div>",
                            unsafe_allow_html=True,
                        )
                    with pcols[3]:
                        if st.button("›", disabled=current_page >= total_pages - 1,
                                     key=f"next_{chosen_id}", width="stretch"):
                            st.session_state[page_key] = min(total_pages - 1, current_page + 1)
                            st.rerun()
                    with pcols[4]:
                        if st.button("»", disabled=current_page >= total_pages - 1,
                                     key=f"last_{chosen_id}", width="stretch"):
                            st.session_state[page_key] = total_pages - 1
                            st.rerun()

                # (Les boutons Appeler 📞 et Détails ℹ️ sont désormais dans chaque ligne)
            else:
                st.info("Aucune entreprise ne correspond aux filtres actifs.")

            if skipped:
                with st.expander(f"{len(skipped)} entreprises écartées (déjà trouvées avant)"):
                    sk_df = to_dataframe(skipped)
                    show = [c for c in ["Nom", "Localité", "Numéro TVA", "Vue pour la 1re fois"] if c in sk_df.columns]
                    st.dataframe(sk_df[show], width="stretch", hide_index=True)

    if st.session_state.log:
        with st.expander("Journal d'exécution"):
            st.code("\n".join(st.session_state.log), language="text")


with tab_campaign:
    cstats = campaign_stats()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("À appeler", cstats.get("À appeler", 0))
    m2.metric("Déjà appelé", cstats.get("Déjà appelé", 0))
    m3.metric("À rappeler", cstats.get("À rappeler", 0))
    m4.metric("Ne plus rappeler", cstats.get("Ne plus rappeler", 0))

    if is_configured():
        st.success("Ringover connecté — envoi de contacts, click-to-call et synchronisation actifs.",
                   icon=":material/check_circle:")
    else:
        st.warning(
            "Ringover non configuré. Définis la variable d'environnement `RINGOVER_API_KEY` "
            "pour activer l'envoi de contacts, le click-to-call et la synchro. "
            "Le suivi de statut et l'export CSV restent disponibles.",
            icon=":material/warning:",
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
            width="stretch",
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

        if st.button("Enregistrer les statuts", type="primary"):
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

        st.markdown(
            f"<h4 style='display:flex;align-items:center;gap:6px;margin-top:1rem;'>"
            f"{lucide('link', 18, '#7c3aed')} Actions Ringover</h4>",
            unsafe_allow_html=True,
        )
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("Envoyer ces contacts vers Ringover",
                         width="stretch", disabled=not is_configured()):
                res = push_contacts(camp)
                (st.success if res["ok"] else st.error)(res["message"])
                if res.get("errors"):
                    with st.expander("Détail des échecs"):
                        st.code("\n".join(res["errors"]), language="text")
        with a2:
            if st.button("Synchroniser les appels passés",
                         width="stretch", disabled=not is_configured()):
                res = sync_call_statuses()
                if res["ok"]:
                    st.success(res["message"])
                    st.rerun()
                else:
                    st.error(res["message"])
        with a3:
            st.download_button(
                "Export CSV (import Ringover)",
                data=ringover_csv(camp),
                file_name=f"ringover_contacts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                width="stretch",
            )

        st.markdown(
            f"<h4 style='display:flex;align-items:center;gap:6px;margin-top:1rem;'>"
            f"{lucide('phone-call', 18, '#7c3aed')} Appeler une entreprise</h4>",
            unsafe_allow_html=True,
        )
        callable_biz = [b for b in camp if b.get("phone")]
        if callable_biz:
            labels = {f"{b['name']} — {b['phone']}": b for b in callable_biz}
            cc1, cc2 = st.columns([3, 1])
            pick = cc1.selectbox("Entreprise à appeler", list(labels.keys()),
                                 label_visibility="collapsed")
            with cc2:
                if st.button("Appeler maintenant", width="stretch",
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
        st.dataframe(to_dataframe(dropped), width="stretch", hide_index=True, height=420)
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
        st.dataframe(sdf, width="stretch", hide_index=True, height=240)
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
        st.dataframe(kdf[cols], width="stretch", hide_index=True, height=360)

        st.download_button(
            "Exporter tout l'historique (CSV)",
            data=kdf.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"historique_entreprises_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

        with st.expander("Réinitialiser l'historique"):
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
        les mieux référencés. Ils sont surlignés (badge doré / badge argenté) dans les cartes et l'Excel.

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

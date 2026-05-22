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
from scraper import filter_by_city, scrape_google_maps
from audit import run_full_audit
from data import (
    ARRONDISSEMENTS,
    PROVINCES,
    all_arrondissement_labels,
    expand_arrondissements_to_communes,
)
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
                     type=button_type, use_container_width=True):
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
                     type=button_type, use_container_width=True):
            with st.spinner("Audit SEO + Google Business en cours… (~3 s)"):
                res = run_full_audit(biz)
            save_seo_audit(dedup, res)
            res["_generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            with audit_slot.container():
                st.markdown(_render_audit_card(res, res["_generated_at"]),
                            unsafe_allow_html=True)


@st.dialog("Détails de l'entreprise", width="large")
def show_business_details(biz: dict) -> None:
    name = biz.get("name") or "Entreprise sans nom"
    rank = biz.get("google_rank")
    status = biz.get("call_status") or "À appeler"

    st.markdown(
        f"### {name}<br>"
        f"{_rank_badge_html(rank)} &nbsp; {_status_chip_html(status)}",
        unsafe_allow_html=True,
    )

    # ---- Briefing IA pré-appel ----
    _render_ai_briefing_section(biz)

    # ---- Audit SEO complet (site web + GMB) ----
    _render_seo_audit_section(biz)

    BRAND = "#7c3aed"
    GOLD = "#f59e0b"
    GREEN = "#059669"

    def _section(icon_name, title, color=BRAND):
        return (f'<div style="display:flex;align-items:center;gap:6px;font-weight:700;'
                f'color:{color};font-size:0.92rem;margin:0.6rem 0 0.4rem 0;'
                f'text-transform:uppercase;letter-spacing:0.04em;">'
                f'{lucide(icon_name, 16, color, 2.2)}<span>{title}</span></div>')

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_section("map-pin", "Coordonnées"), unsafe_allow_html=True)
        if biz.get("address"):
            st.markdown(f"{lucide('map', 14, BRAND)} {biz['address']}", unsafe_allow_html=True)
        if biz.get("phone"):
            st.markdown(f"{lucide('phone', 14, BRAND)} [{biz['phone']}](tel:{biz['phone']})",
                        unsafe_allow_html=True)
        if biz.get("email"):
            st.markdown(f"{lucide('mail', 14, BRAND)} [{biz['email']}](mailto:{biz['email']})",
                        unsafe_allow_html=True)
        if biz.get("website"):
            st.markdown(f"{lucide('globe', 14, BRAND)} [{biz['website']}]({biz['website']})",
                        unsafe_allow_html=True)

        st.markdown(_section("landmark", "Identité légale"), unsafe_allow_html=True)
        if biz.get("vat_number"):
            st.write(f"TVA : `{biz['vat_number']}`")
        if biz.get("bce_number"):
            st.write(f"BCE : `{biz['bce_number']}`")
        if biz.get("legal_form"):
            st.write(f"Forme : {biz['legal_form']}")
        if biz.get("creation_date"):
            st.write(f"Créée le : {biz['creation_date']}")
        if biz.get("managers"):
            st.markdown(f"{lucide('users', 14, BRAND)} **Dirigeant(s) :** {biz['managers']}",
                        unsafe_allow_html=True)
        if biz.get("nace_activities"):
            st.caption(f"NACE : {biz['nace_activities']}")

    with c2:
        st.markdown(_section("star", "Réputation Google", GOLD), unsafe_allow_html=True)
        if biz.get("rating"):
            st.markdown(
                f"{lucide('star', 14, GOLD)} **{biz['rating']}** "
                f"<span style='color:#64748b;'>({biz.get('reviews_count') or 0} avis)</span>",
                unsafe_allow_html=True,
            )
        if biz.get("category"):
            st.write(f"Catégorie : {biz['category']}")
        if biz.get("hours"):
            st.caption(f"Horaires : {biz['hours']}")
        if biz.get("gmaps_url"):
            st.markdown(
                f"{lucide('external-link', 14, BRAND)} [Voir sur Google Maps]({biz['gmaps_url']})",
                unsafe_allow_html=True,
            )

        st.markdown(_section("coins", "Données financières", GREEN), unsafe_allow_html=True)
        for label, key in [
            ("Chiffre d'affaires", "nbb_revenue"),
            ("Fonds propres", "nbb_equity"),
            ("Effectif", "nbb_employees"),
            ("Année", "nbb_year"),
            ("Capital", "capital"),
            ("Établissements", "establishments_count"),
            ("Score solvabilité", "companyweb_score"),
        ]:
            v = biz.get(key)
            if v not in (None, "", 0):
                st.write(f"{label} : {v}")
        if biz.get("nbb_url"):
            st.markdown(
                f"{lucide('external-link', 14, GREEN)} [Comptes annuels BNB]({biz['nbb_url']})",
                unsafe_allow_html=True,
            )
        if biz.get("companyweb_url"):
            st.markdown(
                f"{lucide('external-link', 14, GREEN)} [Fiche CompanyWeb]({biz['companyweb_url']})",
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown(_section("phone-call", "Suivi d'appel"), unsafe_allow_html=True)
    cn1, cn2, cn3 = st.columns(3)
    cn1.metric("Statut actuel", status)
    cn2.metric("Dernier appel", biz.get("last_call_at") or "—")
    cn3.metric("Date de rappel", biz.get("callback_date") or "—")
    if biz.get("call_notes"):
        st.info(biz['call_notes'])


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
                use_container_width=True,
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
            if st.button("Détails", key=f"det_{safe_key}", use_container_width=True):
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
        "preset_query": "opticien",
        "preset_cities": "Waterloo\nBraine-l'Alleud\nNivelles\nLa Hulpe\nHalle",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


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
        default=["opticien"],
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
    metiers = list(dict.fromkeys(selected_metiers + custom_metiers))  # dédup, ordre conservé

    # --- ZONE DE PROSPECTION ---
    st.markdown("")
    st.markdown(
        '<div style="font-size:0.82rem;font-weight:600;color:var(--ink);margin-bottom:6px;">'
        'Zone de prospection</div>',
        unsafe_allow_html=True,
    )
    try:
        zone_mode = st.segmented_control(
            "Mode",
            options=["Par arrondissement", "Par commune"],
            default="Par arrondissement",
            label_visibility="collapsed",
            key="zone_mode",
        )
    except AttributeError:
        zone_mode = st.radio(
            "Mode",
            options=["Par arrondissement", "Par commune"],
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

        default_label = next((lab for lab in arr_options if "Nivelles" in lab), arr_options[0])
        selected_labels = st.multiselect(
            "Arrondissements à scraper",
            options=arr_options,
            default=[default_label],
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
    else:
        cities_raw = st.text_area(
            "Communes ciblées (une par ligne)",
            value=st.session_state.preset_cities,
            height=120,
            placeholder="Waterloo\nBraine-l'Alleud\nNivelles\nLa Hulpe\nHalle",
        )
        cities = [c.strip() for c in cities_raw.splitlines() if c.strip()]
        if cities:
            st.caption(f"**{len(cities)} commune(s)** ciblée(s)")

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
    estimate = nb_combos * (30 if unlimited else min(max_per_city, 30))
    estimate_min = max(1, int(estimate * 0.35 / 60))
    foot1, foot2 = st.columns([2, 1])
    with foot1:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:14px;">'
            f'<div>'
            f'<div class="estimate-num">~ {estimate}</div>'
            f'<div class="estimate-label">prospects estimés · ~{estimate_min} min '
            f'· {len(metiers)} métier(s) × {len(cities)} commune(s)</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    with foot2:
        run = st.button("Lancer la recherche", type="primary", use_container_width=True,
                        disabled=not (metiers and cities))

    # Panneau de progression — placé À L'INTÉRIEUR de la form-card, en dessous du bouton
    progress_slot = st.empty()

st.markdown("")


tab_results, tab_campaign, tab_dropped, tab_history, tab_help = st.tabs(
    ["Résultats", "Campagne d'appels", "Hors zone", "Historique", "Aide"]
)


def log(msg: str) -> None:
    st.session_state.log.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


if run:
    if not metiers or not cities:
        st.error("Indique au moins un métier et une commune.")
    else:
        st.session_state.results = []
        st.session_state.dropped = []
        st.session_state.skipped = []
        st.session_state.log = []

        # Libellé combiné pour l'historique (premier métier ou plusieurs)
        if len(metiers) == 1:
            search_label = metiers[0]
        else:
            search_label = " / ".join(metiers[:3]) + (" …" if len(metiers) > 3 else "")

        # Panneau de progression : progress_slot a déjà été défini dans la form-card,
        # on l'utilise pour rendre l'état "en cours" juste sous le bouton Lancer.
        _started_at = datetime.now()

        def _elapsed_str() -> str:
            delta = (datetime.now() - _started_at).total_seconds()
            mins, secs = divmod(int(delta), 60)
            return f"{mins} min {secs:02d} s" if mins else f"{secs} s"

        def _render_progress(communes_done: int, communes_total: int,
                             prospects_found: int, vat_enriched: int,
                             last_log: str = "") -> None:
            pct = min(100, int(100 * communes_done / max(communes_total, 1)))
            eta_sec = max(0, int(((datetime.now() - _started_at).total_seconds()
                                  / max(communes_done, 1)) * (communes_total - communes_done)))
            eta_mins, eta_s = divmod(eta_sec, 60)
            eta_html = (f"{eta_mins}<span class='pp-sm'>min {eta_s:02d} s</span>"
                        if eta_mins else f"{eta_s}<span class='pp-sm'>sec</span>")
            log_clean = _safe_html(last_log)
            progress_slot.markdown(
                f'<section class="progress-panel">'
                f'<div class="pp-head">'
                f'<div class="pp-title-wrap">'
                f'<span class="pp-pulse"></span>'
                f'<div class="pp-title">'
                f'<h3>Recherche en cours</h3>'
                f'<div class="pp-meta">Lancée il y a {_elapsed_str()} · '
                f'{len(cities)} communes × {len(metiers)} métiers</div>'
                f'</div></div></div>'
                f'<div class="pp-stats">'
                f'<div><div class="pp-label">Communes traitées</div>'
                f'<div class="pp-value">{communes_done}<span class="pp-sm">/ {communes_total}</span></div></div>'
                f'<div><div class="pp-label">Prospects trouvés</div>'
                f'<div class="pp-value">{prospects_found}</div></div>'
                f'<div><div class="pp-label">Enrichissement TVA</div>'
                f'<div class="pp-value">{vat_enriched}<span class="pp-sm">/ {prospects_found}</span></div></div>'
                f'<div><div class="pp-label">Temps restant</div>'
                f'<div class="pp-value">{eta_html}</div></div>'
                f'</div>'
                f'<div class="pp-bar"><div class="pp-bar-fill" style="width:{pct}%;"></div></div>'
                f'<div class="pp-log"><span class="check">✓</span> {log_clean}</div>'
                f'</section>',
                unsafe_allow_html=True,
            )

        def _render_done(communes_total: int, prospects: int, vat: int) -> None:
            progress_slot.markdown(
                f'<section class="progress-panel" style="background:linear-gradient(135deg,#0F6B36,#1F9D55);">'
                f'<div class="pp-head"><div class="pp-title-wrap">'
                f'<span class="pp-pulse" style="background:#FFF;animation:none;box-shadow:none;"></span>'
                f'<div class="pp-title"><h3>Recherche terminée</h3>'
                f'<div class="pp-meta">{communes_total} communes traitées en {_elapsed_str()}</div>'
                f'</div></div></div>'
                f'<div class="pp-stats">'
                f'<div><div class="pp-label">Communes traitées</div>'
                f'<div class="pp-value">{communes_total}</div></div>'
                f'<div><div class="pp-label">Prospects trouvés</div>'
                f'<div class="pp-value">{prospects}</div></div>'
                f'<div><div class="pp-label">Enrichissement TVA</div>'
                f'<div class="pp-value">{vat}<span class="pp-sm">/ {prospects}</span></div></div>'
                f'<div><div class="pp-label">Statut</div>'
                f'<div class="pp-value" style="font-size:1.2rem;">✓ Terminé</div></div>'
                f'</div></section>',
                unsafe_allow_html=True,
            )

        with tab_results:
            _last_msg = {"text": "Démarrage…"}
            communes_total = len(cities) * len(metiers)
            communes_done = 0
            _render_progress(0, communes_total, 0, 0, "Démarrage…")

            def cb(msg: str) -> None:
                log(msg)
                _last_msg["text"] = msg
                # Estimer prospects/vat depuis les messages
                _render_progress(communes_done, communes_total,
                                 len(businesses) if 'businesses' in dir() else 0,
                                 sum(1 for b in (businesses if 'businesses' in dir() else []) if getattr(b, "vat_number", None)),
                                 msg)

            businesses = []
            try:
                for i, m in enumerate(metiers, 1):
                    log(f"[{i}/{len(metiers)}] Scraping métier : {m}")
                    _last_msg["text"] = f"Scraping métier {m}…"
                    _render_progress(communes_done, communes_total, len(businesses), 0, _last_msg["text"])
                    for city_idx, city in enumerate(cities):
                        # Scraping ville par ville pour suivre la progression
                        part = scrape_google_maps(
                            query=m, cities=[city], max_results_per_city=max_per_city,
                            headless=headless, on_progress=cb,
                        )
                        businesses.extend(part)
                        communes_done += 1
                        _render_progress(communes_done, communes_total,
                                         len(businesses), 0,
                                         f"{m} · {city} — {len(part)} prospects")
                log(f"Scraping terminé : {len(businesses)} fiches brutes (tous métiers)")
            except Exception as e:
                st.error(f"Erreur scraping : {e}")

            dropped: list = []
            if strict_city and businesses:
                businesses, dropped = filter_by_city(businesses)
                log(f"Filtre ville : {len(businesses)} gardées, {len(dropped)} hors zone")
                _render_progress(communes_total, communes_total, len(businesses), 0,
                                 f"Filtre ville : {len(dropped)} hors zone écartées")

            skipped: list = []
            if exclude_seen and businesses:
                mark_seen(businesses)
                skipped = [b for b in businesses if b.already_seen]
                businesses = [b for b in businesses if not b.already_seen]
                log(f"Dédup historique : {len(skipped)} déjà connues écartées")
                _render_progress(communes_total, communes_total, len(businesses), 0,
                                 f"Dédup : {len(skipped)} déjà connues")

            if (do_vat or do_bce or do_fin) and businesses:
                log(f"Enrichissement parallèle (workers={workers})…")
                _render_progress(communes_total, communes_total, len(businesses), 0,
                                 "Enrichissement TVA / BCE / financier…")
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

            # Dédup INTRA-BATCH : si deux métiers / villes renvoient la même entreprise
            # (même BCE ou même nom + code postal), on ne garde qu'une seule fiche.
            from storage.history import dedup_key as _dk
            seen_in_batch = set()
            unique_businesses = []
            internal_dupes = 0
            for b in businesses:
                key = _dk(b)
                if key in seen_in_batch:
                    internal_dupes += 1
                    continue
                seen_in_batch.add(key)
                unique_businesses.append(b)
            if internal_dupes:
                log(f"Dédup intra-batch : {internal_dupes} doublons fusionnés (même BCE/nom)")
                _render_progress(communes_total, communes_total, len(unique_businesses), 0,
                                 f"Fusion : {internal_dupes} doublons internes")
            businesses = unique_businesses

            # Filtre téléphone obligatoire (si demandé dans les params)
            try:
                _need_phone_filter = require_phone
            except NameError:
                _need_phone_filter = False
            if _need_phone_filter and businesses:
                before = len(businesses)
                businesses = [b for b in businesses if b.phone]
                removed = before - len(businesses)
                if removed:
                    log(f"Filtre téléphone : {removed} fiches sans tél écartées")
                    _render_progress(communes_total, communes_total, len(businesses), 0,
                                     f"Filtre téléphone : {removed} écartées")

            try:
                new_search_id = save_search(search_label, cities, businesses)
                st.session_state.last_search_id = new_search_id
                st.session_state.selected_search_id = new_search_id
            except Exception as e:
                log(f"! Erreur sauvegarde historique : {e}")

            st.session_state.results = businesses
            st.session_state.dropped = dropped
            st.session_state.skipped = skipped
            st.session_state.last_run = datetime.now()

            vat_n = sum(1 for b in businesses if b.vat_number)
            log(f"Terminé : {len(businesses)} nouvelles entreprises, {vat_n} avec TVA")
            _render_done(communes_total, len(businesses), vat_n)


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
                    use_container_width=True,
                    key=f"xlsx_{chosen_id}",
                )
            with ah3:
                csv_bytes = ringover_csv(biz_dicts)
                fname_csv = f"ringover_scrape_{chosen_id}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
                st.download_button(
                    "Exporter pour Ringover",
                    data=csv_bytes, file_name=fname_csv,
                    mime="text/csv",
                    use_container_width=True,
                    key=f"csv_{chosen_id}",
                )
            with ah4:
                if st.button("Supprimer", use_container_width=True,
                             type="secondary", key=f"del_{chosen_id}",
                             help="Supprime ce scrape de l'historique (les entreprises restent en base)"):
                    delete_search(chosen_id)
                    st.session_state.selected_search_id = None
                    st.rerun()

            # ----------------------------------------------------------------
            # FILTRES CHIPS (style template) + barre de recherche
            # ----------------------------------------------------------------
            with_vat_count = sum(1 for b in biz_dicts if b.get("vat_number"))
            with_web_count = sum(1 for b in biz_dicts if b.get("website"))
            no_phone_count = sum(1 for b in biz_dicts if not b.get("phone"))
            top2_count = sum(1 for b in biz_dicts if (b.get("google_rank") or 0) and b["google_rank"] <= 2)

            filter_options = [
                f"Tous ({len(biz_dicts)})",
                f"Avec TVA ({with_vat_count})",
                f"Avec site web ({with_web_count})",
                f"Top 2 Google ({top2_count})",
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
            elif chip.startswith("Avec site web"):
                filtered = [b for b in biz_dicts if b.get("website")]
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
                                         use_container_width=True):
                                res = click_to_call(phone)
                                if res["ok"]:
                                    st.toast(res["message"], icon=":material/call_made:")
                                else:
                                    st.toast(res["message"], icon=":material/error:")
                        with b2:
                            if st.button(":material/info:",
                                         key=f"info_row_{chosen_id}_{idx}",
                                         help="Voir les détails",
                                         use_container_width=True):
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
                                     key=f"first_{chosen_id}", use_container_width=True):
                            st.session_state[page_key] = 0
                            st.rerun()
                    with pcols[1]:
                        if st.button("‹", disabled=current_page == 0,
                                     key=f"prev_{chosen_id}", use_container_width=True):
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
                                     key=f"next_{chosen_id}", use_container_width=True):
                            st.session_state[page_key] = min(total_pages - 1, current_page + 1)
                            st.rerun()
                    with pcols[4]:
                        if st.button("»", disabled=current_page >= total_pages - 1,
                                     key=f"last_{chosen_id}", use_container_width=True):
                            st.session_state[page_key] = total_pages - 1
                            st.rerun()

                # (Les boutons Appeler 📞 et Détails ℹ️ sont désormais dans chaque ligne)
            else:
                st.info("Aucune entreprise ne correspond aux filtres actifs.")

            if skipped:
                with st.expander(f"{len(skipped)} entreprises écartées (déjà trouvées avant)"):
                    sk_df = to_dataframe(skipped)
                    show = [c for c in ["Nom", "Localité", "Numéro TVA", "Vue pour la 1re fois"] if c in sk_df.columns]
                    st.dataframe(sk_df[show], use_container_width=True, hide_index=True)

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
                         use_container_width=True, disabled=not is_configured()):
                res = push_contacts(camp)
                (st.success if res["ok"] else st.error)(res["message"])
                if res.get("errors"):
                    with st.expander("Détail des échecs"):
                        st.code("\n".join(res["errors"]), language="text")
        with a2:
            if st.button("Synchroniser les appels passés",
                         use_container_width=True, disabled=not is_configured()):
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
                use_container_width=True,
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
                if st.button("Appeler maintenant", use_container_width=True,
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

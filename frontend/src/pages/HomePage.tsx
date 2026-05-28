/**
 * HomePage — réplique structurelle de l'app Streamlit Oui Allo.
 *
 * Sections :
 *   - Topbar (logo + sub + quota)
 *   - Hero (eyebrow + titre italique souligné + stats inline)
 *   - Form-card « Lancer un scrape » (placeholder pour le POC)
 *   - Tabs (Résultats / Campagne / Hors zone / Historique / Aide)
 *   - Contenu du tab actif
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getHistory } from "../lib/api";
import { ResultsTab } from "../tabs/ResultsTab";
import { CampaignTab } from "../tabs/CampaignTab";
import { OutOfZoneTab } from "../tabs/OutOfZoneTab";
import { HistoryTab } from "../tabs/HistoryTab";
import { HelpTab } from "../tabs/HelpTab";

type TabKey = "results" | "campaign" | "out_of_zone" | "history" | "help";

export function HomePage() {
  const [activeTab, setActiveTab] = useState<TabKey>("results");

  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: getHistory,
    staleTime: 60_000,
  });

  const stats = historyQ.data?.stats;

  return (
    <>
      {/* Topbar */}
      <header className="oa-topbar">
        <div className="oa-topbar__inner">
          <Link to="/" className="oa-brand">
            <span className="oa-brand__logo">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="12" cy="12" r="10" />
                <circle cx="12" cy="12" r="6" />
                <circle cx="12" cy="12" r="2" />
              </svg>
            </span>
            <div>
              <div className="oa-brand__name">ScrapperGMB</div>
              <div className="oa-brand__sub">Prospection B2B · Media Fast</div>
            </div>
          </Link>
          <div className="oa-topbar__meta">
            <span className="oa-topbar__quota">
              <strong>{stats?.total_businesses ?? "—"}</strong> prospects en base
            </span>
            <span style={{ color: "var(--ink-400)" }}>
              POC React + FastAPI
            </span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="oa-hero">
        <div className="oa-hero__text">
          <span className="oa-hero__eyebrow">Prospection ciblée</span>
          <h1 className="oa-hero__title">
            Trouve tes prospects B2B en{" "}
            <em>quelques minutes</em>
          </h1>
          <p className="oa-hero__desc">
            Scrape Google Maps + BCE/KBO + dépôts BNB pour obtenir des fiches
            qualifiées avec téléphone, dirigeants et santé financière.
            Pousse vers Ringover en un clic.
          </p>
        </div>
        <div className="oa-hero__stats">
          <div>
            <div className="oa-hero__stat-label">Prospects</div>
            <div className="oa-hero__stat-value">
              {stats?.total_businesses ?? "—"}
            </div>
          </div>
          <div>
            <div className="oa-hero__stat-label">Recherches</div>
            <div className="oa-hero__stat-value">
              {stats?.total_searches ?? "—"}
            </div>
          </div>
          <div>
            <div className="oa-hero__stat-label">Appelés</div>
            <div className="oa-hero__stat-value">
              {stats?.total_called ?? "—"}
            </div>
          </div>
        </div>
      </section>

      {/* Form-card placeholder */}
      <ScrapeFormPlaceholder />

      {/* Tabs */}
      <nav className="oa-tabs" role="tablist">
        <div className="oa-tabs__list">
          <TabButton
            label="Résultats"
            icon={<TargetIcon />}
            active={activeTab === "results"}
            onClick={() => setActiveTab("results")}
          />
          <TabButton
            label="Campagne d'appels"
            icon={<PhoneIcon />}
            active={activeTab === "campaign"}
            onClick={() => setActiveTab("campaign")}
          />
          <TabButton
            label="Hors zone"
            icon={<MapPinIcon />}
            active={activeTab === "out_of_zone"}
            onClick={() => setActiveTab("out_of_zone")}
          />
          <TabButton
            label="Historique"
            icon={<ClockIcon />}
            active={activeTab === "history"}
            onClick={() => setActiveTab("history")}
          />
          <TabButton
            label="Aide"
            icon={<InfoIcon />}
            active={activeTab === "help"}
            onClick={() => setActiveTab("help")}
          />
        </div>
      </nav>

      {/* Tab content */}
      <div className="oa-tab-content">
        {activeTab === "results" && <ResultsTab />}
        {activeTab === "campaign" && <CampaignTab />}
        {activeTab === "out_of_zone" && <OutOfZoneTab />}
        {activeTab === "history" && <HistoryTab />}
        {activeTab === "help" && <HelpTab />}
      </div>
    </>
  );
}

// ─── Form placeholder ─────────────────────────────────────────────────

function ScrapeFormPlaceholder() {
  return (
    <div className="oa-form-card">
      <div className="oa-form-card__inner">
        <div className="oa-form-card__header">
          <div>
            <h2 className="oa-form-card__title">Lancer une nouvelle recherche</h2>
            <p className="oa-form-card__sub">
              Métier + communes ciblées → scrape Google Maps + enrichissement
            </p>
          </div>
          <span
            style={{
              padding: "5px 11px",
              background: "var(--amber-50)",
              color: "var(--amber-700)",
              borderRadius: 999,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            POC
          </span>
        </div>
        <div className="oa-form-row">
          <div className="oa-form-field">
            <label className="oa-form-field__label">Métier(s)</label>
            <input
              type="text"
              className="oa-form-field__input"
              placeholder="ex : opticien, dentiste, garage…"
              disabled
            />
          </div>
          <div className="oa-form-field">
            <label className="oa-form-field__label">Communes ou zone</label>
            <input
              type="text"
              className="oa-form-field__input"
              placeholder="ex : Waterloo, Mons, Liège"
              disabled
            />
          </div>
        </div>
        <div className="oa-form-card__footer">
          <div className="oa-form-estimate">
            <div>
              <div className="oa-form-estimate__num">—</div>
              <div className="oa-form-estimate__label">
                prospects estimés
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--ink-500)" }}>
              Le formulaire de lancement nécessite WebSocket + jobs background.{" "}
              <br />
              Utilise <code className="mono" style={{ background: "var(--ink-100)", padding: "2px 6px", borderRadius: 4 }}>streamlit run app.py</code> pour scraper.
            </span>
            <button
              className="btn btn--primary"
              disabled
              style={{ opacity: 0.5, cursor: "not-allowed" }}
            >
              Lancer (bientôt)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Tab button ───────────────────────────────────────────────────────

function TabButton({
  label,
  icon,
  active,
  onClick,
}: {
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`oa-tab ${active ? "is-active" : ""}`}
      onClick={onClick}
      role="tab"
      aria-selected={active}
    >
      <span className="oa-tab__icon">{icon}</span>
      {label}
    </button>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────

function TargetIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="12" r="6" />
      <circle cx="12" cy="12" r="2" />
    </svg>
  );
}
function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
    </svg>
  );
}
function MapPinIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}
function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function InfoIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

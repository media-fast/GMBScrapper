/**
 * Tab Résultats — reprend exactement la logique de l'ancienne ResultsPage.
 * Sélecteur scrape + métriques + filtres pills + recherche + grille de cards.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSearchBusinesses, listSearches } from "../lib/api";
import { ScrapeSelector } from "../components/ScrapeSelector";
import { BusinessCard } from "../components/BusinessCard";
import {
  FilterPills,
  applyFilter,
  type FilterKey,
} from "../components/FilterPills";
import type { BusinessSummary } from "../lib/types";

export function ResultsTab() {
  const searchesQ = useQuery({
    queryKey: ["searches"],
    queryFn: () => listSearches(100),
  });

  const [activeSearchId, setActiveSearchId] = useState<number | null>(null);
  const effectiveSearchId =
    activeSearchId ?? (searchesQ.data?.[0]?.id ?? null);

  const businessesQ = useQuery({
    queryKey: ["businesses", effectiveSearchId],
    queryFn: () => getSearchBusinesses(effectiveSearchId!),
    enabled: effectiveSearchId !== null,
  });

  const [filter, setFilter] = useState<FilterKey>("all");
  const [searchText, setSearchText] = useState("");

  const filtered = useMemo(() => {
    if (!businessesQ.data) return [];
    let list = applyFilter(businessesQ.data.items, filter);
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      list = list.filter((b) =>
        [
          b.name,
          b.locality,
          b.city,
          b.category,
          b.address,
          b.managers,
          b.vat_number,
          b.phone,
        ].some((f) => f?.toLowerCase().includes(q)),
      );
    }
    return list;
  }, [businessesQ.data, filter, searchText]);

  if (searchesQ.isLoading) {
    return (
      <div className="empty-state">
        <div className="empty-state__title serif">Chargement…</div>
      </div>
    );
  }
  if (searchesQ.error) {
    return (
      <div
        className="card"
        style={{
          padding: 24,
          border: "1px solid #FCA5A5",
          background: "#FEF2F2",
        }}
      >
        <div
          style={{ fontWeight: 600, color: "var(--red-600)", marginBottom: 8 }}
        >
          Backend injoignable
        </div>
        <pre className="mono" style={{ fontSize: 12, color: "#7F1D1D", margin: 0 }}>
          uvicorn backend.main:app --reload --port 8000
        </pre>
      </div>
    );
  }
  if (!searchesQ.data?.length) {
    return (
      <>
        <div className="empty-state">
          <div className="empty-state__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <circle cx="12" cy="12" r="6" />
              <circle cx="12" cy="12" r="2" />
            </svg>
          </div>
          <div className="empty-state__title serif">Prêt à prospecter</div>
          <div className="empty-state__text">
            Lance un scrape depuis l'app Streamlit puis recharge cette page.
          </div>
        </div>
        <div className="oa-steps">
          <Step num={1} title="Définis ta cible">
            Saisis le métier (opticien, dentiste, garage…) et une liste de
            villes dans le formulaire au-dessus.
          </Step>
          <Step num={2} title="Lance le scraping">
            Google Maps + BCE/KBO + sites web sont interrogés pour récupérer
            n° TVA, dirigeants et données financières.
          </Step>
          <Step num={3} title="Appelle tes prospects">
            Push vers Ringover en un clic, click-to-call depuis chaque carte,
            et suivi du statut.
          </Step>
        </div>
      </>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Sélecteur de scrape */}
      <div className="card" style={{ padding: 20 }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--ink-500)",
            marginBottom: 8,
          }}
        >
          Scrape affiché
        </div>
        <ScrapeSelector
          searches={searchesQ.data}
          value={effectiveSearchId}
          onChange={setActiveSearchId}
        />
      </div>

      {/* Métriques */}
      {businessesQ.data && (
        <Metrics
          total={businessesQ.data.total}
          businesses={businessesQ.data.items}
        />
      )}

      {/* Filtres + recherche */}
      {businessesQ.data && (
        <div
          className="card"
          style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}
        >
          <FilterPills
            businesses={businessesQ.data.items}
            creditCounts={businessesQ.data.credit_counts}
            active={filter}
            onChange={setFilter}
          />
          <div style={{ position: "relative", maxWidth: 420 }}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="var(--ink-400)"
              strokeWidth="2"
              style={{
                position: "absolute",
                left: 12,
                top: "50%",
                transform: "translateY(-50%)",
                width: 16,
                height: 16,
              }}
            >
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Rechercher par nom, ville ou TVA…"
              style={{
                width: "100%",
                padding: "9px 14px 9px 38px",
                fontSize: 13,
                borderRadius: 10,
                border: "1px solid var(--ink-200)",
                outline: "none",
                fontFamily: "inherit",
                color: "var(--ink-900)",
                background: "var(--paper)",
              }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--indigo-600)";
                e.target.style.boxShadow = "0 0 0 3px rgba(79, 63, 240, 0.1)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "var(--ink-200)";
                e.target.style.boxShadow = "";
              }}
            />
          </div>
          <div style={{ fontSize: 11, color: "var(--ink-500)" }}>
            {filtered.length} fiche(s) affichée(s) sur {businessesQ.data.total}
          </div>
        </div>
      )}

      {/* Grille de cards */}
      {businessesQ.isLoading ? (
        <div className="empty-state">
          <div className="empty-state__title serif">Chargement des fiches…</div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state__title serif">
            Aucune fiche ne correspond aux filtres
          </div>
          <div className="empty-state__text">
            Réinitialise les filtres ou la recherche pour voir toutes les
            fiches.
          </div>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gap: 16,
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
          }}
        >
          {filtered.map((b) => (
            <BusinessCard key={b.dedup_key} business={b} />
          ))}
        </div>
      )}
    </div>
  );
}

function Metrics({
  total,
  businesses,
}: {
  total: number;
  businesses: BusinessSummary[];
}) {
  const top2 = businesses.filter(
    (b) => b.google_rank !== null && b.google_rank <= 2,
  ).length;
  const withPhone = businesses.filter((b) => b.phone).length;
  const withVat = businesses.filter((b) => b.vat_number).length;
  const withMgr = businesses.filter((b) => b.managers).length;
  const called = businesses.filter((b) => b.call_status === "Déjà appelé").length;

  return (
    <div
      style={{
        display: "grid",
        gap: 10,
        gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
      }}
    >
      <Metric label="Fiches" value={total} />
      <Metric label="Top 2 Google" value={top2} />
      <Metric label="Avec téléphone" value={withPhone} />
      <Metric label="Avec TVA" value={withVat} />
      <Metric label="Avec dirigeant" value={withMgr} />
      <Metric label="Déjà appelé" value={called} />
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="card" style={{ padding: "14px 16px" }}>
      <div
        className="serif"
        style={{
          fontSize: 24,
          fontWeight: 600,
          color: "var(--ink-900)",
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--ink-500)",
          marginTop: 6,
        }}
      >
        {label}
      </div>
    </div>
  );
}

function Step({
  num,
  title,
  children,
}: {
  num: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="oa-step">
      <div className="oa-step__num">{num}</div>
      <div className="oa-step__title">{title}</div>
      <div className="oa-step__text">{children}</div>
    </div>
  );
}

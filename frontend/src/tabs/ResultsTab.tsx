/**
 * Tab Résultats — table de prospects style Oui Allo original.
 * Sélecteur scrape + métriques + actions (Excel/Ringover/Supprimer) +
 * filtres pills + recherche + TABLE avec pagination.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSearchBusinesses, listSearches } from "../lib/api";
import { ScrapeSelector } from "../components/ScrapeSelector";
import { BusinessRow } from "../components/BusinessRow";
import {
  FilterPills,
  applyFilter,
  type FilterKey,
} from "../components/FilterPills";
import type { BusinessSummary } from "../lib/types";

const PAGE_SIZE = 25;

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
  const [page, setPage] = useState(0);

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

  // Reset page quand on change de scrape ou de filtre
  useMemo(() => setPage(0), [effectiveSearchId, filter, searchText]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages - 1);
  const startIdx = currentPage * PAGE_SIZE;
  const pageItems = filtered.slice(startIdx, startIdx + PAGE_SIZE);

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
            Lance un scrape via le formulaire au-dessus.
          </div>
        </div>
        <div className="oa-steps">
          <Step num={1} title="Définis ta cible">
            Saisis le métier et une liste de villes dans le formulaire ci-dessus.
          </Step>
          <Step num={2} title="Lance le scraping">
            Google Maps + BCE/KBO + BNB → fiches enrichies avec TVA, dirigeants,
            santé financière.
          </Step>
          <Step num={3} title="Appelle tes prospects">
            Push vers Ringover en un clic, suivi du statut.
          </Step>
        </div>
      </>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
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

      {/* Card titre + actions + filtres + table */}
      {businessesQ.data && (
        <div className="oa-results-card">
          {/* Titre + boutons d'action */}
          <div className="oa-action-row">
            <h2 className="oa-results-title">
              <em>{businessesQ.data.total} prospects</em> qualifiés
            </h2>
            <div className="oa-action-row__buttons">
              <button className="btn btn--excel" disabled title="À venir">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                Télécharger Excel
              </button>
              <button className="btn btn--excel" disabled title="À venir">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
                </svg>
                Exporter pour Ringover
              </button>
              <button className="btn btn--ghost" disabled title="À venir">
                Supprimer
              </button>
            </div>
          </div>

          {/* Filtres + recherche */}
          <div
            style={{
              display: "flex",
              gap: 16,
              alignItems: "flex-start",
              marginBottom: 16,
              flexWrap: "wrap",
            }}
          >
            <div style={{ flex: 1, minWidth: 280 }}>
              <FilterPills
                businesses={businessesQ.data.items}
                creditCounts={businessesQ.data.credit_counts}
                active={filter}
                onChange={setFilter}
              />
            </div>
            <div style={{ position: "relative", flex: "0 0 320px" }}>
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
                  background: "var(--paper)",
                }}
              />
            </div>
          </div>

          {/* Table */}
          {filtered.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__title serif">
                Aucune fiche ne correspond aux filtres
              </div>
              <div className="empty-state__text">
                Réinitialise les filtres ou la recherche.
              </div>
            </div>
          ) : (
            <>
              <div className="oa-table-wrap">
                <table className="oa-table">
                  <thead>
                    <tr>
                      <th>Entreprise</th>
                      <th>Métier</th>
                      <th>Commune</th>
                      <th>Téléphone</th>
                      <th>TVA</th>
                      <th>Site web</th>
                      <th>Qualité</th>
                      <th>Statut</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((b) => (
                      <BusinessRow key={b.dedup_key} business={b} />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="oa-pagination">
                  <div className="oa-pagination__info">
                    Affichage <strong>{startIdx + 1}–{startIdx + pageItems.length}</strong> sur{" "}
                    <strong>{filtered.length}</strong> prospects · page{" "}
                    {currentPage + 1} / {totalPages}
                  </div>
                  <div className="oa-pagination__nav">
                    <button
                      className="oa-page-btn"
                      onClick={() => setPage(Math.max(0, currentPage - 1))}
                      disabled={currentPage === 0}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M15 18l-6-6 6-6" />
                      </svg>
                    </button>
                    <span className="oa-page-current">
                      <strong>{currentPage + 1}</strong> / {totalPages}
                    </span>
                    <button
                      className="oa-page-btn"
                      onClick={() => setPage(Math.min(totalPages - 1, currentPage + 1))}
                      disabled={currentPage >= totalPages - 1}
                    >
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 18l6-6-6-6" />
                      </svg>
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
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
          fontSize: 28,
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

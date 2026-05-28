/**
 * Tab Campagne d'appels — liste des prospects par statut (À appeler, Déjà
 * appelé, À rappeler, Ne plus rappeler). Filtres pills + grille de cards.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCampaign } from "../lib/api";
import { BusinessCard } from "../components/BusinessCard";

const STATUSES = [
  "À appeler",
  "Déjà appelé",
  "À rappeler",
  "Ne plus rappeler",
] as const;

type StatusFilter = "Tous" | (typeof STATUSES)[number];

export function CampaignTab() {
  const campaignQ = useQuery({
    queryKey: ["campaign"],
    queryFn: () => getCampaign(),
  });

  const [filter, setFilter] = useState<StatusFilter>("Tous");
  const [searchText, setSearchText] = useState("");

  const filtered = useMemo(() => {
    if (!campaignQ.data) return [];
    let list = campaignQ.data.items;
    if (filter !== "Tous") {
      list = list.filter((b) => b.call_status === filter);
    }
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      list = list.filter((b) =>
        [b.name, b.locality, b.city, b.phone, b.managers]
          .some((f) => f?.toLowerCase().includes(q)),
      );
    }
    return list;
  }, [campaignQ.data, filter, searchText]);

  if (campaignQ.isLoading) {
    return (
      <div className="empty-state">
        <div className="empty-state__title serif">Chargement…</div>
      </div>
    );
  }
  if (campaignQ.error) {
    return (
      <div className="card" style={{ padding: 24 }}>
        <div style={{ color: "var(--red-600)", fontWeight: 600 }}>
          Erreur de chargement
        </div>
      </div>
    );
  }

  const counts = campaignQ.data?.status_counts || {};
  const total = campaignQ.data?.total || 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Métriques par statut */}
      <div
        style={{
          display: "grid",
          gap: 10,
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
        }}
      >
        <Metric
          label="Total"
          value={total}
          color="var(--ink-900)"
        />
        <Metric
          label="À appeler"
          value={counts["À appeler"] || 0}
          color="var(--indigo-700)"
        />
        <Metric
          label="Déjà appelé"
          value={counts["Déjà appelé"] || 0}
          color="var(--green-600)"
        />
        <Metric
          label="À rappeler"
          value={counts["À rappeler"] || 0}
          color="var(--red-600)"
        />
        <Metric
          label="Ne plus rappeler"
          value={counts["Ne plus rappeler"] || 0}
          color="var(--ink-500)"
        />
      </div>

      {/* Filtres */}
      <div
        className="card"
        style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          <StatusPill
            label={`Tous (${total})`}
            active={filter === "Tous"}
            onClick={() => setFilter("Tous")}
          />
          {STATUSES.map((s) => (
            <StatusPill
              key={s}
              label={`${s} (${counts[s] || 0})`}
              active={filter === s}
              onClick={() => setFilter(s)}
            />
          ))}
        </div>
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
            placeholder="Rechercher par nom, ville ou téléphone…"
            style={{
              width: "100%",
              padding: "9px 14px 9px 38px",
              fontSize: 13,
              borderRadius: 10,
              border: "1px solid var(--ink-200)",
              outline: "none",
              fontFamily: "inherit",
            }}
          />
        </div>
        <div style={{ fontSize: 11, color: "var(--ink-500)" }}>
          {filtered.length} fiche(s) affichée(s)
        </div>
      </div>

      {/* Grille */}
      {filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state__icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
            </svg>
          </div>
          <div className="empty-state__title serif">Pas de fiche dans cette vue</div>
          <div className="empty-state__text">
            Change de filtre ou lance un scrape pour avoir des prospects à appeler.
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

function StatusPill({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "7px 14px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        fontFamily: "inherit",
        cursor: "pointer",
        transition: "all .15s ease",
        border: "1px solid",
        borderColor: active ? "var(--indigo-900)" : "var(--ink-200)",
        background: active ? "var(--indigo-900)" : "var(--paper)",
        color: active ? "white" : "var(--ink-700)",
      }}
    >
      {label}
    </button>
  );
}

function Metric({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="card" style={{ padding: "14px 16px" }}>
      <div
        className="serif"
        style={{ fontSize: 24, fontWeight: 600, color, lineHeight: 1 }}
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

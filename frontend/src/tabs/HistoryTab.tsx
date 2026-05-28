/**
 * Tab Historique — stats globales + liste des scrapes historiques.
 */

import { useQuery } from "@tanstack/react-query";
import { getHistory } from "../lib/api";
import { formatRanAt } from "../lib/utils";

export function HistoryTab() {
  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: getHistory,
  });

  if (historyQ.isLoading) {
    return (
      <div className="empty-state">
        <div className="empty-state__title serif">Chargement…</div>
      </div>
    );
  }

  const stats = historyQ.data?.stats;
  const searches = historyQ.data?.searches || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Stats globales */}
      <div
        style={{
          display: "grid",
          gap: 10,
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        }}
      >
        <Metric
          label="Recherches lancées"
          value={stats?.total_searches ?? 0}
        />
        <Metric
          label="Prospects connus"
          value={stats?.total_businesses ?? 0}
        />
        <Metric
          label="Déjà appelés"
          value={stats?.total_called ?? 0}
        />
      </div>

      {/* Liste des scrapes */}
      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--ink-100)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <div
              className="serif"
              style={{
                fontSize: 17,
                fontWeight: 600,
                color: "var(--ink-900)",
              }}
            >
              Derniers scrapes
            </div>
            <div
              style={{
                fontSize: 12,
                color: "var(--ink-500)",
                marginTop: 2,
              }}
            >
              {searches.length} recherche{searches.length > 1 ? "s" : ""}{" "}
              historisée{searches.length > 1 ? "s" : ""}
            </div>
          </div>
        </div>
        {searches.length === 0 ? (
          <div className="empty-state" style={{ padding: 40 }}>
            <div className="empty-state__title serif">
              Aucun scrape dans l'historique
            </div>
            <div className="empty-state__text">
              Lance un scrape depuis l'app Streamlit pour démarrer.
            </div>
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "var(--cream)" }}>
                <Th>ID</Th>
                <Th>Métier</Th>
                <Th>Communes</Th>
                <Th>Date</Th>
                <Th style={{ textAlign: "right" }}>Fiches</Th>
                <Th style={{ textAlign: "right" }}>Nouvelles</Th>
              </tr>
            </thead>
            <tbody>
              {searches.map((s) => (
                <tr
                  key={s.id}
                  style={{ borderTop: "1px solid var(--ink-100)" }}
                >
                  <Td className="mono">#{s.id}</Td>
                  <Td>
                    <strong style={{ color: "var(--ink-900)" }}>
                      {s.query}
                    </strong>
                  </Td>
                  <Td
                    style={{
                      maxWidth: 280,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {s.cities || "—"}
                  </Td>
                  <Td style={{ color: "var(--ink-500)" }}>
                    {formatRanAt(s.ran_at)}
                  </Td>
                  <Td style={{ textAlign: "right" }}>{s.total}</Td>
                  <Td style={{ textAlign: "right" }}>
                    {s.new_count > 0 ? (
                      <span
                        style={{
                          padding: "3px 9px",
                          background: "var(--green-50)",
                          color: "var(--green-600)",
                          borderRadius: 999,
                          fontSize: 11,
                          fontWeight: 700,
                        }}
                      >
                        +{s.new_count}
                      </span>
                    ) : (
                      <span style={{ color: "var(--ink-400)" }}>—</span>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="card" style={{ padding: "18px 20px" }}>
      <div
        className="serif"
        style={{
          fontSize: 32,
          fontWeight: 600,
          color: "var(--ink-900)",
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: 10.5,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "var(--ink-500)",
          marginTop: 8,
        }}
      >
        {label}
      </div>
    </div>
  );
}

function Th({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <th
      style={{
        padding: "12px 16px",
        textAlign: "left",
        fontSize: 10.5,
        fontWeight: 700,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: "var(--ink-500)",
        ...style,
      }}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  style,
  className,
}: {
  children: React.ReactNode;
  style?: React.CSSProperties;
  className?: string;
}) {
  return (
    <td
      className={className}
      style={{
        padding: "12px 16px",
        fontSize: 13,
        color: "var(--ink-700)",
        ...style,
      }}
    >
      {children}
    </td>
  );
}

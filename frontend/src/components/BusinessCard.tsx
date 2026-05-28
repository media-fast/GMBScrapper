/**
 * BusinessCard — version Oui Allo.
 *
 * Style cohérent avec le template original (palette indigo, ink, cream)
 * + le helper .credit-pill du fichier oui-allo.css.
 */

import { Link } from "react-router-dom";
import type { BusinessSummary } from "../lib/types";
import { CREDIT_PALETTE, parseCreditReasons } from "../lib/utils";

interface Props {
  business: BusinessSummary;
}

export function BusinessCard({ business: b }: Props) {
  const reasons = parseCreditReasons(b.credit_reasons);
  const subLine = [b.category, b.locality || b.city].filter(Boolean).join(" · ");

  return (
    <article
      className="card"
      style={{
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        transition: "box-shadow .2s, transform .15s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "var(--shadow-md)";
        e.currentTarget.style.transform = "translateY(-1px)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "var(--shadow-sm)";
        e.currentTarget.style.transform = "";
      }}
    >
      {/* Header : nom + rank badge */}
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 12,
        }}
      >
        <h3
          className="serif"
          style={{
            fontSize: 17,
            fontWeight: 600,
            color: "var(--ink-900)",
            lineHeight: 1.25,
            margin: 0,
            flex: 1,
          }}
        >
          {b.name}
        </h3>
        <RankBadge rank={b.google_rank} />
      </header>

      {subLine && (
        <div style={{ fontSize: 12, color: "var(--ink-500)" }}>{subLine}</div>
      )}

      {/* Pills statut + crédit */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <StatusPill status={b.call_status || "À appeler"} />
        {b.credit_color && (
          <span
            className={`credit-pill credit-pill--${b.credit_color}`}
            title={reasons.join(" · ")}
            style={{ cursor: reasons.length > 0 ? "help" : "default" }}
          >
            {b.credit_label || CREDIT_PALETTE[b.credit_color].label}
          </span>
        )}
      </div>

      {/* Bloc infos compactes */}
      <ul
        style={{
          margin: 0,
          padding: 0,
          listStyle: "none",
          display: "flex",
          flexDirection: "column",
          gap: 6,
          fontSize: 13,
          color: "var(--ink-700)",
          marginTop: 4,
        }}
      >
        {b.phone && (
          <InfoRow icon={<PhoneSvg />}>
            <a
              href={`tel:${b.phone}`}
              onClick={(e) => e.stopPropagation()}
              style={{ color: "var(--ink-900)", textDecoration: "none" }}
            >
              {b.phone}
            </a>
          </InfoRow>
        )}
        {b.email && (
          <InfoRow icon={<MailSvg />}>
            <a
              href={`mailto:${b.email}`}
              style={{
                color: "var(--ink-900)",
                textDecoration: "none",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                display: "block",
              }}
            >
              {b.email}
            </a>
          </InfoRow>
        )}
        {b.vat_number && (
          <InfoRow icon={<BriefcaseSvg />}>
            <code
              className="mono"
              style={{ fontSize: 11.5, color: "var(--indigo-700)" }}
            >
              {b.vat_number}
            </code>
          </InfoRow>
        )}
        {b.managers && (
          <InfoRow icon={<UsersSvg />}>
            <span
              style={{
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                display: "block",
              }}
            >
              {b.managers}
            </span>
          </InfoRow>
        )}
        {b.rating !== null && b.rating !== undefined && (
          <InfoRow icon={<StarSvg color="var(--gold)" />}>
            <strong style={{ fontWeight: 600 }}>{b.rating}</strong>
            <span style={{ color: "var(--ink-400)", marginLeft: 4 }}>
              ({b.reviews_count ?? 0} avis)
            </span>
          </InfoRow>
        )}
      </ul>

      {/* Action */}
      <Link
        to={`/business/${encodeURIComponent(b.dedup_key)}`}
        className="btn btn--primary"
        style={{
          marginTop: "auto",
          paddingTop: 8,
          paddingBottom: 8,
          fontSize: 12,
        }}
      >
        Détails
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          style={{ width: 13, height: 13 }}
        >
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </Link>
    </article>
  );
}

function InfoRow({
  icon,
  children,
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <li
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 8,
      }}
    >
      <span
        style={{
          flexShrink: 0,
          color: "var(--indigo-600)",
          display: "inline-flex",
          marginTop: 2,
        }}
      >
        {icon}
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>{children}</div>
    </li>
  );
}

function RankBadge({ rank }: { rank: number | null }) {
  if (!rank) return null;
  if (rank === 1) {
    return (
      <span
        className="rank-badge"
        style={{ margin: 0, fontSize: 10.5 }}
      >
        <svg viewBox="0 0 24 24" fill="currentColor">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
        </svg>
        N°1
      </span>
    );
  }
  if (rank === 2) {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "4px 10px",
          background: "linear-gradient(135deg, #E2E8F0, #CBD5E1)",
          color: "#475569",
          borderRadius: 999,
          fontSize: 10.5,
          fontWeight: 700,
        }}
      >
        N°2
      </span>
    );
  }
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "4px 9px",
        background: "var(--ink-100)",
        color: "var(--ink-500)",
        borderRadius: 6,
        fontSize: 10.5,
        fontWeight: 600,
      }}
    >
      N°{rank}
    </span>
  );
}

const STATUS_PALETTE: Record<string, { bg: string; fg: string }> = {
  "À appeler": { bg: "var(--indigo-100)", fg: "var(--indigo-700)" },
  "Déjà appelé": { bg: "var(--green-50)", fg: "var(--green-600)" },
  "À rappeler": { bg: "var(--red-50)", fg: "var(--red-600)" },
  "Ne plus rappeler": { bg: "var(--ink-100)", fg: "var(--ink-500)" },
};

function StatusPill({ status }: { status: string }) {
  const palette =
    STATUS_PALETTE[status] || { bg: "var(--ink-100)", fg: "var(--ink-500)" };
  return (
    <span
      className="status-pill"
      style={{ background: palette.bg, color: palette.fg }}
    >
      {status}
    </span>
  );
}

// ─── SVG icons ────────────────────────────────────────────────────────

function PhoneSvg() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
    </svg>
  );
}
function MailSvg() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}
function BriefcaseSvg() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16" />
    </svg>
  );
}
function UsersSvg() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
    </svg>
  );
}
function StarSvg({ color = "currentColor" }: { color?: string }) {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill={color}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}

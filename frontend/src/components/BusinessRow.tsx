/**
 * BusinessRow — ligne de table dans la liste des prospects (style Oui Allo
 * original avec colonnes Entreprise / Métier / Commune / Téléphone / TVA /
 * Site web / Qualité / Statut / Action).
 */

import { Link } from "react-router-dom";
import type { BusinessSummary } from "../lib/types";
import { completenessScore } from "../lib/utils";

interface Props {
  business: BusinessSummary;
}

export function BusinessRow({ business: b }: Props) {
  const initials = computeInitials(b.name);
  const score = completenessScore(b);
  const status = computeStatus(b);
  const url = b.website
    ? b.website.replace(/^https?:\/\//, "").replace(/\/$/, "")
    : "";

  return (
    <tr>
      {/* Entreprise (avatar + nom + adresse) */}
      <td>
        <div className="oa-table__entreprise">
          <span className="oa-avatar">{initials}</span>
          <div style={{ minWidth: 0 }}>
            <div className="oa-table__name">
              <Link to={`/business/${encodeURIComponent(b.dedup_key)}`}>
                {b.name}
              </Link>
            </div>
            {b.address && <div className="oa-table__addr">{b.address}</div>}
          </div>
        </div>
      </td>

      {/* Métier (chip) */}
      <td>
        {b.category ? (
          <span className="oa-metier-chip">{b.category}</span>
        ) : (
          <span className="oa-tva--missing">—</span>
        )}
      </td>

      {/* Commune */}
      <td>{b.locality || b.city || "—"}</td>

      {/* Téléphone */}
      <td>
        {b.phone ? (
          <a
            href={`tel:${b.phone}`}
            style={{ color: "var(--ink-900)", textDecoration: "none" }}
          >
            {b.phone}
          </a>
        ) : (
          <span className="oa-tva--missing">non trouvé</span>
        )}
      </td>

      {/* TVA */}
      <td>
        {b.vat_number ? (
          <span className="oa-tva--present">{b.vat_number}</span>
        ) : (
          <span className="oa-tva--missing">non trouvée</span>
        )}
      </td>

      {/* Site web */}
      <td>
        {b.website ? (
          <a
            href={b.website}
            target="_blank"
            rel="noopener noreferrer"
            className="oa-site-link"
          >
            {url.length > 30 ? url.slice(0, 30) + "…" : url}
          </a>
        ) : (
          <span className="oa-tva--missing">—</span>
        )}
      </td>

      {/* Qualité */}
      <td>
        <div className="oa-quality">
          <div className="oa-quality__bar">
            <div
              className="oa-quality__fill"
              style={{ width: `${score}%` }}
            />
          </div>
          <span className="oa-quality__num">{score}</span>
        </div>
      </td>

      {/* Statut */}
      <td>
        <span className={`oa-status oa-status--${status.cls}`}>
          {status.label}
        </span>
      </td>

      {/* Action */}
      <td>
        <div className="oa-actions">
          {b.phone ? (
            <a
              href={`tel:${b.phone}`}
              className="oa-action-btn oa-action-btn--call"
              title="Appeler"
              onClick={(e) => e.stopPropagation()}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
              </svg>
            </a>
          ) : (
            <button
              className="oa-action-btn oa-action-btn--info"
              disabled
              title="Pas de téléphone"
              style={{ opacity: 0.4, cursor: "not-allowed" }}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72 12.84 12.84 0 00.7 2.81 2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45 12.84 12.84 0 002.81.7A2 2 0 0122 16.92z" />
                <line x1="2" y1="2" x2="22" y2="22" />
              </svg>
            </button>
          )}
          <Link
            to={`/business/${encodeURIComponent(b.dedup_key)}`}
            className="oa-action-btn oa-action-btn--info"
            title="Voir détails"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
          </Link>
        </div>
      </td>
    </tr>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────

function computeInitials(name: string): string {
  const cleaned = (name || "").replace(/[^A-Za-zÀ-ÿ ]/g, " ").trim();
  const parts = cleaned.split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function computeStatus(b: BusinessSummary): { cls: string; label: string } {
  if (!b.phone) return { cls: "phone-missing", label: "Sans téléphone" };
  if (!b.vat_number) return { cls: "tva-missing", label: "TVA manquante" };
  if (!b.website) return { cls: "site-missing", label: "Pas de site" };
  return { cls: "complet", label: "Complet" };
}

/**
 * ScrapeProgressPanel — port du _render_progress_panel + _render_done_panel
 * Streamlit.
 *
 * - Pendant le scrape : fond ink-900 + pulse dot vert + stats + log tail
 * - Une fois terminé : fond green gradient + breakdown des pertes + auto-jump
 *   vers la nouvelle recherche dans le tab Résultats
 * - Polling 1.5 s via TanStack Query
 */

import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getScrapeProgress } from "../lib/api";
import type { ScrapeProgress } from "../lib/types";

interface Props {
  scrapeId: string;
  onDone?: (searchId: number) => void;
  onDismiss?: () => void;
}

const PHASE_LABEL: Record<string, string> = {
  scraping: "Scraping Google Maps",
  filtering: "Filtre ville",
  dedup_seen: "Dédup historique",
  enrichment: "Enrichissement TVA / BCE",
  dedup_post: "Dédup post-BCE",
  saving: "Sauvegarde",
  done: "Recherche terminée",
  cancelled: "Recherche annulée",
  error: "Erreur durant le scraping",
};

export function ScrapeProgressPanel({ scrapeId, onDone, onDismiss }: Props) {
  const qc = useQueryClient();

  const { data: progress } = useQuery({
    queryKey: ["scrape-progress", scrapeId],
    queryFn: () => getScrapeProgress(scrapeId),
    refetchInterval: (q) => {
      const p = q.state.data as ScrapeProgress | undefined;
      return p?.active ? 1500 : false;
    },
    refetchIntervalInBackground: true,
  });

  // À la fin du scrape : invalider les caches dépendants + appeler onDone
  useEffect(() => {
    if (!progress) return;
    if (progress.phase === "done" && progress.result_search_id != null) {
      // Recharge la liste des scrapes pour faire apparaître le nouveau
      qc.invalidateQueries({ queryKey: ["searches"] });
      qc.invalidateQueries({ queryKey: ["history"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
      onDone?.(progress.result_search_id);
    }
  }, [progress, qc, onDone]);

  if (!progress) {
    return null;
  }

  const isDone = progress.phase === "done";
  const isError = progress.phase === "error";
  const isCancelled = progress.phase === "cancelled";
  const phaseLabel = PHASE_LABEL[progress.phase] || progress.phase;

  // Calcule durée
  const duration = computeDuration(progress.started_at, progress.ended_at);

  const bg = isDone
    ? "linear-gradient(135deg, #0F6B36, #1F9D55)"
    : isError
      ? "linear-gradient(135deg, #7F1D1D, #B91C1C)"
      : "var(--ink-900)";

  return (
    <div className="oa-form-card">
      <section
        style={{
          background: bg,
          color: "white",
          borderRadius: 22,
          padding: "26px 30px",
          position: "relative",
          overflow: "hidden",
          boxShadow: "var(--shadow-md)",
        }}
      >
        {/* Glow décoratif */}
        <div
          style={{
            position: "absolute",
            top: "-50%",
            right: "-10%",
            width: 400,
            height: 400,
            background:
              "radial-gradient(circle, rgba(107, 95, 255, 0.25) 0%, transparent 60%)",
            pointerEvents: "none",
          }}
        />

        {/* Header */}
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: 22,
            position: "relative",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span
              className={isDone ? "" : "scrape-pulse"}
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: isDone
                  ? "white"
                  : isError
                    ? "#FEE2E2"
                    : "#6EE7B7",
                flexShrink: 0,
              }}
            />
            <div>
              <h3
                className="serif"
                style={{
                  fontSize: 22,
                  fontWeight: 600,
                  margin: 0,
                  letterSpacing: "-0.01em",
                }}
              >
                {phaseLabel}
              </h3>
              <div
                style={{
                  fontSize: 12.5,
                  color: "rgba(255,255,255,0.7)",
                  marginTop: 4,
                }}
              >
                {progress.cities_total} ville(s) × {progress.variants_total}{" "}
                variante(s)
                {duration && ` · ${duration}`}
              </div>
            </div>
          </div>
          {(isDone || isError || isCancelled) && onDismiss && (
            <button
              onClick={onDismiss}
              style={{
                background: "rgba(255,255,255,0.1)",
                border: "1px solid rgba(255,255,255,0.2)",
                color: "white",
                borderRadius: 8,
                padding: "6px 12px",
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              Fermer
            </button>
          )}
        </header>

        {/* Stats grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))",
            gap: 16,
            position: "relative",
          }}
        >
          <Stat label="Villes" value={progress.cities_total} />
          <Stat label="Variantes" value={progress.variants_total} />
          <Stat
            label={isDone ? "Prospects finaux" : "Bruts"}
            value={isDone ? progress.result_count : progress.prospects_brut}
            sub={
              isDone
                ? `/ ${progress.prospects_brut} bruts`
                : undefined
            }
          />
          <Stat
            label="Enrich. TVA"
            value={progress.vat_enriched}
            sub={`/ ${progress.result_count || "—"}`}
          />
          <Stat
            label="Statut"
            value={isDone ? "✓" : isError ? "✗" : "…"}
            small
          />
        </div>

        {/* Loss breakdown (seulement à la fin) */}
        {isDone && progress.prospects_brut > progress.result_count && (
          <LossBreakdown
            losses={progress.losses}
            diff={progress.prospects_brut - progress.result_count}
          />
        )}

        {/* Erreur */}
        {(isError || progress.error) && (
          <div
            style={{
              marginTop: 18,
              padding: "12px 14px",
              background: "rgba(255,255,255,0.1)",
              borderRadius: 10,
              fontSize: 12.5,
              borderLeft: "3px solid #FEE2E2",
            }}
          >
            {progress.error || "Une erreur est survenue."}
          </div>
        )}

        {/* Google bloqué warning */}
        {progress.google_blocked && (
          <div
            style={{
              marginTop: 18,
              padding: "14px 16px",
              background: "rgba(255, 200, 100, 0.15)",
              borderRadius: 10,
              fontSize: 12.5,
              borderLeft: "3px solid #FCD34D",
            }}
          >
            ⚠ <strong>Google a bloqué l'IP</strong> — change d'IP (VPN,
            4G), désactive le headless ou réduis le batch pour relancer.
          </div>
        )}

        {/* Log tail */}
        {progress.log_tail.length > 0 && (
          <details
            style={{
              marginTop: 18,
              fontSize: 11.5,
              color: "rgba(255,255,255,0.7)",
              position: "relative",
            }}
          >
            <summary
              style={{
                cursor: "pointer",
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                fontWeight: 600,
                fontSize: 10.5,
              }}
            >
              Logs ({progress.log_tail.length} dernières lignes)
            </summary>
            <ul
              className="mono"
              style={{
                marginTop: 8,
                padding: "10px 14px",
                background: "rgba(0,0,0,0.3)",
                borderRadius: 8,
                listStyle: "none",
                fontSize: 11,
                lineHeight: 1.6,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {progress.log_tail.map((line, i) => (
                <li key={i}>{line}</li>
              ))}
            </ul>
          </details>
        )}
      </section>
      <style>{`
        @keyframes scrape-pulse-anim {
          0% { box-shadow: 0 0 0 0 rgba(110, 231, 183, 0.7); }
          70% { box-shadow: 0 0 0 12px rgba(110, 231, 183, 0); }
          100% { box-shadow: 0 0 0 0 rgba(110, 231, 183, 0); }
        }
        .scrape-pulse { animation: scrape-pulse-anim 1.6s infinite; }
      `}</style>
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────

function Stat({
  label,
  value,
  sub,
  small,
}: {
  label: string;
  value: string | number;
  sub?: string;
  small?: boolean;
}) {
  return (
    <div>
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.55)",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        className="serif"
        style={{
          fontSize: small ? 24 : 32,
          fontWeight: 600,
          color: "white",
          letterSpacing: "-0.02em",
          lineHeight: 1,
          display: "flex",
          alignItems: "baseline",
          gap: 6,
        }}
      >
        {value}
        {sub && (
          <span
            style={{
              fontSize: 12,
              color: "rgba(255,255,255,0.55)",
              fontWeight: 500,
              fontFamily: "Inter, sans-serif",
            }}
          >
            {sub}
          </span>
        )}
      </div>
    </div>
  );
}

const LOSS_LABELS: Record<string, string> = {
  city_filter: "hors zone (filtre ville)",
  dedup_seen: "déjà connues (dédup historique)",
  dedup_post_bce: "doublons BCE révélés après enrichissement",
  dedup_intra: "chaînes (même BCE + même localité)",
  phone_filter: "sans téléphone (filtre obligatoire)",
};

function LossBreakdown({
  losses,
  diff,
}: {
  losses: Record<string, number>;
  diff: number;
}) {
  const rows = Object.entries(LOSS_LABELS)
    .filter(([k]) => (losses[k] || 0) > 0)
    .map(([k, label]) => ({ key: k, label, n: losses[k] }));

  if (rows.length === 0) return null;

  return (
    <div
      style={{
        marginTop: 18,
        paddingTop: 14,
        borderTop: "1px solid rgba(255,255,255,0.18)",
        position: "relative",
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.55)",
          fontWeight: 600,
          marginBottom: 10,
        }}
      >
        Détail des {diff} fiches écartées
      </div>
      {rows.map((r) => (
        <div
          key={r.key}
          style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "4px 0",
            fontSize: 12.5,
          }}
        >
          <span style={{ color: "rgba(255,255,255,0.7)" }}>– {r.label}</span>
          <span style={{ fontWeight: 600 }}>−{r.n}</span>
        </div>
      ))}
    </div>
  );
}

function computeDuration(
  startedAt: string | null,
  endedAt: string | null,
): string | null {
  if (!startedAt) return null;
  const start = new Date(startedAt.replace(" ", "T")).getTime();
  const end = endedAt
    ? new Date(endedAt.replace(" ", "T")).getTime()
    : Date.now();
  if (!start || !end || end < start) return null;
  const secs = Math.floor((end - start) / 1000);
  const mins = Math.floor(secs / 60);
  const s = secs % 60;
  return mins
    ? `${mins} min ${s.toString().padStart(2, "0")} s`
    : `${s} s`;
}

/**
 * Page Détail entreprise — port 1:1 du template Oui Allo
 * (_build_detail_visual_html dans app.py Streamlit).
 *
 * Structure :
 *   .action-bar (breadcrumb + tracking strip + actions)
 *   .shell
 *     ├ .sidebar
 *     │   ├ .card.identity-card (rank badge + nom + sub + score panel + contact list)
 *     │   └ .card.admins-card (dirigeants)
 *     └ .main
 *         ├ .tabs (Évaluation / Identité légale / Historique)
 *         ├ panel Évaluation : 3 .eval-card (santé / présence / signaux)
 *         ├ panel Identité légale : 2 .accordion
 *         └ panel Historique : empty-state ou data-grid
 *
 * Tout le styling vient de styles/oui-allo.css — pas de Tailwind ici.
 */

import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBusinessDetail } from "../lib/api";
import type { BusinessDetail } from "../lib/types";
import { CREDIT_PALETTE, parseCreditReasons } from "../lib/utils";

type TabKey = "evaluation" | "identite" | "historique";

export function BusinessDetailPage() {
  const { dedupKey } = useParams<{ dedupKey: string }>();
  const key = dedupKey ? decodeURIComponent(dedupKey) : "";

  const { data: b, isLoading, error } = useQuery({
    queryKey: ["business", key],
    queryFn: () => getBusinessDetail(key),
    enabled: !!key,
  });

  const [tab, setTab] = useState<TabKey>("evaluation");

  // ─── Active la classe oui-allo sur <body> uniquement sur cette page
  useEffect(() => {
    document.body.classList.add("oui-allo");
    return () => document.body.classList.remove("oui-allo");
  }, []);

  if (isLoading) {
    return (
      <div className="empty-state">
        <div className="empty-state__title serif">Chargement…</div>
      </div>
    );
  }
  if (error || !b) {
    return (
      <div className="empty-state">
        <div className="empty-state__title serif">Fiche introuvable</div>
        <Link to="/" className="btn btn--ghost" style={{ marginTop: 20 }}>
          ← Retour aux résultats
        </Link>
      </div>
    );
  }

  // ─── Données dérivées ─────────────────────────────────────────────
  const subtitleParts = [
    b.legal_form,
    b.category,
    b.city ? `${b.city}, BE` : null,
  ].filter(Boolean);
  const subtitle = subtitleParts.join(" · ");

  const yearMatch = b.creation_date?.match(/(\d{4})/);
  const yearCreated = yearMatch ? parseInt(yearMatch[1], 10) : null;
  const age =
    yearCreated !== null ? Math.max(0, new Date().getFullYear() - yearCreated) : null;

  const status = b.call_status || "À appeler";
  const pulseColor =
    status === "À rappeler" ? "var(--red-600)" : "var(--amber-700)";

  // ─── Render ───────────────────────────────────────────────────────
  return (
    <>
      {/* Action bar (breadcrumb + tracking + actions) */}
      <div className="action-bar">
        <div className="action-bar__inner">
          <div className="breadcrumb">
            <Link
              to="/"
              style={{ color: "inherit", textDecoration: "none" }}
            >
              Prospects
            </Link>
            <ChevronSmall />
            <span>{b.city || "—"}</span>
            <ChevronSmall />
            <span style={{ color: "var(--ink-900)", fontWeight: 500 }}>
              {b.name}
            </span>
          </div>

          <div className="tracking-strip">
            <div className="tracking-cell">
              <span className="tracking-cell__label">Statut</span>
              <span className="tracking-cell__value">
                <span
                  className="pulse-dot"
                  style={{ background: pulseColor }}
                />
                {status}
              </span>
            </div>
            <div className="tracking-cell">
              <span className="tracking-cell__label">Dernier appel</span>
              <span
                className="tracking-cell__value"
                style={{ color: "var(--ink-400)" }}
              >
                —
              </span>
            </div>
            <div className="tracking-cell">
              <span className="tracking-cell__label">Rappel</span>
              <span
                className="tracking-cell__value"
                style={{ color: "var(--ink-400)" }}
              >
                —
              </span>
            </div>
          </div>

          <div className="actions">
            {b.phone && (
              <a
                href={`tel:${b.phone}`}
                className="btn btn--call"
                title="Appeler maintenant"
              >
                <PhoneIcon />
                Appeler
              </a>
            )}
            <Link to="/" className="btn btn--ghost btn--icon" title="Retour">
              <BackIcon />
            </Link>
          </div>
        </div>
      </div>

      {/* Shell = sidebar + main */}
      <div className="shell">
        <Sidebar b={b} subtitle={subtitle} age={age} yearCreated={yearCreated} />
        <Main b={b} tab={tab} onTab={setTab} />
      </div>
    </>
  );
}

// ─── SIDEBAR ────────────────────────────────────────────────────────

function Sidebar({
  b,
  subtitle,
  age,
  yearCreated,
}: {
  b: BusinessDetail;
  subtitle: string;
  age: number | null;
  yearCreated: number | null;
}) {
  const managers =
    b.managers
      ?.split(/[,;\n]+/)
      .map((m) => m.trim())
      .filter(Boolean)
      .slice(0, 8) || [];

  return (
    <aside className="sidebar">
      <div className="card">
        <div className="identity-card">
          {b.google_rank && (
            <div className="rank-badge">
              <StarIcon />
              Prospect N°{b.google_rank}{b.google_rank === 1 ? "er" : "e"}
            </div>
          )}
          <h1 className="company-name">{b.name}</h1>
          {subtitle && <p className="company-form">{subtitle}</p>}

          {(b.rating || age !== null) && (
            <div className="score-panel">
              {b.rating && (
                <div className="score-block">
                  <div className="score-block__label">Réputation Google</div>
                  <div className="score-block__value">
                    {b.rating} <small>/5</small>
                  </div>
                  <div className="stars">
                    {"★".repeat(Math.round(b.rating))}
                    {"☆".repeat(Math.max(0, 5 - Math.round(b.rating)))}
                  </div>
                  <div className="reviews-count">{b.reviews_count ?? 0} avis</div>
                </div>
              )}
              {age !== null && (
                <div className="score-block">
                  <div className="score-block__label">Ancienneté</div>
                  <div className="score-block__value">
                    {age} <small>ans</small>
                  </div>
                  <div
                    className="reviews-count"
                    style={{ marginTop: 16 }}
                  >
                    depuis {yearCreated}
                  </div>
                </div>
              )}
            </div>
          )}

          <ContactList b={b} />
        </div>

        <div className="ai-footer">
          <span className="ai-dot" />
          <span>
            Enrichissement IA ·{" "}
            <strong style={{ color: "var(--ink-700)" }}>POC React</strong>
          </span>
        </div>
      </div>

      {managers.length > 0 && (
        <div className="card admins-card">
          <div className="admins-card__title">
            <UsersIcon />
            Dirigeants
          </div>
          {managers.map((name) => (
            <AdminRow key={name} name={name} />
          ))}
        </div>
      )}
    </aside>
  );
}

function ContactList({ b }: { b: BusinessDetail }) {
  const reasons = parseCreditReasons(b.credit_reasons);
  const fullAddr = b.address
    ? b.postal_code && b.locality && !b.address.includes(b.postal_code)
      ? `${b.address}, ${b.postal_code} ${b.locality}`
      : b.address
    : null;

  return (
    <div className="contact-list">
      {b.phone && (
        <a href={`tel:${b.phone}`} className="contact-item">
          <span className="contact-item__icon">
            <PhoneIcon />
          </span>
          <div className="contact-item__main">
            <div className="contact-item__label">Téléphone</div>
            <div className="contact-item__value">{b.phone}</div>
          </div>
          <ArrowIcon />
        </a>
      )}
      {b.email && (
        <a href={`mailto:${b.email}`} className="contact-item">
          <span className="contact-item__icon">
            <MailIcon />
          </span>
          <div className="contact-item__main">
            <div className="contact-item__label">Email</div>
            <div className="contact-item__value">{b.email}</div>
          </div>
          <ArrowIcon />
        </a>
      )}
      {b.website && (
        <div className="website-block">
          <a
            href={b.website}
            target="_blank"
            rel="noopener noreferrer"
            className="website-block__main"
          >
            <span className="website-block__icon">
              <GlobeIcon />
            </span>
            <div className="website-block__info">
              <div className="website-block__label">Site web</div>
              <div className="website-block__url">
                {b.website.replace(/^https?:\/\//, "").replace(/\/$/, "")}
              </div>
            </div>
            <ExtArrowIcon />
          </a>

          {/* Bloc santé financière */}
          {b.credit_color && (
            <div
              style={{
                marginTop: 12,
                padding: "12px 14px",
                background: "var(--cream)",
                borderRadius: 11,
                border: "1px solid var(--ink-100)",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                  marginBottom: 4,
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    color: "var(--ink-500)",
                  }}
                >
                  Santé financière
                </div>
                <span
                  className={`credit-pill credit-pill--${b.credit_color}`}
                  title={reasons.join(" · ")}
                >
                  {b.credit_label || CREDIT_PALETTE[b.credit_color].label}
                </span>
              </div>
              {reasons.length > 0 && (
                <ul
                  style={{
                    margin: "8px 0 0 0",
                    paddingLeft: 18,
                    listStyle: "none",
                  }}
                >
                  {reasons.slice(0, 4).map((r, i) => (
                    <li
                      key={i}
                      style={{
                        margin: "4px 0",
                        fontSize: 12,
                        color: "var(--ink-700)",
                        lineHeight: 1.45,
                        position: "relative",
                      }}
                    >
                      <span
                        style={{
                          position: "absolute",
                          left: -12,
                          color: "var(--ink-400)",
                        }}
                      >
                        •
                      </span>
                      {r}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
      {fullAddr && (
        <a
          href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(b.address || "")}`}
          target="_blank"
          rel="noopener noreferrer"
          className="contact-item"
        >
          <span className="contact-item__icon">
            <MapPinIcon />
          </span>
          <div className="contact-item__main">
            <div className="contact-item__label">Adresse</div>
            <div className="contact-item__value">{fullAddr}</div>
          </div>
          <ArrowIcon />
        </a>
      )}
    </div>
  );
}

function AdminRow({ name }: { name: string }) {
  const parts = name.split(" ").filter(Boolean);
  const initials =
    parts.length >= 2
      ? (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
      : name.slice(0, 2).toUpperCase();
  return (
    <div className="admin-row">
      <div className="admin-avatar">{initials}</div>
      <div className="admin-info">
        <div className="admin-name">{name}</div>
        <div className="admin-role">Administrateur</div>
      </div>
      <a
        href={`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(name)}`}
        target="_blank"
        rel="noopener noreferrer"
        className="admin-action"
        title="Rechercher sur LinkedIn"
      >
        <SearchIcon />
      </a>
    </div>
  );
}

// ─── MAIN (tabs) ────────────────────────────────────────────────────

function Main({
  b,
  tab,
  onTab,
}: {
  b: BusinessDetail;
  tab: TabKey;
  onTab: (t: TabKey) => void;
}) {
  return (
    <main className="main">
      <div className="tabs" role="tablist">
        <button
          className={`tab ${tab === "evaluation" ? "is-active" : ""}`}
          onClick={() => onTab("evaluation")}
          role="tab"
        >
          <StarIcon />
          Évaluation
        </button>
        <button
          className={`tab ${tab === "identite" ? "is-active" : ""}`}
          onClick={() => onTab("identite")}
          role="tab"
        >
          <BuildingIcon />
          Identité légale
        </button>
        <button
          className={`tab ${tab === "historique" ? "is-active" : ""}`}
          onClick={() => onTab("historique")}
          role="tab"
        >
          <ClockIcon />
          Historique
        </button>
      </div>

      <section className={`panel ${tab === "evaluation" ? "is-active" : ""}`}>
        <EvaluationPanel b={b} />
      </section>
      <section className={`panel ${tab === "identite" ? "is-active" : ""}`}>
        <IdentitePanel b={b} />
      </section>
      <section className={`panel ${tab === "historique" ? "is-active" : ""}`}>
        <HistoriquePanel b={b} />
      </section>
    </main>
  );
}

// ─── PANELS ─────────────────────────────────────────────────────────

function EvaluationPanel({ b }: { b: BusinessDetail }) {
  // Santé financière (BNB)
  const finRows: { icon: React.ReactNode; label: string; value: React.ReactNode }[] = [];
  if (b.creation_date)
    finRows.push({
      icon: <ClockIcon />,
      label: "Activité depuis",
      value: b.creation_date,
    });
  finRows.push({
    icon: <CheckCircleIcon />,
    label: "Statut BCE",
    value: (
      <span
        className="status-pill"
        style={{ background: "var(--green-50)", color: "var(--green-600)" }}
      >
        {b.bce_status || "Actif"}
      </span>
    ),
  });
  if (b.nbb_year)
    finRows.push({
      icon: <ClockIcon />,
      label: "Dernier exercice",
      value: b.nbb_year,
    });
  if (b.nbb_deposit_date)
    finRows.push({
      icon: <ClockIcon />,
      label: "Date de dépôt",
      value: b.nbb_deposit_date,
    });
  if (b.nbb_deposits_count)
    finRows.push({
      icon: <BuildingIcon />,
      label: "Total dépôts BNB",
      value: String(b.nbb_deposits_count),
    });

  // Présence locale
  const locRows: { icon: React.ReactNode; label: string; value: string }[] = [];
  const cityLabel = (b.locality || b.city || "") + (b.postal_code ? ` (${b.postal_code})` : "");
  if (cityLabel.trim())
    locRows.push({ icon: <MapPinIcon />, label: "Ville", value: cityLabel });
  locRows.push({ icon: <GlobeIcon />, label: "Pays", value: "Belgique" });
  if (b.category)
    locRows.push({ icon: <GridIcon />, label: "Catégorie Google", value: b.category });

  // Signaux qualifiants
  const signals: { label: string; value: React.ReactNode }[] = [];
  if (b.reviews_count) {
    signals.push({
      label: "Volume d'avis",
      value: `${b.reviews_count} avis · ${b.reviews_count >= 10 ? "Activité visible" : "Peu d'avis"}`,
    });
  }
  const yearMatch = b.creation_date?.match(/(\d{4})/);
  const age = yearMatch ? Math.max(0, new Date().getFullYear() - parseInt(yearMatch[1], 10)) : null;
  if (age !== null) {
    signals.push({
      label: "Ancienneté",
      value: `${age} ans · ${age >= 3 ? "Activité stable" : "Récente"}`,
    });
  }
  signals.push({
    label: "Site web actif",
    value: b.website ? (
      <span style={{ color: "var(--green-600)" }}>Oui · digitalement présent</span>
    ) : (
      <span style={{ color: "var(--red-600)" }}>Pas de site · opportunité</span>
    ),
  });

  return (
    <div className="eval-grid">
      {/* Santé financière */}
      <div className="eval-card">
        <div className="eval-card__header">
          <div
            className="eval-card__icon"
            style={{ background: "var(--green-50)", color: "var(--green-600)" }}
          >
            <TrendingUpIcon />
          </div>
          <div>
            <div className="eval-card__title">Santé financière</div>
            <div className="eval-card__sub">Sources officielles BNB</div>
          </div>
        </div>
        {finRows.map((r, i) => (
          <div className="stat-row" key={i}>
            <span className="stat-row__label">
              {r.icon}
              {r.label}
            </span>
            <span className="stat-row__value">{r.value}</span>
          </div>
        ))}
        {b.nbb_url && (
          <div style={{ marginTop: 16 }}>
            <a
              href={b.nbb_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ext-link"
            >
              <span className="ext-link__icon">
                <FileIcon />
              </span>
              <div className="ext-link__main">
                <div className="ext-link__title">Comptes annuels BNB</div>
                <div className="ext-link__sub">Banque Nationale de Belgique</div>
              </div>
              <span className="ext-link__arrow">
                <ExtArrowIcon />
              </span>
            </a>
          </div>
        )}
      </div>

      {/* Présence locale */}
      <div className="eval-card">
        <div className="eval-card__header">
          <div
            className="eval-card__icon"
            style={{ background: "var(--amber-50)", color: "var(--amber-700)" }}
          >
            <MapPinIcon />
          </div>
          <div>
            <div className="eval-card__title">Présence locale</div>
            <div className="eval-card__sub">Localisation & catégorie</div>
          </div>
        </div>
        {locRows.map((r, i) => (
          <div className="stat-row" key={i}>
            <span className="stat-row__label">
              {r.icon}
              {r.label}
            </span>
            <span className="stat-row__value">{r.value}</span>
          </div>
        ))}
        {b.gmaps_url && (
          <div style={{ marginTop: 16 }}>
            <a
              href={b.gmaps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ext-link"
            >
              <span className="ext-link__icon">
                <MapPinIcon />
              </span>
              <div className="ext-link__main">
                <div className="ext-link__title">Voir sur Google Maps</div>
                <div className="ext-link__sub">Localisation, photos & itinéraire</div>
              </div>
              <span className="ext-link__arrow">
                <ExtArrowIcon />
              </span>
            </a>
          </div>
        )}
      </div>

      {/* Signaux qualifiants */}
      <div className="eval-card eval-card--full">
        <div className="eval-card__header">
          <div
            className="eval-card__icon"
            style={{ background: "var(--indigo-50)", color: "var(--indigo-700)" }}
          >
            <CheckCircleIcon />
          </div>
          <div>
            <div className="eval-card__title">Signaux qualifiants</div>
            <div className="eval-card__sub">
              Pourquoi ce prospect mérite votre attention
            </div>
          </div>
        </div>
        <div className="data-grid">
          {signals.map((s, i) => (
            <div className="data-row" key={i}>
              <span className="data-row__label">{s.label}</span>
              <span className="data-row__value">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function IdentitePanel({ b }: { b: BusinessDetail }) {
  const [openLegal, setOpenLegal] = useState(true);
  const [openNace, setOpenNace] = useState(true);

  const legalRows: { label: string; value: React.ReactNode; mono?: boolean }[] = [];
  if (b.vat_number)
    legalRows.push({ label: "Numéro TVA", value: b.vat_number, mono: true });
  if (b.bce_number)
    legalRows.push({ label: "Numéro BCE", value: b.bce_number, mono: true });
  if (b.legal_form) legalRows.push({ label: "Forme juridique", value: b.legal_form });
  if (b.creation_date)
    legalRows.push({ label: "Date de création", value: b.creation_date });
  if (b.capital) legalRows.push({ label: "Capital", value: b.capital });

  const naceEntries = (b.nace_activities || "")
    .split(/[;\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <>
      <div className={`accordion ${openLegal ? "is-open" : ""}`}>
        <button
          className="acc-header"
          aria-expanded={openLegal}
          onClick={() => setOpenLegal((v) => !v)}
        >
          <span className="acc-icon acc-icon--indigo">
            <BuildingIcon />
          </span>
          <div className="acc-titles">
            <div className="acc-title">Données légales & immatriculation</div>
            <div className="acc-subtitle">TVA, BCE, forme juridique</div>
          </div>
          <span className="acc-chevron">
            <ChevronDownIcon />
          </span>
        </button>
        <div className="acc-body">
          <div className="acc-body-inner">
            <div className="data-grid">
              {legalRows.map((r, i) => (
                <div className="data-row" key={i}>
                  <span className="data-row__label">{r.label}</span>
                  <span
                    className={`data-row__value ${r.mono ? "mono" : ""}`}
                  >
                    {r.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {naceEntries.length > 0 && (
        <div className={`accordion ${openNace ? "is-open" : ""}`}>
          <button
            className="acc-header"
            aria-expanded={openNace}
            onClick={() => setOpenNace((v) => !v)}
          >
            <span className="acc-icon acc-icon--indigo">
              <GridIcon />
            </span>
            <div className="acc-titles">
              <div className="acc-title">Codes d'activité NACE</div>
              <div className="acc-subtitle">
                {naceEntries.length} code(s) enregistré(s)
              </div>
            </div>
            <span className="acc-chevron">
              <ChevronDownIcon />
            </span>
          </button>
          <div className="acc-body">
            <div className="acc-body-inner">
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                }}
              >
                {naceEntries.map((entry, i) => {
                  const m = entry.match(/^\s*([\d.]+)\s*[-–]?\s*(.*)$/);
                  const code = m ? m[1] : "";
                  const label = m ? m[2].trim() : entry;
                  return (
                    <div
                      key={i}
                      className="nace-chip"
                      style={{ padding: "12px 14px", fontSize: 13 }}
                    >
                      {code && <span className="nace-chip__code">{code}</span>}
                      <span>{label}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function HistoriquePanel({ b }: { b: BusinessDetail }) {
  return (
    <div className="eval-card">
      <div className="empty-state">
        <div className="empty-state__icon">
          <PhoneIcon />
        </div>
        <div className="empty-state__title serif">
          Aucun appel pour l'instant
        </div>
        <div className="empty-state__text">
          L'historique d'appels, notes et rappels apparaîtra ici dès le premier
          contact avec {b.name}.
        </div>
      </div>
    </div>
  );
}

// ─── ICONS (SVG inline pour matcher exactement le template Streamlit) ───

function ChevronSmall() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 18l6-6-6-6" />
    </svg>
  );
}
function ChevronDownIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 9l6 6 6-6" />
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
function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
      <polyline points="22,6 12,13 2,6" />
    </svg>
  );
}
function GlobeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" />
    </svg>
  );
}
function MapPinIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  );
}
function ArrowIcon() {
  return (
    <span className="contact-item__action">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M5 12h14M12 5l7 7-7 7" />
      </svg>
    </span>
  );
}
function ExtArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M7 17L17 7M7 7h10v10" />
    </svg>
  );
}
function StarIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </svg>
  );
}
function UsersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
    </svg>
  );
}
function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
function BuildingIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4" />
    </svg>
  );
}
function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function CheckCircleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 11-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
function TrendingUpIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  );
}
function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}
function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
}
function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <path d="M19 12H5M12 19l-7-7 7-7" />
    </svg>
  );
}

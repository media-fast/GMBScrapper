import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Phone,
  Mail,
  Globe,
  MapPin,
  Briefcase,
  Users,
  Calendar,
  ExternalLink,
  Building2,
} from "lucide-react";
import { getBusinessDetail } from "../lib/api";
import { CreditPill } from "../components/CreditPill";
import { parseCreditReasons } from "../lib/utils";

export function BusinessDetailPage() {
  const { dedupKey } = useParams<{ dedupKey: string }>();
  const key = dedupKey ? decodeURIComponent(dedupKey) : "";

  const { data: b, isLoading, error } = useQuery({
    queryKey: ["business", key],
    queryFn: () => getBusinessDetail(key),
    enabled: !!key,
  });

  if (isLoading) {
    return (
      <div className="text-center py-20 text-ink-500">
        Chargement de la fiche…
      </div>
    );
  }
  if (error || !b) {
    return (
      <div className="card p-8 text-center">
        <p className="text-ink-700 mb-4">Fiche introuvable.</p>
        <Link to="/" className="btn-primary">
          <ArrowLeft className="w-4 h-4" />
          Retour aux résultats
        </Link>
      </div>
    );
  }

  const reasons = parseCreditReasons(b.credit_reasons);
  const subLine = [b.legal_form, b.category, b.city]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="space-y-6">
      {/* Bouton retour */}
      <Link to="/" className="btn-secondary w-fit">
        <ArrowLeft className="w-4 h-4" />
        Retour aux résultats
      </Link>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ─── COLONNE PRINCIPALE ─── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Hero */}
          <div className="card p-8">
            <div className="flex items-start justify-between gap-4 mb-3">
              <div>
                <h1 className="text-3xl font-bold text-ink-900 mb-1">
                  {b.name}
                </h1>
                {subLine && (
                  <p className="text-sm text-ink-500">{subLine}</p>
                )}
              </div>
            </div>

            {/* Pills statut + crédit */}
            <div className="flex flex-wrap gap-2 mt-4">
              <span className="pill bg-blue-100 text-blue-800">
                {b.call_status || "À appeler"}
              </span>
              <CreditPill
                color={b.credit_color}
                label={b.credit_label}
                reasons={reasons}
                size="md"
              />
              {b.google_rank && b.google_rank <= 2 && (
                <span className="pill bg-amber-100 text-amber-800">
                  Prospect N°{b.google_rank}
                </span>
              )}
            </div>
          </div>

          {/* Contact */}
          <Section title="Contact">
            <ul className="space-y-3 text-sm">
              {b.phone && (
                <ContactRow icon={Phone} label="Téléphone">
                  <a
                    href={`tel:${b.phone}`}
                    className="text-brand-700 hover:underline"
                  >
                    {b.phone}
                  </a>
                </ContactRow>
              )}
              {b.email && (
                <ContactRow icon={Mail} label="Email">
                  <a
                    href={`mailto:${b.email}`}
                    className="text-brand-700 hover:underline"
                  >
                    {b.email}
                  </a>
                </ContactRow>
              )}
              {b.website && (
                <ContactRow icon={Globe} label="Site web">
                  <a
                    href={b.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-brand-700 hover:underline inline-flex items-center gap-1"
                  >
                    {b.website.replace(/^https?:\/\//, "")}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </ContactRow>
              )}
              {b.address && (
                <ContactRow icon={MapPin} label="Adresse">
                  <span>{b.address}</span>
                  {b.gmaps_url && (
                    <a
                      href={b.gmaps_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand-700 hover:underline ml-2 text-xs"
                    >
                      Voir sur Maps ↗
                    </a>
                  )}
                </ContactRow>
              )}
            </ul>
          </Section>

          {/* Identité légale */}
          <Section title="Identité légale">
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <Field
                icon={Briefcase}
                label="TVA"
                value={b.vat_number}
                copyable
              />
              <Field
                icon={Building2}
                label="BCE"
                value={b.bce_number}
                copyable
              />
              <Field icon={Briefcase} label="Forme" value={b.legal_form} />
              <Field icon={Briefcase} label="Statut" value={b.bce_status} />
              <Field
                icon={Calendar}
                label="Création"
                value={b.creation_date}
              />
              <Field icon={Briefcase} label="Capital" value={b.capital} />
              <Field
                icon={Users}
                label="Dirigeants"
                value={b.managers}
                colSpan
              />
              <Field
                icon={Briefcase}
                label="NACE"
                value={b.nace_activities}
                colSpan
              />
            </dl>
          </Section>
        </div>

        {/* ─── SIDEBAR ─── */}
        <aside className="space-y-4">
          {/* Santé financière */}
          <Section title="Santé financière">
            {b.credit_color ? (
              <>
                <div className="mb-3">
                  <CreditPill
                    color={b.credit_color}
                    label={b.credit_label}
                    size="md"
                  />
                </div>
                {reasons.length > 0 && (
                  <ul className="space-y-2 text-sm text-ink-700">
                    {reasons.map((r, i) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-ink-400">•</span>
                        <span>{r}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {b.credit_computed_at && (
                  <p className="text-[11px] text-ink-400 mt-3 italic">
                    Calculé le {b.credit_computed_at}
                  </p>
                )}
                {b.has_credit_ai_report && (
                  <div className="mt-4 pt-4 border-t border-ink-100 text-xs text-ink-500">
                    📊 Rapport d'analyse IA disponible
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-ink-500 italic">
                Pas encore évalué.
              </p>
            )}
          </Section>

          {/* Dépôts BNB */}
          {b.nbb_year && (
            <Section title="Dépôts BNB">
              <dl className="space-y-2 text-sm">
                <SidebarField label="Dernier exercice" value={b.nbb_year} />
                <SidebarField
                  label="Date de dépôt"
                  value={b.nbb_deposit_date}
                />
                <SidebarField label="Modèle" value={b.nbb_model_type} />
                <SidebarField
                  label="Total dépôts"
                  value={b.nbb_deposits_count?.toString() ?? null}
                />
              </dl>
              {b.nbb_url && (
                <a
                  href={b.nbb_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary w-full mt-4 text-xs"
                >
                  Consulter BNB
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </Section>
          )}

          {/* Avis Google */}
          {b.rating && (
            <Section title="Avis Google">
              <div className="text-center">
                <div className="text-4xl font-bold text-amber-500">
                  {b.rating}
                </div>
                <div className="text-xs text-ink-500 mt-1">
                  / 5 · {b.reviews_count ?? 0} avis
                </div>
              </div>
            </Section>
          )}
        </aside>
      </div>
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card p-6">
      <h2 className="text-xs font-semibold text-ink-500 uppercase tracking-wider mb-4">
        {title}
      </h2>
      {children}
    </section>
  );
}

function ContactRow({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-start gap-3">
      <Icon className="w-4 h-4 text-brand-600 mt-0.5 flex-shrink-0" />
      <div>
        <div className="text-xs text-ink-500">{label}</div>
        <div>{children}</div>
      </div>
    </li>
  );
}

function Field({
  icon: Icon,
  label,
  value,
  copyable = false,
  colSpan = false,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | null;
  copyable?: boolean;
  colSpan?: boolean;
}) {
  if (!value) return null;
  return (
    <div className={colSpan ? "col-span-2" : ""}>
      <dt className="text-xs text-ink-500 flex items-center gap-1">
        <Icon className="w-3 h-3" />
        {label}
      </dt>
      <dd
        className={`mt-0.5 font-medium text-ink-800 ${
          copyable ? "font-mono text-xs" : ""
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

function SidebarField({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-xs text-ink-500">{label}</dt>
      <dd className="text-xs font-medium text-ink-800">{value}</dd>
    </div>
  );
}

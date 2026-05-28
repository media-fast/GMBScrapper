import { Link } from "react-router-dom";
import {
  Phone,
  Mail,
  Briefcase,
  Users,
  Star,
  Trophy,
  Medal,
  ArrowRight,
} from "lucide-react";
import type { BusinessSummary } from "../lib/types";
import { parseCreditReasons } from "../lib/utils";
import { CreditPill } from "./CreditPill";

interface Props {
  business: BusinessSummary;
}

export function BusinessCard({ business: b }: Props) {
  const reasons = parseCreditReasons(b.credit_reasons);
  const subLine = [b.category, b.locality || b.city].filter(Boolean).join(" · ");

  return (
    <article className="card p-5 flex flex-col gap-3 hover:shadow-md transition">
      {/* Header : nom + rank badge */}
      <header className="flex items-start justify-between gap-3">
        <h3 className="font-semibold text-base text-ink-900 leading-tight flex-1">
          {b.name}
        </h3>
        <RankBadge rank={b.google_rank} />
      </header>

      {subLine && (
        <div className="text-xs text-ink-500 -mt-1">{subLine}</div>
      )}

      {/* Pills statut + crédit */}
      <div className="flex flex-wrap gap-1.5">
        <StatusPill status={b.call_status || "À appeler"} />
        <CreditPill
          color={b.credit_color}
          label={b.credit_label}
          reasons={reasons}
        />
      </div>

      {/* Bloc infos compactes */}
      <ul className="space-y-1.5 text-sm text-ink-700 mt-1">
        {b.phone && (
          <InfoRow icon={Phone}>
            <a
              href={`tel:${b.phone}`}
              className="hover:text-brand-700"
              onClick={(e) => e.stopPropagation()}
            >
              {b.phone}
            </a>
          </InfoRow>
        )}
        {b.email && (
          <InfoRow icon={Mail}>
            <a href={`mailto:${b.email}`} className="hover:text-brand-700 truncate block">
              {b.email}
            </a>
          </InfoRow>
        )}
        {b.vat_number && (
          <InfoRow icon={Briefcase}>
            <code className="text-xs">{b.vat_number}</code>
          </InfoRow>
        )}
        {b.managers && (
          <InfoRow icon={Users}>
            <span className="truncate">{b.managers}</span>
          </InfoRow>
        )}
        {b.rating && (
          <InfoRow icon={Star} iconColor="text-amber-500">
            <strong className="font-semibold">{b.rating}</strong>
            <span className="text-ink-400 ml-1">
              ({b.reviews_count ?? 0} avis)
            </span>
          </InfoRow>
        )}
      </ul>

      {/* Action */}
      <div className="pt-2 mt-auto">
        <Link
          to={`/business/${encodeURIComponent(b.dedup_key)}`}
          className="btn-secondary w-full"
        >
          Détails
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </article>
  );
}

function InfoRow({
  icon: Icon,
  iconColor = "text-brand-600",
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  iconColor?: string;
  children: React.ReactNode;
}) {
  return (
    <li className="flex items-start gap-2">
      <Icon className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${iconColor}`} />
      <div className="min-w-0 flex-1">{children}</div>
    </li>
  );
}

function RankBadge({ rank }: { rank: number | null }) {
  if (!rank) return null;
  if (rank === 1) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold text-white bg-gradient-to-br from-amber-400 to-amber-600 shadow-sm">
        <Trophy className="w-3 h-3" />
        N°1
      </span>
    );
  }
  if (rank === 2) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold text-white bg-gradient-to-br from-slate-300 to-slate-500 shadow-sm">
        <Medal className="w-3 h-3" />
        N°2
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-semibold text-ink-600 bg-ink-100">
      N°{rank}
    </span>
  );
}

const STATUS_PALETTE: Record<string, { bg: string; fg: string }> = {
  "À appeler": { bg: "bg-blue-100", fg: "text-blue-800" },
  "Déjà appelé": { bg: "bg-green-100", fg: "text-green-800" },
  "À rappeler": { bg: "bg-red-100", fg: "text-red-800" },
  "Ne plus rappeler": { bg: "bg-slate-100", fg: "text-slate-700" },
};

function StatusPill({ status }: { status: string }) {
  const palette = STATUS_PALETTE[status] || {
    bg: "bg-slate-100",
    fg: "text-slate-700",
  };
  return (
    <span className={`pill ${palette.bg} ${palette.fg}`}>{status}</span>
  );
}

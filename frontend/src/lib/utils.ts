/**
 * Utilitaires partagés frontend.
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { CreditColor } from "./types";

/** Concatène les classes Tailwind en évitant les doublons (shadcn pattern). */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/** Palette Tailwind pour les pills couleur crédit. */
export const CREDIT_PALETTE: Record<
  CreditColor,
  { bg: string; fg: string; ring: string; icon: string; label: string }
> = {
  red: {
    bg: "bg-red-100",
    fg: "text-red-800",
    ring: "ring-red-200",
    icon: "octagon-alert",
    label: "Mauvais payeur",
  },
  orange: {
    bg: "bg-orange-100",
    fg: "text-orange-800",
    ring: "ring-orange-200",
    icon: "triangle-alert",
    label: "À risque",
  },
  yellow: {
    bg: "bg-yellow-100",
    fg: "text-yellow-800",
    ring: "ring-yellow-200",
    icon: "circle-alert",
    label: "À surveiller",
  },
  green: {
    bg: "bg-green-100",
    fg: "text-green-800",
    ring: "ring-green-200",
    icon: "shield-check",
    label: "Bon payeur",
  },
  gray: {
    bg: "bg-slate-100",
    fg: "text-slate-700",
    ring: "ring-slate-200",
    icon: "circle-help",
    label: "Non évalué",
  },
};

/** Parse credit_reasons (JSON string) → array de strings. */
export function parseCreditReasons(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

/** Score de complétude (réplique de _score côté Streamlit). */
export function completenessScore(b: {
  phone: string | null;
  vat_number: string | null;
  website: string | null;
  managers: string | null;
  rating: number | null;
  reviews_count: number | null;
}): number {
  let pts = 0;
  if (b.phone) pts += 25;
  if (b.vat_number) pts += 25;
  if (b.website) pts += 20;
  if (b.managers) pts += 15;
  if (b.rating && b.rating >= 4.0) pts += 10;
  if (b.reviews_count && b.reviews_count >= 10) pts += 5;
  return Math.min(pts, 100);
}

/** Formate une date "2026-05-28 17:01" → "28/05/2026 à 17:01". */
export function formatRanAt(raw: string): string {
  const m = raw.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$/);
  if (!m) return raw;
  const [, y, mo, d, h, mi] = m;
  return `${d}/${mo}/${y} à ${h}:${mi}`;
}

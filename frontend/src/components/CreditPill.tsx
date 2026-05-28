import {
  ShieldCheck,
  TriangleAlert,
  CircleAlert,
  OctagonAlert,
  CircleHelp,
} from "lucide-react";
import type { CreditColor } from "../lib/types";
import { CREDIT_PALETTE, cn } from "../lib/utils";

const ICONS: Record<CreditColor, React.ComponentType<{ className?: string }>> = {
  green: ShieldCheck,
  yellow: CircleAlert,
  orange: TriangleAlert,
  red: OctagonAlert,
  gray: CircleHelp,
};

interface Props {
  color: CreditColor | null;
  label?: string | null;
  /** Tooltip natif (title attribute) ou texte custom */
  reasons?: string[];
  size?: "sm" | "md";
}

export function CreditPill({ color, label, reasons, size = "sm" }: Props) {
  if (!color) return null;
  const palette = CREDIT_PALETTE[color];
  const Icon = ICONS[color];
  const displayLabel = label || palette.label;
  const tooltip = reasons?.join(" · ");

  return (
    <span
      title={tooltip}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-semibold",
        "ring-1 ring-inset",
        palette.bg,
        palette.fg,
        palette.ring,
        size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm",
        tooltip && "cursor-help",
      )}
    >
      <Icon className={size === "sm" ? "w-3 h-3" : "w-3.5 h-3.5"} />
      {displayLabel}
    </span>
  );
}

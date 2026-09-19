import { ReactNode, CSSProperties, ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

export function Card({
  children, className = "", style, interactive = false,
}: { children: ReactNode; className?: string; style?: CSSProperties; interactive?: boolean }) {
  return (
    <div className={`card ${interactive ? "card-interactive" : ""} p-5 ${className}`} style={style}>
      {children}
    </div>
  );
}

export function StatTile({
  label, value, sub, tone = "default", icon,
}: { label: string; value: string | number; sub?: string; tone?: "default" | "good" | "warn" | "bad"; icon?: ReactNode }) {
  const toneColor = { default: "var(--brand)", good: "var(--good)", warn: "var(--warn)", bad: "var(--bad)" }[tone];
  const toneBg = { default: "var(--bg-subtle)", good: "var(--good-bg)", warn: "var(--warn-bg)", bad: "var(--bad-bg)" }[tone];
  return (
    <Card interactive className="relative overflow-hidden">
      <div className="absolute top-0 left-0 right-0 h-[3px]" style={{ background: toneColor, opacity: 0.85 }} />
      <div
        className="absolute -top-8 -right-8 w-24 h-24 rounded-full opacity-[0.06] pointer-events-none"
        style={{ background: toneColor }}
      />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>{label}</div>
          <div className="text-[1.7rem] leading-tight font-bold mt-1.5 tabular-nums" style={{ color: toneColor }}>{value}</div>
          {sub && <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>{sub}</div>}
        </div>
        {icon && (
          <div className="shrink-0 w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: toneBg, color: toneColor }}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}

const PRIORITY_STYLE: Record<string, { bg: string; color: string }> = {
  LOW: { bg: "var(--bg-subtle)", color: "var(--text-muted)" },
  MEDIUM: { bg: "var(--info-bg)", color: "var(--info)" },
  HIGH: { bg: "var(--warn-bg)", color: "var(--warn)" },
  CRITICAL: { bg: "var(--bad-bg)", color: "var(--bad)" },
};
export function PriorityBadge({ priority }: { priority: string }) {
  const s = PRIORITY_STYLE[priority] || PRIORITY_STYLE.LOW;
  return <span className="badge" style={{ background: s.bg, color: s.color }}>{priority}</span>;
}

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  UNASSIGNED: { bg: "var(--bg-subtle)", color: "var(--text-muted)" },
  ASSIGNED: { bg: "var(--good-bg)", color: "var(--good)" },
  IN_PROGRESS: { bg: "var(--info-bg)", color: "var(--info)" },
  COMPLETED: { bg: "var(--bg-subtle)", color: "var(--text-faint)" },
  AT_RISK: { bg: "var(--bad-bg)", color: "var(--bad)" },
  AVAILABLE: { bg: "var(--good-bg)", color: "var(--good)" },
  UNAVAILABLE: { bg: "var(--bad-bg)", color: "var(--bad)" },
  ON_LEAVE: { bg: "var(--warn-bg)", color: "var(--warn)" },
  PARTIALLY_AVAILABLE: { bg: "var(--warn-bg)", color: "var(--warn)" },
};
export function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.UNASSIGNED;
  const isLive = status === "AVAILABLE" || status === "ASSIGNED" || status === "IN_PROGRESS";
  return (
    <span className="badge" style={{ background: s.bg, color: s.color }}>
      {isLive && <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.color }} />}
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function RiskBadge({ risk }: { risk: number }) {
  const style = risk >= 0.6
    ? { background: "var(--bad-bg)", color: "var(--bad)" }
    : risk >= 0.3
      ? { background: "var(--warn-bg)", color: "var(--warn)" }
      : { background: "var(--good-bg)", color: "var(--good)" };
  return <span className="badge tabular-nums" style={style}>{Math.round(risk * 100)}%</span>;
}

interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  loading?: boolean;
}
export function Button({ children, onClick, variant = "primary", disabled, loading, className = "", ...rest }: ButtonProps) {
  const base = "inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-150 ease-smooth active:scale-[0.97] disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100 focus-ring";
  const styles = {
    primary: "text-white shadow-xs hover:shadow-card hover:brightness-110",
    secondary: "hover:brightness-95",
    danger: "text-white shadow-xs hover:shadow-card hover:brightness-110",
    ghost: "hover:bg-[var(--bg-subtle)]",
  }[variant];
  const style: CSSProperties =
    variant === "primary" ? { background: "var(--brand)" } :
    variant === "danger" ? { background: "var(--bad)" } :
    variant === "secondary" ? { background: "var(--bg-subtle)", color: "var(--text)" } :
    { color: "var(--text-muted)" };

  return (
    <button onClick={onClick} disabled={disabled || loading} className={`${base} ${styles} ${className}`} style={style} {...rest}>
      {loading && <Loader2 size={14} className="animate-spin" />}
      {children}
    </button>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function SkeletonRows({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2.5">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex gap-3">
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={c} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function EmptyState({ icon, title, description }: { icon?: ReactNode; title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      {icon && <div className="mb-3 opacity-40">{icon}</div>}
      <div className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>{title}</div>
      {description && <div className="text-xs mt-1 max-w-xs" style={{ color: "var(--text-faint)" }}>{description}</div>}
    </div>
  );
}

export function Divider({ className = "" }: { className?: string }) {
  return <div className={`h-px w-full ${className}`} style={{ background: "var(--border)" }} />;
}

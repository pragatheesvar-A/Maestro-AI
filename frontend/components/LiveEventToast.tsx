"use client";
import { useEffect, useState } from "react";
import { useAllocationStore } from "@/lib/store";
import { Zap, UserX, UserCheck, ListPlus, RefreshCw } from "lucide-react";

const EVENT_META: Record<string, { icon: any; label: string; tone: string }> = {
  EMPLOYEE_UNAVAILABLE: { icon: UserX, label: "Employee unavailable", tone: "var(--bad)" },
  EMPLOYEE_AVAILABLE: { icon: UserCheck, label: "Employee available", tone: "var(--good)" },
  TASK_CREATED: { icon: ListPlus, label: "Task created", tone: "var(--info)" },
  REALLOCATION_COMPLETE: { icon: RefreshCw, label: "Reallocation complete", tone: "var(--accent)" },
};

/**
 * Toasts that appear automatically, unprompted, whenever the backend
 * pushes a state-changing event over the WebSocket -- the visible proof
 * that the platform is reacting live rather than waiting for the viewer
 * to refresh. Purely presentational; the underlying state change was
 * already applied by the real API call.
 */
export default function LiveEventToast() {
  const events = useAllocationStore((s) => s.events);
  const [visible, setVisible] = useState<{ id: string; type: string; summary: string } | null>(null);

  useEffect(() => {
    const latest = events[0];
    if (!latest) return;
    if (latest.type === "CONNECTED") return;
    const meta = EVENT_META[latest.type];
    if (!meta) return;

    let summary = meta.label;
    if (latest.type === "REALLOCATION_COMPLETE") {
      const n = latest.payload?.changes?.length ?? 0;
      summary = `${n} task${n === 1 ? "" : "s"} re-optimized`;
    } else if (latest.payload?.employee_name) {
      summary = `${latest.payload.employee_name}`;
    } else if (latest.payload?.title) {
      summary = latest.payload.title;
    }

    setVisible({ id: latest.id, type: latest.type, summary });
    const timer = setTimeout(() => setVisible(null), 4200);
    return () => clearTimeout(timer);
  }, [events]);

  if (!visible) return null;
  const meta = EVENT_META[visible.type];
  if (!meta) return null;
  const Icon = meta.icon;

  return (
    <div className="fixed bottom-6 right-6 z-[60] animate-fade-rise" key={visible.id}>
      <div
        className="flex items-center gap-3 rounded-2xl px-4 py-3 pr-5"
        style={{ background: "var(--surface-raised)", border: "1px solid var(--border-strong)", boxShadow: "var(--shadow-lg)" }}
      >
        <div className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${meta.tone}22`, color: meta.tone }}>
          <Icon size={15} />
        </div>
        <div>
          <div className="text-xs font-semibold" style={{ color: "var(--text)" }}>{meta.label}</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>{visible.summary}</div>
        </div>
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: meta.tone }} />
      </div>
    </div>
  );
}

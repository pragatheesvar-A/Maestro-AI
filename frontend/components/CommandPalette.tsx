"use client";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  LayoutDashboard, Users, ListChecks, Zap, Scale, ShieldAlert, Bot, Bell, Settings,
  Search, Sparkles, AlertTriangle, CornerDownLeft,
} from "lucide-react";
import { optimizeAllocation } from "@/lib/api";

interface Item {
  id: string;
  label: string;
  hint?: string;
  icon: any;
  group: "Navigate" | "Actions";
  run: () => void | Promise<void>;
}

/**
 * Global command palette (Ctrl/Cmd+K) -- a real, functioning quick-action
 * launcher, not decorative chrome: it navigates via the router and can
 * trigger the actual optimizer API. Standard pattern in premium tools
 * (Linear, Vercel, Raycast); included so the demo has a genuinely advanced
 * interaction surface beyond point-and-click navigation.
 */
export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState(false);
  const router = useRouter();
  const qc = useQueryClient();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (open) setQuery("");
  }, [open]);

  const items: Item[] = useMemo(() => [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, group: "Navigate", run: () => router.push("/dashboard") },
    { id: "employees", label: "Employees", icon: Users, group: "Navigate", run: () => router.push("/employees") },
    { id: "tasks", label: "Tasks", icon: ListChecks, group: "Navigate", run: () => router.push("/tasks") },
    { id: "allocation", label: "Live Allocation", icon: Zap, group: "Navigate", run: () => router.push("/allocation") },
    { id: "workload", label: "Workload & Fairness", icon: Scale, group: "Navigate", run: () => router.push("/workload") },
    { id: "sla", label: "SLA Analytics", icon: ShieldAlert, group: "Navigate", run: () => router.push("/sla") },
    { id: "ai-center", label: "AI Decision Center", icon: Bot, group: "Navigate", run: () => router.push("/ai-center") },
    { id: "alerts", label: "Alerts", icon: Bell, group: "Navigate", run: () => router.push("/alerts") },
    { id: "admin", label: "Admin Settings", icon: Settings, group: "Navigate", run: () => router.push("/admin") },
    {
      id: "optimize", label: "Optimize Allocation", hint: "Runs the real CP-SAT solver now", icon: Sparkles, group: "Actions",
      run: async () => {
        setRunning(true);
        try {
          await optimizeAllocation({});
          await qc.invalidateQueries({ queryKey: ["tasks"] });
          await qc.invalidateQueries({ queryKey: ["dashboard"] });
        } finally {
          setRunning(false);
        }
      },
    },
    {
      id: "simulate", label: "Go simulate a disruption", hint: "Opens Live Allocation", icon: AlertTriangle, group: "Actions",
      run: () => router.push("/allocation"),
    },
  ], [router, qc]);

  const filtered = items.filter((i) => i.label.toLowerCase().includes(query.toLowerCase()));
  const grouped = { Navigate: filtered.filter((i) => i.group === "Navigate"), Actions: filtered.filter((i) => i.group === "Actions") };

  if (!open) return null;

  async function select(item: Item) {
    setOpen(false);
    await item.run();
  }

  return (
    <div
      className="fixed inset-0 z-[70] flex items-start justify-center pt-[14vh] px-4 animate-fade-rise"
      style={{ background: "rgba(10, 8, 18, 0.55)", backdropFilter: "blur(3px)", animationDuration: "0.15s" }}
      onClick={() => setOpen(false)}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-2xl animate-scale-in overflow-hidden"
        style={{ background: "var(--surface-raised)", border: "1px solid var(--border-strong)", boxShadow: "var(--shadow-lg)" }}
      >
        <div className="flex items-center gap-2.5 px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
          <Search size={15} style={{ color: "var(--text-faint)" }} />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages or run an action…"
            className="flex-1 bg-transparent text-sm outline-none"
          />
          <kbd className="text-[10px] font-semibold px-1.5 py-0.5 rounded" style={{ background: "var(--bg-subtle)", color: "var(--text-faint)" }}>ESC</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto py-2">
          {(["Actions", "Navigate"] as const).map((group) =>
            grouped[group].length > 0 && (
              <div key={group} className="px-2 mb-1">
                <div className="text-[10px] font-semibold uppercase tracking-wide px-2.5 py-1" style={{ color: "var(--text-faint)" }}>{group}</div>
                {grouped[group].map((item) => {
                  const Icon = item.icon;
                  return (
                    <button
                      key={item.id}
                      onClick={() => select(item)}
                      disabled={running}
                      className="w-full flex items-center gap-3 px-2.5 py-2 rounded-xl text-sm transition-colors duration-100 hover:bg-[var(--bg-subtle)] disabled:opacity-50"
                    >
                      <Icon size={15} style={{ color: "var(--brand)" }} />
                      <span className="flex-1 text-left font-medium">{item.label}</span>
                      {item.hint && <span className="text-[11px]" style={{ color: "var(--text-faint)" }}>{item.hint}</span>}
                      <CornerDownLeft size={12} style={{ color: "var(--text-faint)" }} />
                    </button>
                  );
                })}
              </div>
            )
          )}
          {filtered.length === 0 && (
            <div className="text-center text-sm py-8" style={{ color: "var(--text-faint)" }}>No matches</div>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";
import { Suspense, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { Card, PriorityBadge, StatusBadge, RiskBadge, SkeletonRows, EmptyState, Button } from "@/components/ui";
import { getTasks, TaskOut } from "@/lib/api";
import TaskQrModal from "@/components/TaskQrModal";
import { format } from "date-fns";
import { ListChecks, QrCode } from "lucide-react";

const PRIORITIES = [
  { value: "", label: "All priorities" },
  { value: "CRITICAL", label: "Critical" },
  { value: "HIGH", label: "High" },
  { value: "MEDIUM", label: "Medium" },
  { value: "LOW", label: "Low" },
];

function TasksPageInner() {
  const { data: tasks, isLoading } = useQuery({ queryKey: ["tasks"], queryFn: getTasks, refetchInterval: 8000 });
  const [selected, setSelected] = useState<TaskOut | null>(null);
  const [priorityFilter, setPriorityFilter] = useState("");
  const [showQr, setShowQr] = useState(false);
  const searchParams = useSearchParams();

  // Deep-link support for the QR-code task lookup: scanning a task's QR
  // code opens /tasks?taskId=<id>, which auto-selects that task the moment
  // the list loads -- the whole point of a QR-based "scan a physical work
  // order to see your live assignment" flow.
  useEffect(() => {
    const deepLinkId = searchParams.get("taskId");
    if (deepLinkId && tasks) {
      const found = tasks.find((t) => t.id === deepLinkId);
      if (found) setSelected(found);
    }
  }, [searchParams, tasks]);

  const filtered = (tasks || []).filter((t) => !priorityFilter || t.priority === priorityFilter);

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Tasks</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{tasks?.length ?? 0} tasks across all projects.</p>
        </div>
        <div className="flex gap-1.5 p-1 rounded-xl" style={{ background: "var(--bg-subtle)" }}>
          {PRIORITIES.map((p) => (
            <button
              key={p.value}
              onClick={() => setPriorityFilter(p.value)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150"
              style={priorityFilter === p.value
                ? { background: "var(--surface)", color: "var(--text)", boxShadow: "var(--shadow-sm)" }
                : { color: "var(--text-faint)" }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2 overflow-x-auto max-h-[72vh] overflow-y-auto p-0">
          {isLoading ? (
            <div className="p-5"><SkeletonRows rows={8} cols={6} /></div>
          ) : filtered.length === 0 ? (
            <EmptyState icon={<ListChecks size={32} />} title="No tasks match this filter" />
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10" style={{ background: "var(--surface)" }}>
                <tr className="text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)", borderBottom: "1px solid var(--border)" }}>
                  <th className="py-3 px-5">ID</th>
                  <th className="py-3 px-3">Title</th>
                  <th className="py-3 px-3">Priority</th>
                  <th className="py-3 px-3">Assignee</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-5">SLA Risk</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => {
                  const active = selected?.id === t.id;
                  return (
                    <tr
                      key={t.id} onClick={() => setSelected(t)}
                      className="table-row-hover cursor-pointer"
                      style={{ borderBottom: "1px solid var(--border)", background: active ? "var(--info-bg)" : "transparent" }}
                    >
                      <td className="py-3 px-5 font-mono text-xs" style={{ color: "var(--text-faint)" }}>{t.id}</td>
                      <td className="py-3 px-3 font-medium">{t.title}</td>
                      <td className="py-3 px-3"><PriorityBadge priority={t.priority} /></td>
                      <td className="py-3 px-3" style={{ color: "var(--text-muted)" }}>{t.assigned_employee_name || "—"}</td>
                      <td className="py-3 px-3"><StatusBadge status={t.status} /></td>
                      <td className="py-3 px-5">{t.sla_risk != null ? <RiskBadge risk={t.sla_risk} /> : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="lg:sticky lg:top-16 self-start">
          <div className="flex items-center justify-between mb-4">
            <div className="font-semibold text-sm">Task Details</div>
            {selected && (
              <button
                onClick={() => setShowQr(true)}
                className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-colors duration-150"
                style={{ background: "var(--brand-soft)", color: "var(--brand)" }}
              >
                <QrCode size={13} /> QR
              </button>
            )}
          </div>
          {!selected ? (
            <EmptyState icon={<ListChecks size={28} />} title="No task selected" description="Click a row to view details, or scan a task QR code." />
          ) : (
            <div className="space-y-4 text-sm animate-fade-rise">
              <div>
                <div className="font-mono text-xs" style={{ color: "var(--text-faint)" }}>{selected.id}</div>
                <div className="text-base font-bold mt-0.5">{selected.title}</div>
                <div className="mt-1 leading-relaxed" style={{ color: "var(--text-muted)" }}>{selected.description}</div>
              </div>
              <div className="flex gap-2"><PriorityBadge priority={selected.priority} /><StatusBadge status={selected.status} /></div>
              <div className="grid grid-cols-2 gap-3 pt-1">
                <InfoField label="Project" value={selected.project} />
                <InfoField label="Location" value={selected.location} />
                <InfoField label="Est. Hours" value={`${selected.estimated_hours}h`} />
                <InfoField label="Complexity" value={`${Math.round(selected.complexity * 100)}%`} />
                <InfoField label="Deadline" value={selected.deadline ? format(new Date(selected.deadline), "MMM d, HH:mm") : "—"} />
                <InfoField label="SLA Risk" value={selected.sla_risk != null ? `${Math.round(selected.sla_risk * 100)}%` : "—"} />
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-faint)" }}>Required Skills</div>
                <div className="flex flex-wrap gap-1.5">
                  {selected.required_skills.map((s) => (
                    <span key={s} className="badge" style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}>{s}</span>
                  ))}
                </div>
              </div>
              <div className="rounded-xl p-3" style={{ background: "var(--bg-subtle)" }}>
                <div className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>Current Assignee</div>
                <div className="font-medium mt-0.5">{selected.assigned_employee_name || "Unassigned"}</div>
                {selected.skill_match_score != null && (
                  <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>Skill match: {Math.round(selected.skill_match_score * 100)}%</div>
                )}
              </div>
            </div>
          )}
        </Card>
      </div>

      {showQr && selected && (
        <TaskQrModal taskId={selected.id} taskTitle={selected.title} onClose={() => setShowQr(false)} />
      )}
    </AppShell>
  );
}

export default function TasksPage() {
  return (
    <Suspense fallback={null}>
      <TasksPageInner />
    </Suspense>
  );
}

function InfoField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10.5px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>{label}</div>
      <div className="font-medium mt-0.5">{value}</div>
    </div>
  );
}

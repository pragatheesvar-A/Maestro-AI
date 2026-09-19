"use client";
import { useQuery } from "@tanstack/react-query";
import AppShell from "@/components/AppShell";
import { Card, RiskBadge, PriorityBadge, SkeletonRows, EmptyState, StatTile } from "@/components/ui";
import { getSlaAnalytics } from "@/lib/api";
import { format } from "date-fns";
import { ShieldAlert, ShieldCheck, Clock } from "lucide-react";

export default function SlaPage() {
  const { data } = useQuery({ queryKey: ["sla-full"], queryFn: getSlaAnalytics, refetchInterval: 8000 });

  const highRisk = (data || []).filter((d) => d.sla_risk >= 0.6).length;
  const avgRisk = data && data.length ? data.reduce((s, d) => s + d.sla_risk, 0) / data.length : null;

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">SLA Analytics</h1>
        <p className="text-sm mt-1 max-w-2xl leading-relaxed" style={{ color: "var(--text-muted)" }}>
          Model-predicted SLA breach risk per task. Predictions come from a gradient-boosted classifier
          trained on a labeled synthetic dataset.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <StatTile label="Active Tasks" value={data?.length ?? "—"} icon={<Clock size={17} />} />
        <StatTile label="High Risk Tasks" value={highRisk} tone={highRisk > 0 ? "bad" : "good"} icon={<ShieldAlert size={17} />} />
        <StatTile label="Avg SLA Risk" value={avgRisk != null ? `${Math.round(avgRisk * 100)}%` : "—"} tone={avgRisk != null && avgRisk > 0.4 ? "warn" : "good"} icon={<ShieldCheck size={17} />} />
      </div>

      <Card className="overflow-x-auto p-0">
        {!data ? (
          <div className="p-5"><SkeletonRows rows={8} cols={5} /></div>
        ) : data.length === 0 ? (
          <EmptyState icon={<ShieldCheck size={32} />} title="No active tasks" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)", borderBottom: "1px solid var(--border)" }}>
                <th className="py-3 px-5">Task</th>
                <th className="py-3 px-3">Priority</th>
                <th className="py-3 px-3">Predicted Completion</th>
                <th className="py-3 px-3">Deadline</th>
                <th className="py-3 px-5">SLA Risk</th>
              </tr>
            </thead>
            <tbody>
              {data.map((t) => (
                <tr key={t.task_id} className="table-row-hover" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="py-3 px-5">
                    <div className="font-medium">{t.task_title}</div>
                    <div className="font-mono text-xs" style={{ color: "var(--text-faint)" }}>{t.task_id}</div>
                  </td>
                  <td className="py-3 px-3"><PriorityBadge priority={t.priority} /></td>
                  <td className="py-3 px-3 tabular-nums" style={{ color: "var(--text-muted)" }}>{t.predicted_completion_hours}h</td>
                  <td className="py-3 px-3" style={{ color: "var(--text-muted)" }}>{t.deadline ? format(new Date(t.deadline), "MMM d, HH:mm") : "—"}</td>
                  <td className="py-3 px-5"><RiskBadge risk={t.sla_risk} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </AppShell>
  );
}

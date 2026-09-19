"use client";
import { useQuery } from "@tanstack/react-query";
import AppShell from "@/components/AppShell";
import { Card, StatTile, Skeleton } from "@/components/ui";
import { getFairnessAnalytics } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";
import { Scale, PieChart as PieIcon, Activity } from "lucide-react";

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl px-3 py-2 text-xs shadow-pop" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="font-semibold mb-0.5">{label}</div>
      <div style={{ color: "var(--brand)" }}>Utilization: {payload[0].value}%</div>
    </div>
  );
}

export default function WorkloadPage() {
  const { data } = useQuery({ queryKey: ["fairness"], queryFn: getFairnessAnalytics, refetchInterval: 8000 });

  const chartData = (data?.per_employee || [])
    .slice()
    .sort((a, b) => b.utilization - a.utilization)
    .map((e) => ({ name: e.employee_name, utilization: Math.round(e.utilization * 100) }));

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Workload &amp; Fairness</h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>How evenly work is distributed across the team.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <StatTile label="Jain Fairness Index" value={data ? data.jain_fairness_index.toFixed(3) : "—"} sub="1.0 = perfectly fair allocation" tone={data && data.jain_fairness_index > 0.85 ? "good" : "warn"} icon={<Scale size={17} />} />
        <StatTile label="Gini Coefficient" value={data ? data.gini_coefficient.toFixed(3) : "—"} sub="0 = equal, 1 = maximally unequal" tone={data && data.gini_coefficient < 0.3 ? "good" : "warn"} icon={<PieIcon size={17} />} />
        <StatTile label="Workload Variance" value={data ? data.workload_variance.toFixed(1) : "—"} sub="Lower = more consistent workloads" icon={<Activity size={17} />} />
      </div>

      <Card>
        <div className="font-semibold text-sm mb-4">Utilization by Employee</div>
        {!data ? <Skeleton className="h-[420px] w-full" /> : (
          <ResponsiveContainer width="100%" height={Math.max(420, chartData.length * 26)}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 40 }} barSize={16}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" unit="%" tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
              <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11, fill: "var(--text-muted)" }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "var(--bg-subtle)" }} />
              <Bar dataKey="utilization" radius={[0, 6, 6, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={entry.utilization > 90 ? "var(--bad)" : entry.utilization > 70 ? "var(--warn)" : "var(--brand)"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </Card>
    </AppShell>
  );
}

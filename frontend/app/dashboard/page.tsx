"use client";
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import AppShell from "@/components/AppShell";
import EmployeeDashboard from "@/components/EmployeeDashboard";
import { Card, StatTile, Skeleton, EmptyState } from "@/components/ui";
import { getDashboardStats, getWorkloadAnalytics, getSlaAnalytics, getTasks } from "@/lib/api";
import { useAllocationStore, useAuthStore } from "@/lib/store";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend, AreaChart, Area,
} from "recharts";
import { Users, UserCheck, ListTodo, AlertTriangle, ShieldAlert, Gauge, Scale, ListX, TrendingUp } from "lucide-react";

const PRIORITY_COLORS: Record<string, string> = { LOW: "#9CA3AF", MEDIUM: "#4a63f6", HIGH: "#d68806", CRITICAL: "#e0384c" };
const STATUS_COLORS: Record<string, string> = { UNASSIGNED: "#9CA3AF", ASSIGNED: "#10a15e", IN_PROGRESS: "#4a63f6", COMPLETED: "#6b7086", AT_RISK: "#e0384c" };

function ChartTooltip({ active, payload, label, unit = "" }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl px-3 py-2 text-xs shadow-pop" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
      <div className="font-semibold mb-0.5">{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{ color: p.color || p.fill }}>{p.name}: {p.value}{unit}</div>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const role = useAuthStore((s) => s.role);
  return <AppShell>{role === "EMPLOYEE" ? <EmployeeDashboard /> : <ManagerDashboard />}</AppShell>;
}

function ManagerDashboard() {
  const { data: stats } = useQuery({ queryKey: ["dashboard"], queryFn: getDashboardStats, refetchInterval: 10000 });
  const { data: workload } = useQuery({ queryKey: ["workload"], queryFn: getWorkloadAnalytics, refetchInterval: 10000 });
  const { data: sla } = useQuery({ queryKey: ["sla"], queryFn: getSlaAnalytics, refetchInterval: 10000 });
  const { data: tasks } = useQuery({ queryKey: ["tasks-dashboard"], queryFn: getTasks, refetchInterval: 10000 });

  const fairnessHistory = useAllocationStore((s) => s.fairnessHistory);
  const pushFairness = useAllocationStore((s) => s.pushFairness);
  const lastLiveUpdateAt = useAllocationStore((s) => s.lastLiveUpdateAt);
  useEffect(() => {
    if (stats) pushFairness(stats.fairness_index);
  }, [stats, pushFairness]);
  const fairnessChart = fairnessHistory.map((p, i) => ({ i, value: Math.round(p.value * 1000) / 10 }));

  const priorityData = tasks
    ? Object.entries(
        tasks.reduce((acc: Record<string, number>, t) => ({ ...acc, [t.priority]: (acc[t.priority] || 0) + 1 }), {})
      ).map(([name, value]) => ({ name, value }))
    : [];

  const statusData = tasks
    ? Object.entries(
        tasks.reduce((acc: Record<string, number>, t) => ({ ...acc, [t.status]: (acc[t.status] || 0) + 1 }), {})
      ).map(([name, value]) => ({ name, value }))
    : [];

  const workloadChart = (workload || [])
    .slice()
    .sort((a, b) => b.utilization - a.utilization)
    .slice(0, 12)
    .map((w) => ({ name: w.employee_name, utilization: Math.round(w.utilization * 100) }));
  const slaChart = (sla || []).slice(0, 10).map((s) => ({ name: s.task_id, risk: Math.round(s.sla_risk * 100) }));

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>Real-time overview of workforce allocation.</p>
      </div>

      <div key={lastLiveUpdateAt ?? "initial"} className="animate-flash-update rounded-2xl -m-2 p-2">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-4">
          <StatTile label="Total Employees" value={stats?.total_employees ?? "—"} icon={<Users size={17} />} />
          <StatTile label="Available" value={stats?.available_employees ?? "—"} tone="good" icon={<UserCheck size={17} />} />
          <StatTile label="Active Tasks" value={stats?.active_tasks ?? "—"} icon={<ListTodo size={17} />} />
          <StatTile label="Unassigned" value={stats?.unassigned_tasks ?? "—"} tone={stats && stats.unassigned_tasks > 0 ? "warn" : "good"} icon={<ListX size={17} />} />
          <StatTile label="Active Disruptions" value={stats?.active_disruptions ?? "—"} tone={stats && stats.active_disruptions > 0 ? "bad" : "good"} icon={<AlertTriangle size={17} />} />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <StatTile label="Avg SLA Risk" value={stats ? `${Math.round(stats.avg_sla_risk * 100)}%` : "—"} tone={stats && stats.avg_sla_risk > 0.5 ? "bad" : "good"} icon={<ShieldAlert size={17} />} />
          <StatTile label="Avg Workload Utilization" value={stats ? `${Math.round(stats.avg_workload_utilization * 100)}%` : "—"} icon={<Gauge size={17} />} />
          <StatTile label="Fairness Index (Jain)" value={stats ? stats.fairness_index.toFixed(2) : "—"} sub="1.0 = perfectly fair" tone={stats && stats.fairness_index > 0.85 ? "good" : "warn"} icon={<Scale size={17} />} />
        </div>
      </div>

      <Card className="mb-6 relative overflow-hidden">
        <div className="flex items-center justify-between mb-1">
          <div className="font-semibold text-sm flex items-center gap-2">
            <TrendingUp size={14} style={{ color: "var(--brand)" }} /> Fairness Trend
          </div>
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full" style={{ background: "var(--good-bg)", color: "var(--good)" }}>
            live this session
          </span>
        </div>
        <p className="text-xs mb-3" style={{ color: "var(--text-faint)" }}>
          Real Jain fairness index sampled every dashboard refresh — watch it stay high even through a disruption.
        </p>
        {fairnessChart.length < 2 ? (
          <EmptyState title="Collecting live samples…" description="Keep this page open — the trend fills in as the dashboard polls the optimizer." />
        ) : (
          <ResponsiveContainer width="100%" height={90}>
            <AreaChart data={fairnessChart} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="fairnessFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--brand)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--brand)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis domain={[0, 100]} hide />
              <Tooltip content={<ChartTooltip unit="%" />} />
              <Area type="monotone" dataKey="value" name="Fairness" stroke="var(--brand)" strokeWidth={2} fill="url(#fairnessFill)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Card>
          <div className="font-semibold text-sm mb-4">Workload Distribution <span className="font-normal" style={{ color: "var(--text-faint)" }}>· top 12</span></div>
          {!workload ? <Skeleton className="h-[260px] w-full" /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={workloadChart} barSize={22}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--text-faint)" }} angle={-30} textAnchor="end" height={60} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "var(--text-faint)" }} unit="%" axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip unit="%" />} cursor={{ fill: "var(--bg-subtle)" }} />
                <Bar dataKey="utilization" fill="var(--brand)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card>
          <div className="font-semibold text-sm mb-4">SLA Risk <span className="font-normal" style={{ color: "var(--text-faint)" }}>· highest risk tasks</span></div>
          {!sla ? <Skeleton className="h-[260px] w-full" /> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={slaChart} barSize={22}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--text-faint)" }} angle={-30} textAnchor="end" height={60} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "var(--text-faint)" }} unit="%" axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip unit="%" />} cursor={{ fill: "var(--bg-subtle)" }} />
                <Bar dataKey="risk" fill="var(--bad)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <div className="font-semibold text-sm mb-2">Tasks by Priority</div>
          {!tasks ? <Skeleton className="h-[220px] w-full" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={priorityData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={48} outerRadius={78} paddingAngle={2} cornerRadius={4}>
                  {priorityData.map((entry, i) => <Cell key={i} fill={PRIORITY_COLORS[entry.name] || "#999"} stroke="none" />)}
                </Pie>
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
        <Card>
          <div className="font-semibold text-sm mb-2">Allocation Status</div>
          {!tasks ? <Skeleton className="h-[220px] w-full" /> : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={48} outerRadius={78} paddingAngle={2} cornerRadius={4}>
                  {statusData.map((entry, i) => <Cell key={i} fill={STATUS_COLORS[entry.name] || "#999"} stroke="none" />)}
                </Pie>
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </>
  );
}

"use client";
import { useQuery } from "@tanstack/react-query";
import { Card, StatTile, StatusBadge, PriorityBadge, RiskBadge, EmptyState, Skeleton } from "@/components/ui";
import { getEmployee, getTasks } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import {
  Briefcase, Clock, TrendingUp, TrendingDown, Minus, ShieldAlert, ListChecks, Award,
} from "lucide-react";

const TREND_META: Record<string, { icon: any; color: string; label: string }> = {
  improving: { icon: TrendingUp, color: "var(--good)", label: "Improving" },
  declining: { icon: TrendingDown, color: "var(--bad)", label: "Declining" },
  stable: { icon: Minus, color: "var(--text-muted)", label: "Stable" },
  insufficient_data: { icon: Minus, color: "var(--text-faint)", label: "Not enough data yet" },
};

/**
 * The role-differentiated view for the EMPLOYEE role: instead of the
 * company-wide manager dashboard, a signed-in employee sees only their own
 * profile, their own assigned tasks, and the same recency-weighted
 * performance / risk signals a manager would see about them -- backed by
 * the employee_id the login response links to their User record (see
 * app/seed.py's "Employee Demo" -> Deepa link, and /auth/login returning
 * employee_id).
 */
export default function EmployeeDashboard() {
  const employeeId = useAuthStore((s) => s.employeeId);
  const fullName = useAuthStore((s) => s.fullName);

  const { data: profile } = useQuery({
    queryKey: ["me-employee", employeeId],
    queryFn: () => getEmployee(employeeId as string),
    enabled: !!employeeId,
    refetchInterval: 10000,
  });
  const { data: allTasks } = useQuery({ queryKey: ["tasks"], queryFn: getTasks, refetchInterval: 8000 });

  const myTasks = (allTasks || []).filter((t) => t.assigned_employee_id === employeeId);

  if (!employeeId) {
    return (
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">My Work</h1>
        <Card className="mt-4">
          <EmptyState
            icon={<Briefcase size={28} />}
            title="No employee profile linked to this login"
            description="This account has an EMPLOYEE role but isn't linked to an Employee record. Ask an admin to link it."
          />
        </Card>
      </div>
    );
  }

  const utilization = profile ? profile.current_workload_hours / profile.max_capacity_hours : 0;
  const trend = TREND_META[profile?.performance_trend || "insufficient_data"];
  const TrendIcon = trend.icon;

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-white font-bold text-lg shrink-0" style={{ background: "var(--brand)" }}>
          {(profile?.name || fullName || "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Welcome back, {profile?.name?.split(" ")[0] || fullName}</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{profile?.role} · {profile?.location || "—"}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatTile
          label="My Active Tasks" value={myTasks.length}
          icon={<ListChecks size={17} />}
        />
        <StatTile
          label="Workload" value={profile ? `${Math.round(utilization * 100)}%` : "—"}
          sub={profile ? `${profile.current_workload_hours}/${profile.max_capacity_hours}h` : undefined}
          tone={utilization > 0.85 ? "bad" : utilization > 0.7 ? "warn" : "good"}
          icon={<Clock size={17} />}
        />
        <StatTile
          label="Performance (recency-weighted)"
          value={profile?.dynamic_performance_score != null ? `${Math.round(profile.dynamic_performance_score * 100)}%` : "—"}
          sub={profile?.performance_sample_size ? `${profile.performance_sample_size} recent tasks` : undefined}
          tone="default"
          icon={<Award size={17} />}
        />
        <StatTile
          label="Availability" value={profile?.availability_status?.replace(/_/g, " ") || "—"}
          tone={profile?.availability_status === "AVAILABLE" ? "good" : "warn"}
          icon={<ShieldAlert size={17} />}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2">
          <div className="font-semibold text-sm mb-4">My Assigned Tasks</div>
          {!allTasks ? (
            <Skeleton className="h-40 w-full" />
          ) : myTasks.length === 0 ? (
            <EmptyState icon={<Briefcase size={28} />} title="No tasks currently assigned" description="Check back after the next allocation run." />
          ) : (
            <div className="space-y-2.5">
              {myTasks.map((t) => (
                <div key={t.id} className="rounded-xl p-3.5" style={{ background: "var(--bg-subtle)" }}>
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="font-medium text-sm">{t.title}</div>
                    <div className="flex items-center gap-1.5">
                      <PriorityBadge priority={t.priority} />
                      <StatusBadge status={t.status} />
                    </div>
                  </div>
                  <div className="flex items-center gap-3 mt-2 text-xs" style={{ color: "var(--text-muted)" }}>
                    <span className="font-mono">{t.id}</span>
                    <span>{t.estimated_hours}h estimated</span>
                    {t.sla_risk != null && <RiskBadge risk={t.sla_risk} />}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <div className="font-semibold text-sm mb-4">My Performance Trend</div>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: `${trend.color}22`, color: trend.color }}>
              <TrendIcon size={16} />
            </div>
            <div>
              <div className="text-sm font-semibold">{trend.label}</div>
              <div className="text-xs" style={{ color: "var(--text-faint)" }}>vs. earlier completed tasks</div>
            </div>
          </div>
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Computed from your own completed-task history with a 30-day recency half-life — recent work
            counts more than older work, so this score reflects how you're doing lately, not a fixed rating.
          </p>
          {profile?.skills && profile.skills.length > 0 && (
            <div className="mt-4">
              <div className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-faint)" }}>My Skills</div>
              <div className="flex flex-wrap gap-1.5">
                {profile.skills.map((s) => (
                  <span key={s.skill_name} className="badge" style={{ background: "var(--brand-soft)", color: "var(--brand)" }}>
                    {s.skill_name} · {Math.round(s.proficiency * 100)}%
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

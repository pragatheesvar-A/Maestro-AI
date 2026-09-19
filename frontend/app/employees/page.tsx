"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppShell from "@/components/AppShell";
import { Card, StatusBadge, SkeletonRows, EmptyState } from "@/components/ui";
import { getEmployees, Employee } from "@/lib/api";
import { Search, Users } from "lucide-react";

export default function EmployeesPage() {
  const { data: employees, isLoading } = useQuery({ queryKey: ["employees"], queryFn: getEmployees, refetchInterval: 8000 });
  const [selected, setSelected] = useState<Employee | null>(null);
  const [search, setSearch] = useState("");

  const filtered = (employees || []).filter((e) =>
    e.name.toLowerCase().includes(search.toLowerCase()) || e.role.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Employees</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>{employees?.length ?? 0} employees in the workforce pool.</p>
        </div>
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-faint)" }} />
          <input
            placeholder="Search by name or role…" value={search} onChange={(e) => setSearch(e.target.value)}
            className="border rounded-xl pl-9 pr-3.5 py-2.5 text-sm w-72 outline-none transition-all focus-ring"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-2 overflow-x-auto p-0">
          {isLoading ? (
            <div className="p-5"><SkeletonRows rows={8} cols={5} /></div>
          ) : filtered.length === 0 ? (
            <EmptyState icon={<Users size={32} />} title="No employees found" description="Try a different search term." />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)", borderBottom: "1px solid var(--border)" }}>
                  <th className="py-3 px-5">Name</th>
                  <th className="py-3 px-3">Role</th>
                  <th className="py-3 px-3">Location</th>
                  <th className="py-3 px-3">Workload</th>
                  <th className="py-3 px-5">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((e) => {
                  const util = e.current_workload_hours / e.max_capacity_hours;
                  const active = selected?.id === e.id;
                  return (
                    <tr
                      key={e.id} onClick={() => setSelected(e)}
                      className="table-row-hover cursor-pointer"
                      style={{ borderBottom: "1px solid var(--border)", background: active ? "var(--info-bg)" : "transparent" }}
                    >
                      <td className="py-3 px-5 font-medium">{e.name}</td>
                      <td className="py-3 px-3" style={{ color: "var(--text-muted)" }}>{e.role}</td>
                      <td className="py-3 px-3" style={{ color: "var(--text-muted)" }}>{e.location}</td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--bg-subtle)" }}>
                            <div
                              className="h-full rounded-full transition-all duration-500 ease-smooth"
                              style={{ width: `${Math.min(100, util * 100)}%`, background: util > 0.85 ? "var(--bad)" : "var(--brand)" }}
                            />
                          </div>
                          <span className="text-xs tabular-nums" style={{ color: "var(--text-faint)" }}>{e.current_workload_hours}/{e.max_capacity_hours}h</span>
                        </div>
                      </td>
                      <td className="py-3 px-5"><StatusBadge status={e.availability_status} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>

        <Card className="lg:sticky lg:top-16 self-start">
          <div className="font-semibold text-sm mb-4">Employee Profile</div>
          {!selected ? (
            <EmptyState icon={<Users size={28} />} title="No employee selected" description="Click a row to view their profile." />
          ) : (
            <div className="space-y-4 animate-fade-rise">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold text-white shrink-0" style={{ background: "var(--brand)" }}>
                  {selected.name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
                </div>
                <div>
                  <div className="text-base font-bold">{selected.name}</div>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>{selected.role} · {selected.location}</div>
                </div>
              </div>
              <StatusBadge status={selected.availability_status} />
              <div className="grid grid-cols-2 gap-3 text-sm pt-1">
                <InfoField label="Experience" value={`${selected.experience_years} yrs`} />
                <InfoField label="Performance" value={`${Math.round(selected.historical_performance_score * 100)}%`} />
                <InfoField label="Workload" value={`${selected.current_workload_hours}/${selected.max_capacity_hours}h`} />
                <InfoField label="Certifications" value={selected.certifications.join(", ") || "None"} />
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-faint)" }}>Skills</div>
                <div className="flex flex-wrap gap-1.5">
                  {selected.skills.map((s) => (
                    <span key={s.skill_name} className="badge" style={{ background: "var(--info-bg)", color: "var(--info)" }}>
                      {s.skill_name} · {Math.round(s.proficiency * 100)}%
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
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

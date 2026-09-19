"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import AppShell from "@/components/AppShell";
import { Card, Button, PriorityBadge, StatusBadge, RiskBadge, SkeletonRows, EmptyState } from "@/components/ui";
import { getTasks, getEmployees, optimizeAllocation, triggerEmployeeUnavailable, getDecisionTrace, resetDemo, DecisionTrace, TaskOut } from "@/lib/api";
import { useAllocationStore } from "@/lib/store";
import { AlertTriangle, Sparkles, X, CheckCircle2, ArrowRight, Loader2, MessageSquareText, Inbox, RotateCcw, QrCode } from "lucide-react";
import TaskQrModal from "@/components/TaskQrModal";

type Stage = "idle" | "disrupting" | "impact" | "reopt" | "verify" | "done";

export default function AllocationPage() {
  const qc = useQueryClient();
  const { data: tasks } = useQuery({ queryKey: ["tasks"], queryFn: getTasks, refetchInterval: 8000 });
  const { data: employees } = useQuery({ queryKey: ["employees"], queryFn: getEmployees, refetchInterval: 8000 });
  const lastDisruption = useAllocationStore((s) => s.lastDisruption);
  const clearDisruption = useAllocationStore((s) => s.clearDisruption);

  const [showSimModal, setShowSimModal] = useState(false);
  const [showResetModal, setShowResetModal] = useState(false);
  const [selectedEmpId, setSelectedEmpId] = useState<string>("");
  const [stage, setStage] = useState<Stage>("idle");
  const [optimizing, setOptimizing] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [traceTask, setTraceTask] = useState<string | null>(null);
  const [trace, setTrace] = useState<DecisionTrace | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);
  const [qrTask, setQrTask] = useState<TaskOut | null>(null);

  const availableEmployees = (employees || []).filter((e) => e.availability_status === "AVAILABLE");

  async function handleOptimize() {
    setOptimizing(true);
    try {
      await optimizeAllocation({});
      await qc.invalidateQueries({ queryKey: ["tasks"] });
      await qc.invalidateQueries({ queryKey: ["employees"] });
    } finally {
      setOptimizing(false);
    }
  }

  async function runDisruption() {
    if (!selectedEmpId) return;
    const emp = employees?.find((e) => e.id === selectedEmpId);
    setShowSimModal(false);
    clearDisruption();
    setStage("disrupting");
    await sleep(550);
    setStage("impact");
    await sleep(650);
    setStage("reopt");
    try {
      await triggerEmployeeUnavailable(selectedEmpId, `${emp?.name || "Employee"} marked unavailable (simulated disruption)`);
      setStage("verify");
      await sleep(450);
      setStage("done");
      await qc.invalidateQueries({ queryKey: ["tasks"] });
      await qc.invalidateQueries({ queryKey: ["employees"] });
      await qc.invalidateQueries({ queryKey: ["dashboard"] });
    } catch (e) {
      setStage("idle");
    }
  }

  async function handleResetDemo() {
    setShowResetModal(false);
    setResetting(true);
    clearDisruption();
    setStage("idle");
    try {
      await resetDemo();
      await qc.invalidateQueries();
    } finally {
      setResetting(false);
    }
  }

  async function openTrace(taskId: string) {
    setTraceTask(taskId);
    setTraceLoading(true);
    try {
      const t = await getDecisionTrace(taskId);
      setTrace(t);
    } catch {
      setTrace(null);
    } finally {
      setTraceLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Live Allocation</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>Real-time task → employee assignment, powered by OR-Tools CP-SAT.</p>
        </div>
        <div className="flex gap-2.5">
          <Button variant="secondary" onClick={handleOptimize} loading={optimizing}>
            <Sparkles size={14} /> {optimizing ? "Optimizing…" : "Optimize Allocation"}
          </Button>
          <Button variant="danger" onClick={() => setShowSimModal(true)}>
            <AlertTriangle size={14} /> Simulate Employee Unavailable
          </Button>
          <Button variant="ghost" onClick={() => setShowResetModal(true)} loading={resetting} title="Restore the original demo dataset (30 employees, 100 tasks, T4021 → Priya)">
            <RotateCcw size={14} /> {resetting ? "Resetting…" : "Reset Demo"}
          </Button>
        </div>
      </div>

      {stage !== "idle" && <DisruptionFlow stage={stage} onClose={() => setStage("idle")} />}

      {lastDisruption && stage === "idle" && (
        <Card className="mb-6 animate-fade-rise" style={{ borderLeft: "3px solid var(--bad)" }}>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>
                <AlertTriangle size={15} />
              </div>
              <div>
                <div className="font-semibold text-sm">
                  Disruption handled: {lastDisruption.affected_employee_name || "employee"} became unavailable
                </div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                  {lastDisruption.changes?.length || 0} task(s) reassigned in {Math.round(lastDisruption.duration_ms)}ms · Fairness index {lastDisruption.fairness_index?.toFixed(2)}
                </div>
              </div>
            </div>
            <button onClick={clearDisruption} className="p-1 rounded-lg transition-colors hover:bg-[var(--bg-subtle)]" style={{ color: "var(--text-faint)" }}>
              <X size={16} />
            </button>
          </div>
          <div className="mt-4 space-y-2">
            {(lastDisruption.changes || []).map((c: any) => (
              <div key={c.task_id} className="text-sm rounded-xl p-3" style={{ background: "var(--bg-subtle)" }}>
                <div className="flex items-center gap-2 font-medium flex-wrap">
                  <span className="font-mono text-xs" style={{ color: "var(--text-faint)" }}>{c.task_id}</span>
                  <span>{c.old_employee_name || "Unassigned"}</span>
                  <ArrowRight size={13} style={{ color: "var(--text-faint)" }} />
                  <span style={{ color: "var(--brand)" }}>{c.new_employee_name || "Unassigned"}</span>
                </div>
                <div className="text-xs mt-1.5 leading-relaxed" style={{ color: "var(--text-muted)" }}>{c.explanation}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card className="overflow-x-auto p-0">
        {!tasks ? (
          <div className="p-5"><SkeletonRows rows={8} cols={6} /></div>
        ) : tasks.length === 0 ? (
          <EmptyState icon={<Inbox size={32} />} title="No tasks yet" description="Create tasks from the Tasks page, then run Optimize Allocation." />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)", borderBottom: "1px solid var(--border)" }}>
                <th className="py-3 px-5">Task</th>
                <th className="py-3 px-3">Employee</th>
                <th className="py-3 px-3">Skill Match</th>
                <th className="py-3 px-3">Workload</th>
                <th className="py-3 px-3">SLA Risk</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-5">Why</th>
              </tr>
            </thead>
            <tbody>
              {tasks.slice(0, 60).map((t) => (
                <tr key={t.id} className="table-row-hover" style={{ borderBottom: "1px solid var(--border)" }}>
                  <td className="py-3 px-5">
                    <div className="font-medium">{t.title}</div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <span className="font-mono text-[11px]" style={{ color: "var(--text-faint)" }}>{t.id}</span>
                      <PriorityBadge priority={t.priority} />
                    </div>
                  </td>
                  <td className="py-3 px-3">{t.assigned_employee_name || <span style={{ color: "var(--text-faint)" }}>Unassigned</span>}</td>
                  <td className="py-3 px-3 tabular-nums">{t.skill_match_score != null ? `${Math.round(t.skill_match_score * 100)}%` : "—"}</td>
                  <td className="py-3 px-3" style={{ color: "var(--text-muted)" }}>{t.estimated_hours}h</td>
                  <td className="py-3 px-3">{t.sla_risk != null ? <RiskBadge risk={t.sla_risk} /> : "—"}</td>
                  <td className="py-3 px-3"><StatusBadge status={t.status} /></td>
                  <td className="py-3 px-5">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => openTrace(t.id)}
                        className="inline-flex items-center gap-1 text-xs font-semibold transition-opacity hover:opacity-70"
                        style={{ color: "var(--brand)" }}
                      >
                        <MessageSquareText size={12} /> Explain
                      </button>
                      <button
                        onClick={() => setQrTask(t)}
                        className="inline-flex items-center gap-1 text-xs font-semibold transition-opacity hover:opacity-70"
                        style={{ color: "var(--text-faint)" }}
                        title="Show QR code for this task"
                      >
                        <QrCode size={12} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {showSimModal && (
        <Modal onClose={() => setShowSimModal(false)}>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>
              <AlertTriangle size={17} />
            </div>
            <div className="font-semibold">Simulate Employee Unavailable</div>
          </div>
          <p className="text-xs mt-2 mb-4 leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Select an employee to mark unavailable. Affected tasks are automatically re-optimized with minimum disruption to the rest of the schedule.
          </p>
          <select
            value={selectedEmpId} onChange={(e) => setSelectedEmpId(e.target.value)}
            className="w-full border rounded-xl px-3.5 py-2.5 text-sm mb-5 outline-none transition-all focus-ring"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
          >
            <option value="">Select employee…</option>
            {availableEmployees.map((e) => <option key={e.id} value={e.id}>{e.name} ({e.role})</option>)}
          </select>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowSimModal(false)}>Cancel</Button>
            <Button variant="danger" onClick={runDisruption} disabled={!selectedEmpId}>Trigger Disruption</Button>
          </div>
        </Modal>
      )}

      {showResetModal && (
        <Modal onClose={() => setShowResetModal(false)}>
          <div className="flex items-center gap-2.5 mb-1">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: "var(--info-bg)", color: "var(--info)" }}>
              <RotateCcw size={17} />
            </div>
            <div className="font-semibold">Reset Demo Data</div>
          </div>
          <p className="text-xs mt-2 mb-5 leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Restores the original deterministic dataset — 30 employees, 100 tasks, and the initial optimized
            allocation (T4021 → Priya). Use this between demo runs so the disruption scenario is always reliable.
            Any manual changes since the last reset will be lost.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setShowResetModal(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleResetDemo}>Reset Now</Button>
          </div>
        </Modal>
      )}

      {traceTask && (
        <Modal onClose={() => { setTraceTask(null); setTrace(null); }} wide>
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: "var(--text-faint)" }}>Decision Trace</div>
              <div className="font-mono text-sm font-semibold mt-0.5">{traceTask}</div>
            </div>
            <button onClick={() => { setTraceTask(null); setTrace(null); }} className="p-1.5 rounded-lg transition-colors hover:bg-[var(--bg-subtle)]" style={{ color: "var(--text-faint)" }}>
              <X size={16} />
            </button>
          </div>
          {traceLoading ? (
            <SkeletonRows rows={4} cols={3} />
          ) : !trace ? (
            <EmptyState title="No decision trace yet" description={'Run "Optimize Allocation" first to generate one for this task.'} />
          ) : (
            <div className="space-y-5">
              <div className="text-sm rounded-xl p-3.5 leading-relaxed" style={{ background: "var(--info-bg)", color: "var(--info)" }}>{trace.explanation}</div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-faint)" }}>Reason Codes</div>
                <div className="flex flex-wrap gap-1.5">
                  {trace.reason_codes.map((r) => <span key={r} className="badge" style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}>{r}</span>)}
                </div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-faint)" }}>Hard Constraints Checked</div>
                <div className="flex flex-wrap gap-1.5">
                  {trace.hard_constraints_checked.map((r) => (
                    <span key={r} className="badge" style={{ background: "var(--good-bg)", color: "var(--good)" }}><CheckCircle2 size={10} />{r}</span>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-faint)" }}>Candidates Evaluated ({trace.candidates.length})</div>
                <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid var(--border)" }}>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-left" style={{ color: "var(--text-faint)", borderBottom: "1px solid var(--border)", background: "var(--bg-subtle)" }}>
                        <th className="py-2 px-3 font-semibold">Employee</th>
                        <th className="py-2 px-3 font-semibold">Skill</th>
                        <th className="py-2 px-3 font-semibold">SLA Risk</th>
                        <th className="py-2 px-3 font-semibold">Workload</th>
                        <th className="py-2 px-3 font-semibold">Preference</th>
                        <th className="py-2 px-3 font-semibold">Chosen</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trace.candidates.map((c: any) => {
                        const chosen = c.employee_id === trace.chosen_employee_id;
                        return (
                          <tr key={c.employee_id} style={{ borderTop: "1px solid var(--border)", background: chosen ? "var(--good-bg)" : "transparent" }}>
                            <td className="py-2 px-3 font-medium">{c.employee_name}</td>
                            <td className="py-2 px-3 tabular-nums">{Math.round(c.skill_match * 100)}%</td>
                            <td className="py-2 px-3 tabular-nums">{Math.round(c.sla_risk * 100)}%</td>
                            <td className="py-2 px-3 tabular-nums">{Math.round(c.workload_utilization_after * 100)}%</td>
                            <td className="py-2 px-3 tabular-nums">{Math.round(c.preference_score * 100)}%</td>
                            <td className="py-2 px-3">{chosen ? <CheckCircle2 size={14} style={{ color: "var(--good)" }} /> : ""}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </Modal>
      )}

      {qrTask && (
        <TaskQrModal taskId={qrTask.id} taskTitle={qrTask.title} onClose={() => setQrTask(null)} />
      )}
    </AppShell>
  );
}

function DisruptionFlow({ stage, onClose }: { stage: Stage; onClose: () => void }) {
  const steps: { key: Stage; label: string }[] = [
    { key: "disrupting", label: "Disruption Detected" },
    { key: "impact", label: "Impact Analysis" },
    { key: "reopt", label: "Re-Optimization (CP-SAT)" },
    { key: "verify", label: "Solution Verification" },
    { key: "done", label: "Allocation Updated" },
  ];
  const order: Stage[] = ["disrupting", "impact", "reopt", "verify", "done"];
  const currentIdx = order.indexOf(stage);

  return (
    <Card className="mb-6 animate-fade-rise" style={{ borderLeft: "3px solid var(--brand)" }}>
      <div className="flex items-center justify-between mb-4">
        <div className="font-semibold text-sm flex items-center gap-2">
          {stage !== "done" && <Loader2 size={14} className="animate-spin" style={{ color: "var(--brand)" }} />}
          Disruption Response Pipeline
        </div>
        {stage === "done" && (
          <button onClick={onClose} className="p-1 rounded-lg transition-colors hover:bg-[var(--bg-subtle)]" style={{ color: "var(--text-faint)" }}>
            <X size={16} />
          </button>
        )}
      </div>
      <div className="flex items-center gap-1.5 flex-wrap">
        {steps.map((s, i) => {
          const active = i <= currentIdx;
          const isCurrent = s.key === stage;
          return (
            <div key={s.key} className="flex items-center gap-1.5">
              <div
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-300 ease-smooth"
                style={active ? { background: "var(--brand)", color: "white" } : { background: "var(--bg-subtle)", color: "var(--text-faint)" }}
              >
                {isCurrent && stage !== "done" ? <Loader2 size={11} className="animate-spin" /> : active ? <CheckCircle2 size={11} /> : null}
                {s.label}
              </div>
              {i < steps.length - 1 && <ArrowRight size={12} style={{ color: "var(--text-faint)" }} />}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

function Modal({ children, onClose, wide }: { children: React.ReactNode; onClose: () => void; wide?: boolean }) {
  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 p-4 animate-fade-rise"
      style={{ background: "rgba(10, 11, 16, 0.5)", backdropFilter: "blur(3px)", animationDuration: "0.18s" }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className={`card animate-scale-in p-6 w-full ${wide ? "max-w-2xl" : "max-w-sm"} max-h-[85vh] overflow-y-auto`}
        style={{ boxShadow: "var(--shadow-lg)" }}
      >
        {children}
      </div>
    </div>
  );
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

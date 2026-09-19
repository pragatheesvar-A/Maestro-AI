"use client";
import { useState } from "react";
import AppShell from "@/components/AppShell";
import { Card, Button, EmptyState } from "@/components/ui";
import { runManagerAgent } from "@/lib/api";
import { Bot, Send, ArrowRight, Sparkles, AlertCircle } from "lucide-react";

const SUGGESTIONS = [
  "Reassign all tasks from unavailable employees.",
  "Prioritize urgent tasks.",
  "Balance workload across the team.",
  "Assign all high-priority tasks while keeping workload balanced.",
];

export default function AiCenterPage() {
  const [instruction, setInstruction] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [history, setHistory] = useState<{ instruction: string; result: any }[]>([]);

  async function submit(text?: string) {
    const value = text ?? instruction;
    if (!value.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await runManagerAgent(value);
      setResult(res);
      setHistory((h) => [{ instruction: value, result: res }, ...h].slice(0, 10));
      setInstruction("");
    } catch (e: any) {
      setResult({ error: e?.response?.data?.detail || "Request failed" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <div className="mb-6 flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center text-white shrink-0 shadow-xs">
          <Bot size={19} />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Decision Center</h1>
          <p className="text-sm mt-1 max-w-2xl leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Natural language is parsed into structured optimizer parameters by a bounded LangGraph agent workflow,
            then a real CP-SAT solve makes the actual allocation decision — the LLM never assigns employees directly.
          </p>
        </div>
      </div>

      <Card className="mb-5">
        <div className="flex gap-2.5">
          <input
            value={instruction} onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="e.g. Balance workload across the team while prioritizing urgent tasks…"
            className="flex-1 border rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all focus-ring"
            style={{ borderColor: "var(--border)", background: "var(--surface)" }}
          />
          <Button onClick={() => submit()} loading={loading}>
            <Send size={14} /> {loading ? "Running…" : "Run"}
          </Button>
        </div>
        <div className="flex flex-wrap gap-2 mt-3.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s} onClick={() => submit(s)}
              className="text-xs px-3 py-1.5 rounded-full transition-colors duration-150 hover:brightness-95"
              style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {loading && (
        <Card className="mb-5">
          <div className="flex items-center gap-2 text-sm animate-pulse-soft" style={{ color: "var(--text-muted)" }}>
            <Sparkles size={15} style={{ color: "var(--brand)" }} />
            Manager Agent → Skill Agent → Workload Agent → SLA Agent → Optimization → Verification…
          </div>
        </Card>
      )}

      {result && !loading && (
        <Card className="mb-5 animate-fade-rise">
          {result.error ? (
            <div className="flex items-center gap-2 text-sm" style={{ color: "var(--bad)" }}>
              <AlertCircle size={15} /> {result.error}
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--text-faint)" }}>Interpreted Parameters</div>
                <pre className="text-xs rounded-xl p-3 overflow-x-auto" style={{ background: "var(--bg-subtle)" }}>{JSON.stringify(result.interpreted_parameters, null, 2)}</pre>
              </div>
              <div className="text-sm rounded-xl p-3" style={{ background: "var(--info-bg)", color: "var(--info)" }}>
                <span className="font-semibold">Action taken:</span> {result.action_taken}
              </div>
              {result.result?.changes?.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: "var(--text-faint)" }}>Assignment Changes ({result.result.changes.length})</div>
                  <div className="space-y-1.5">
                    {result.result.changes.slice(0, 15).map((c: any) => (
                      <div key={c.task_id} className="text-xs flex items-center gap-2 rounded-lg px-3 py-2" style={{ background: "var(--bg-subtle)" }}>
                        <span className="font-mono" style={{ color: "var(--text-faint)" }}>{c.task_id}</span>
                        {c.old_employee_name || "Unassigned"}
                        <ArrowRight size={11} style={{ color: "var(--text-faint)" }} />
                        <span className="font-medium" style={{ color: "var(--brand)" }}>{c.new_employee_name || "Unassigned"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      <Card>
        <div className="text-[11px] font-semibold uppercase tracking-wide mb-3" style={{ color: "var(--text-faint)" }}>Recent Instructions</div>
        {history.length === 0 ? (
          <EmptyState title="No instructions run yet" description="Try one of the suggestions above." />
        ) : (
          <div className="space-y-3">
            {history.map((h, i) => (
              <div key={i} className="pb-3" style={{ borderBottom: i < history.length - 1 ? "1px solid var(--border)" : "none" }}>
                <div className="text-sm font-medium">{h.instruction}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>{h.result?.action_taken}</div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  );
}

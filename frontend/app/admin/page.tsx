"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import AppShell from "@/components/AppShell";
import { Card, Button } from "@/components/ui";
import { useAuthStore } from "@/lib/store";
import { API_BASE, createTask } from "@/lib/api";
import axios from "axios";
import { Activity, ShieldCheck, CheckCircle2 } from "lucide-react";

export default function AdminPage() {
  const { role } = useAuthStore();
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => axios.get(`${API_BASE}/health`).then((r) => r.data),
    refetchInterval: 15000,
  });

  const [taskForm, setTaskForm] = useState({ title: "", priority: "MEDIUM", estimated_hours: 8, skill: "" });
  const [creating, setCreating] = useState(false);
  const [msg, setMsg] = useState("");

  async function handleCreateEmergencyTask() {
    if (!taskForm.title) return;
    setCreating(true);
    setMsg("");
    try {
      await createTask({
        title: taskForm.title, priority: "CRITICAL", estimated_hours: taskForm.estimated_hours,
        required_skills: taskForm.skill ? [{ skill_name: taskForm.skill, min_proficiency: 0.4 }] : [],
        description: "Emergency task created via Admin Settings.",
      });
      setMsg("Emergency task created. Run Optimize Allocation on the Live Allocation page to staff it.");
      setTaskForm({ title: "", priority: "MEDIUM", estimated_hours: 8, skill: "" });
    } catch (e: any) {
      setMsg(e?.response?.data?.detail || "Failed to create task.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Admin Settings</h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
          System configuration · role: <span className="font-semibold" style={{ color: "var(--text)" }}>{role}</span>
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Card>
          <div className="font-semibold text-sm mb-4 flex items-center gap-2"><Activity size={14} style={{ color: "var(--brand)" }} /> System Health</div>
          {health ? (
            <div className="space-y-3 text-sm">
              <Row label="Status" value={health.status} good />
              <Row label="Database" value={health.database} />
              <Row label="Embedding backend" value={health.embedding_backend} />
              <Row label="Event bus backend" value={health.event_bus_backend} />
            </div>
          ) : (
            <div className="text-sm" style={{ color: "var(--text-faint)" }}>Checking…</div>
          )}
        </Card>

        <Card>
          <div className="font-semibold text-sm mb-4 flex items-center gap-2">🚨 Create Emergency Task</div>
          <div className="space-y-2.5">
            <input
              placeholder="Task title" value={taskForm.title}
              onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
              className="w-full border rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all focus-ring" style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            />
            <input
              placeholder="Required skill (optional)" value={taskForm.skill}
              onChange={(e) => setTaskForm({ ...taskForm, skill: e.target.value })}
              className="w-full border rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all focus-ring" style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            />
            <input
              type="number" placeholder="Estimated hours" value={taskForm.estimated_hours}
              onChange={(e) => setTaskForm({ ...taskForm, estimated_hours: Number(e.target.value) })}
              className="w-full border rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all focus-ring" style={{ borderColor: "var(--border)", background: "var(--surface)" }}
            />
            <Button onClick={handleCreateEmergencyTask} loading={creating} variant="danger" className="w-full">
              {creating ? "Creating…" : "Create Emergency Task (CRITICAL priority)"}
            </Button>
            {msg && <div className="text-xs rounded-lg px-3 py-2" style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}>{msg}</div>}
          </div>
        </Card>

        <Card className="lg:col-span-2">
          <div className="font-semibold text-sm mb-3 flex items-center gap-2"><ShieldCheck size={14} style={{ color: "var(--brand)" }} /> Roles</div>
          <p className="text-xs mb-3" style={{ color: "var(--text-muted)" }}>RBAC is enforced server-side via JWT-encoded roles.</p>
          <div className="flex flex-wrap gap-2">
            <span className="badge" style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}>ADMIN — full access</span>
            <span className="badge" style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}>MANAGER — manage employees/tasks/allocation</span>
            <span className="badge" style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}>EMPLOYEE — read-only view</span>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}

function Row({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="flex justify-between items-center">
      <span style={{ color: "var(--text-muted)" }}>{label}</span>
      <span className="font-medium font-mono text-xs flex items-center gap-1.5">
        {good && <CheckCircle2 size={12} style={{ color: "var(--good)" }} />}
        {value}
      </span>
    </div>
  );
}

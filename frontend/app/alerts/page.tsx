"use client";
import { useQuery } from "@tanstack/react-query";
import AppShell from "@/components/AppShell";
import { Card, EmptyState } from "@/components/ui";
import { getNotifications } from "@/lib/api";
import { useAllocationStore } from "@/lib/store";
import { format } from "date-fns";
import { AlertTriangle, Bell, Info, AlertOctagon, Radio } from "lucide-react";

const SEVERITY_STYLE: Record<string, { icon: any; color: string; bg: string }> = {
  LOW: { icon: Info, color: "var(--text-muted)", bg: "var(--bg-subtle)" },
  MEDIUM: { icon: Bell, color: "var(--info)", bg: "var(--info-bg)" },
  HIGH: { icon: AlertTriangle, color: "var(--warn)", bg: "var(--warn-bg)" },
  CRITICAL: { icon: AlertOctagon, color: "var(--bad)", bg: "var(--bad-bg)" },
};

export default function AlertsPage() {
  const { data: notifications } = useQuery({ queryKey: ["notifications"], queryFn: getNotifications, refetchInterval: 10000 });
  const events = useAllocationStore((s) => s.events);

  const liveDisruptions = events.filter((e) => e.type === "EMPLOYEE_UNAVAILABLE" || e.type === "REALLOCATION_COMPLETE");

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Alerts</h1>
        <p className="text-sm mt-1 max-w-2xl leading-relaxed" style={{ color: "var(--text-muted)" }}>
          Live disruption and SLA notifications. Architecture is ready for email/SMS/push channels.
        </p>
      </div>

      <Card className="mb-5">
        <div className="font-semibold text-sm mb-4 flex items-center gap-2">
          <Radio size={14} style={{ color: "var(--brand)" }} /> Live Event Feed
          <span className="text-[10px] font-normal" style={{ color: "var(--text-faint)" }}>this session</span>
        </div>
        {liveDisruptions.length === 0 ? (
          <EmptyState icon={<Radio size={28} />} title="No live events yet" description="Trigger a disruption from Live Allocation to see events here in real time." />
        ) : (
          <div className="space-y-2.5">
            {liveDisruptions.map((e) => (
              <div key={e.id} className="text-sm rounded-xl px-3.5 py-2.5" style={{ background: "var(--bg-subtle)", borderLeft: "3px solid var(--brand)" }}>
                <div className="font-medium">{e.type.replace(/_/g, " ")}</div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-faint)" }}>{new Date(e.timestamp).toLocaleTimeString()}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="font-semibold text-sm mb-4">Notifications</div>
        {(!notifications || notifications.length === 0) ? (
          <EmptyState icon={<Bell size={28} />} title="No notifications yet" />
        ) : (
          <div className="space-y-2.5">
            {notifications.map((n: any) => {
              const style = SEVERITY_STYLE[n.severity] || SEVERITY_STYLE.LOW;
              const Icon = style.icon;
              return (
                <div key={n.id} className="flex items-start gap-3 rounded-xl p-3.5" style={{ background: style.bg }}>
                  <Icon size={16} style={{ color: style.color }} className="mt-0.5 shrink-0" />
                  <div>
                    <div className="text-sm font-medium">{n.title}</div>
                    <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{n.message}</div>
                    <div className="text-xs mt-1" style={{ color: "var(--text-faint)" }}>{format(new Date(n.created_at), "MMM d, HH:mm")}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </AppShell>
  );
}

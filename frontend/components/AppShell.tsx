"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import LiveEventToast from "./LiveEventToast";
import CommandPalette from "./CommandPalette";
import { useAuthStore, useAllocationStore } from "@/lib/store";
import { useAllocationSocket } from "@/lib/ws";
import { WifiOff } from "lucide-react";

function useRelativeTime(ts: number | null) {
  const [, forceTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);
  if (!ts) return null;
  const secs = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (secs < 2) return "just now";
  if (secs < 60) return `${secs}s ago`;
  return `${Math.round(secs / 60)}m ago`;
}

const EMPLOYEE_ALLOWED_PATHS = new Set(["/dashboard", "/alerts"]);

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { token, role, hydrate } = useAuthStore();
  const connected = useAllocationStore((s) => s.connected);
  const lastLiveUpdateAt = useAllocationStore((s) => s.lastLiveUpdateAt);
  const router = useRouter();
  const pathname = usePathname();
  const relTime = useRelativeTime(lastLiveUpdateAt);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    const t = localStorage.getItem("smartalloc_token");
    if (!t) router.replace("/login");
  }, [router]);

  // Role-based route guard: an EMPLOYEE login can reach manager/admin-only
  // pages by typing the URL directly even though they're hidden from the
  // sidebar -- redirect back to their own dashboard instead of exposing
  // company-wide screens their role shouldn't see.
  useEffect(() => {
    if (role === "EMPLOYEE" && pathname && !EMPLOYEE_ALLOWED_PATHS.has(pathname)) {
      router.replace("/dashboard");
    }
  }, [role, pathname, router]);

  useAllocationSocket();

  return (
    <div className="flex min-h-screen" style={{ background: "var(--bg)" }}>
      <Sidebar />
      <div className="ml-64 flex-1 min-w-0 relative">
        <div
          className="pointer-events-none fixed top-0 right-0 w-[560px] h-[420px] opacity-[0.06] -z-10"
          style={{ background: "radial-gradient(circle at 70% 0%, var(--brand), transparent 65%)" }}
        />
        <div
          className="sticky top-0 z-30 flex items-center justify-end gap-2.5 px-7 h-11 backdrop-blur"
          style={{ borderBottom: "1px solid var(--border)", background: "color-mix(in srgb, var(--surface) 85%, transparent)" }}
        >
          {relTime && (
            <span className="text-[10.5px]" style={{ color: "var(--text-faint)" }}>updated {relTime}</span>
          )}
          <span
            className="flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-full transition-colors duration-300"
            style={connected
              ? { color: "var(--good)", background: "var(--good-bg)" }
              : { color: "var(--text-faint)", background: "var(--bg-subtle)" }}
          >
            {connected ? (
              <><span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse-soft" /> Live</>
            ) : (
              <><WifiOff size={11} /> Connecting…</>
            )}
          </span>
        </div>
        <main className="px-7 py-6 max-w-[1600px] animate-fade-rise">{children}</main>
      </div>
      <LiveEventToast />
      <CommandPalette />
    </div>
  );
}

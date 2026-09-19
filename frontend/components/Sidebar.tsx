"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard, Users, ListChecks, Zap, Scale, ShieldAlert,
  Bot, Bell, Settings, LogOut, Search,
} from "lucide-react";
import { useAuthStore } from "@/lib/store";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["MANAGER", "ADMIN"] },
  { href: "/dashboard", label: "My Work", icon: LayoutDashboard, roles: ["EMPLOYEE"] },
  { href: "/employees", label: "Employees", icon: Users, roles: ["MANAGER", "ADMIN"] },
  { href: "/tasks", label: "Tasks", icon: ListChecks, roles: ["MANAGER", "ADMIN"] },
  { href: "/allocation", label: "Live Allocation", icon: Zap, roles: ["MANAGER", "ADMIN"] },
  { href: "/workload", label: "Workload & Fairness", icon: Scale, roles: ["MANAGER", "ADMIN"] },
  { href: "/sla", label: "SLA Analytics", icon: ShieldAlert, roles: ["MANAGER", "ADMIN"] },
  { href: "/ai-center", label: "AI Decision Center", icon: Bot, roles: ["MANAGER", "ADMIN"] },
  { href: "/alerts", label: "Alerts", icon: Bell, roles: ["MANAGER", "ADMIN", "EMPLOYEE"] },
  { href: "/admin", label: "Admin Settings", icon: Settings, roles: ["ADMIN"] },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { fullName, role, logout } = useAuthStore();

  const initials = (fullName || "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const visibleNav = NAV.filter((item) => !role || item.roles.includes(role));

  return (
    <aside
      className="fixed left-0 top-0 h-screen w-64 flex flex-col z-40"
      style={{ borderRight: "1px solid var(--border)", background: "var(--surface)" }}
    >
      <div className="px-5 h-16 flex items-center gap-2.5" style={{ borderBottom: "1px solid var(--border)" }}>
        <div className="w-8 h-8 rounded-lg gradient-brand flex items-center justify-center text-white shadow-xs shrink-0">
          <Zap size={16} strokeWidth={2.5} />
        </div>
        <div className="min-w-0">
          <div className="font-bold text-[15px] tracking-tight leading-none">
            Maestro <span className="text-gradient-brand">AI</span>
          </div>
          <div className="text-[10.5px] mt-1 truncate" style={{ color: "var(--text-faint)" }}>Dynamic Workforce Allocation</div>
        </div>
      </div>

      {role !== "EMPLOYEE" && (
        <div className="px-3 pt-3">
          <button
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs transition-colors duration-150"
            style={{ background: "var(--bg-subtle)", color: "var(--text-faint)" }}
          >
            <Search size={13} />
            <span className="flex-1 text-left">Quick search</span>
            <kbd className="text-[9.5px] font-semibold px-1.5 py-0.5 rounded" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>Ctrl K</kbd>
          </button>
        </div>
      )}

      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {visibleNav.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.label}
              href={item.href}
              className="relative flex items-center gap-2.5 px-3 py-2 rounded-xl text-[13px] font-medium transition-all duration-150 ease-smooth"
              style={active
                ? { background: "var(--brand)", color: "white" }
                : { color: "var(--text-muted)" }}
              onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "var(--bg-subtle)"; }}
              onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
            >
              <Icon size={16} strokeWidth={2} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-3 pb-4 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
        <div className="flex items-center gap-2.5 px-2 py-2 rounded-xl" style={{ background: "var(--bg-subtle)" }}>
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 text-white"
            style={{ background: "var(--brand)" }}
          >
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold truncate">{fullName || "—"}</div>
            <div className="text-[10.5px] truncate" style={{ color: "var(--text-faint)" }}>{role || ""}</div>
          </div>
          <button
            onClick={() => { logout(); router.push("/login"); }}
            className="p-1.5 rounded-lg transition-colors hover:bg-[var(--border)] shrink-0"
            title="Sign out"
            style={{ color: "var(--text-faint)" }}
          >
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}

"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Zap, ArrowRight, AlertCircle, Check } from "lucide-react";
import AutomationBackground from "@/components/AutomationBackground";

const DEMO_ACCOUNTS = [
  { label: "Manager", email: "manager@smartalloc.ai", password: "manager123" },
  { label: "Admin", email: "admin@smartalloc.ai", password: "admin123" },
  { label: "Employee", email: "employee@smartalloc.ai", password: "employee123" },
];

export default function LoginPage() {
  const [email, setEmail] = useState("manager@smartalloc.ai");
  const [password, setPassword] = useState("manager123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedDemo, setSelectedDemo] = useState<string>("Manager");
  const [shake, setShake] = useState(false);
  const [pop, setPop] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);
  const router = useRouter();

  function fillDemo(acc: (typeof DEMO_ACCOUNTS)[number]) {
    setEmail(acc.email);
    setPassword(acc.password);
    setSelectedDemo(acc.label);
    setError("");
    // Tactile feedback: the card "pops" to acknowledge the quick-fill.
    setPop(false);
    requestAnimationFrame(() => setPop(true));
  }

  async function handleLogin(e?: React.FormEvent) {
    e?.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await login(email, password);
      setAuth(data.access_token, data.role, data.full_name, data.employee_id);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Login failed. Is the backend running?");
      // Tactile feedback: shake the card on a failed sign-in.
      setShake(false);
      requestAnimationFrame(() => setShake(true));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center px-4 overflow-hidden" style={{ background: "#0a0812" }}>
      {/* Full-bleed dynamic automation background */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 gradient-brand opacity-[0.9]" />
        <AutomationBackground className="absolute inset-0 w-full h-full" />
        <div
          className="absolute inset-0"
          style={{ background: "radial-gradient(circle at 50% 50%, transparent 0%, rgba(10,8,18,0.55) 75%)" }}
        />
      </div>

      {/* Status chip, top-left */}
      <div className="absolute top-6 left-6 flex items-center gap-2.5 text-white">
        <div className="w-9 h-9 rounded-xl bg-white/15 backdrop-blur flex items-center justify-center">
          <Zap size={18} strokeWidth={2.5} />
        </div>
        <div className="font-bold text-lg tracking-tight">Maestro AI</div>
      </div>
      <div className="absolute top-6 right-6 hidden sm:flex items-center gap-1.5 text-[11px] font-medium text-white/80 bg-white/10 backdrop-blur px-3 py-1.5 rounded-full">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse-soft" />
        AI optimizer live
      </div>

      {/* Centered card */}
      <div className="relative w-full max-w-[400px] animate-fade-rise">
        <div
          className={`rounded-2xl p-7 ${shake ? "animate-shake" : ""} ${pop ? "animate-pop" : ""}`}
          onAnimationEnd={() => { setShake(false); setPop(false); }}
          style={{
            background: "rgba(21, 18, 32, 0.74)",
            backdropFilter: "blur(20px)",
            border: "1px solid rgba(255,255,255,0.1)",
            boxShadow: "0 24px 60px -12px rgba(0,0,0,0.55)",
          }}
        >
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold tracking-tight text-white">Welcome back</h2>
            <p className="text-sm mt-1.5 text-white/55">Sign in to manage live task allocation.</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="text-xs font-semibold text-white/50">Email</label>
              <input
                value={email} onChange={(e) => { setEmail(e.target.value); setSelectedDemo(""); }}
                className="mt-1.5 w-full rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all duration-150 text-white placeholder-white/30"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.12)" }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(161,121,255,0.55)")}
                onBlur={(e) => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.12)")}
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-white/50">Password</label>
              <input
                type="password" value={password} onChange={(e) => { setPassword(e.target.value); setSelectedDemo(""); }}
                className="mt-1.5 w-full rounded-xl px-3.5 py-2.5 text-sm outline-none transition-all duration-150 text-white placeholder-white/30"
                style={{ background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.12)" }}
                onFocus={(e) => (e.currentTarget.style.borderColor = "rgba(161,121,255,0.55)")}
                onBlur={(e) => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.12)")}
              />
            </div>
            {error && (
              <div className="flex items-start gap-2 text-xs rounded-xl px-3 py-2.5 text-red-200 animate-fade-rise" style={{ background: "rgba(242,97,126,0.18)" }}>
                <AlertCircle size={14} className="mt-0.5 shrink-0" />
                {error}
              </div>
            )}
            <button
              type="submit" disabled={loading}
              className="w-full text-white rounded-xl py-2.5 text-sm font-semibold transition-all duration-150 ease-smooth shadow-lg hover:brightness-110 active:scale-[0.98] disabled:opacity-60 flex items-center justify-center gap-1.5"
              style={{ background: "linear-gradient(135deg, var(--brand-strong), var(--accent))" }}
            >
              {loading ? "Signing in…" : <>Sign in <ArrowRight size={15} /></>}
            </button>
          </form>

          <div className="mt-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex-1 h-px bg-white/10" />
              <span className="text-[11px] font-medium text-white/35">DEMO ACCOUNTS</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              {DEMO_ACCOUNTS.map((acc) => {
                const active = selectedDemo === acc.label;
                return (
                  <button
                    key={acc.email}
                    type="button"
                    onClick={() => fillDemo(acc)}
                    className="relative text-xs font-medium px-2 py-2 rounded-xl transition-all duration-150 active:scale-95 flex items-center justify-center gap-1"
                    style={active
                      ? { background: "var(--brand)", borderColor: "transparent", color: "white" }
                      : { background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", color: "rgba(255,255,255,0.6)" }}
                  >
                    {active && <Check size={11} />}
                    {acc.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-white/35 mt-5">
          Real OR-Tools optimization · Live disruption reassignment · Explainable decisions
        </p>
      </div>
    </div>
  );
}

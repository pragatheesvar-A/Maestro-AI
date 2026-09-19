import { create } from "zustand";

interface AuthState {
  token: string | null;
  role: string | null;
  fullName: string | null;
  employeeId: string | null;
  setAuth: (token: string, role: string, fullName: string, employeeId?: string | null) => void;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  role: null,
  fullName: null,
  employeeId: null,
  setAuth: (token, role, fullName, employeeId) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("smartalloc_token", token);
      localStorage.setItem("smartalloc_role", role);
      localStorage.setItem("smartalloc_name", fullName);
      if (employeeId) localStorage.setItem("smartalloc_employee_id", employeeId);
      else localStorage.removeItem("smartalloc_employee_id");
    }
    set({ token, role, fullName, employeeId: employeeId ?? null });
  },
  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("smartalloc_token");
      localStorage.removeItem("smartalloc_role");
      localStorage.removeItem("smartalloc_name");
      localStorage.removeItem("smartalloc_employee_id");
    }
    set({ token: null, role: null, fullName: null, employeeId: null });
  },
  hydrate: () => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("smartalloc_token");
      const role = localStorage.getItem("smartalloc_role");
      const fullName = localStorage.getItem("smartalloc_name");
      const employeeId = localStorage.getItem("smartalloc_employee_id");
      if (token) set({ token, role, fullName, employeeId });
    }
  },
}));

export interface LiveEvent {
  id: string;
  type: string;
  payload: any;
  timestamp: number;
}

export interface FairnessPoint {
  t: number;
  value: number;
}

interface AllocationState {
  events: LiveEvent[];
  lastDisruption: any | null;
  connected: boolean;
  fairnessHistory: FairnessPoint[];
  lastLiveUpdateAt: number | null;
  addEvent: (type: string, payload: any) => void;
  setDisruption: (payload: any) => void;
  setConnected: (c: boolean) => void;
  clearDisruption: () => void;
  pushFairness: (value: number) => void;
  markLiveUpdate: () => void;
}

export const useAllocationStore = create<AllocationState>((set) => ({
  events: [],
  lastDisruption: null,
  connected: false,
  fairnessHistory: [],
  lastLiveUpdateAt: null,
  addEvent: (type, payload) =>
    set((s) => ({
      events: [{ id: `${Date.now()}-${Math.random()}`, type, payload, timestamp: Date.now() }, ...s.events].slice(0, 50),
    })),
  setDisruption: (payload) => set({ lastDisruption: payload }),
  clearDisruption: () => set({ lastDisruption: null }),
  setConnected: (c) => set({ connected: c }),
  markLiveUpdate: () => set({ lastLiveUpdateAt: Date.now() }),
  // Tracks the real, live fairness index over the session -- a rolling
  // window of actual values returned by /analytics/dashboard, not
  // simulated data. Powers the Dashboard's "Fairness Trend" sparkline so a
  // viewer can watch allocation balance hold steady through a disruption.
  pushFairness: (value) =>
    set((s) => {
      const last = s.fairnessHistory[s.fairnessHistory.length - 1];
      if (last && Math.abs(last.value - value) < 0.0005) return s; // dedupe unchanged polls
      return { fairnessHistory: [...s.fairnessHistory, { t: Date.now(), value }].slice(-40) };
    }),
}));

"use client";
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { WS_BASE } from "./api";
import { useAllocationStore } from "./store";

// Event types that mean "the allocation/employee/task state changed on the
// server" -- any of these should instantly invalidate the relevant React
// Query caches app-wide, rather than waiting for the next 10s poll. This is
// what makes the dashboard/live allocation genuinely real-time instead of
// just frequently-polled.
const STATE_CHANGING_EVENTS = new Set([
  "REALLOCATION_COMPLETE", "EMPLOYEE_UNAVAILABLE", "EMPLOYEE_AVAILABLE", "TASK_CREATED",
]);
const INVALIDATE_KEYS = [
  "dashboard", "workload", "fairness", "sla", "sla-full", "tasks", "tasks-dashboard", "employees", "notifications",
];

/**
 * Subscribes to /ws/allocation, pushes every message into the Zustand
 * allocation store (for the live event feed / disruption banner), and
 * instantly invalidates every dashboard-relevant React Query cache so all
 * open pages reflect the change immediately -- true push-driven live
 * updates, not just polling.
 */
export function useAllocationSocket() {
  const addEvent = useAllocationStore((s) => s.addEvent);
  const setDisruption = useAllocationStore((s) => s.setDisruption);
  const setConnected = useAllocationStore((s) => s.setConnected);
  const markLiveUpdate = useAllocationStore((s) => s.markLiveUpdate);
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number>(1000);
  const qc = useQueryClient();

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(`${WS_BASE}/ws/allocation`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryRef.current = 1000;
      };
      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          addEvent(data.type, data);
          if (data.type === "REALLOCATION_COMPLETE") {
            setDisruption(data);
          }
          if (STATE_CHANGING_EVENTS.has(data.type)) {
            markLiveUpdate();
            INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
          }
        } catch (e) {
          // ignore malformed frames
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) {
          setTimeout(connect, retryRef.current);
          retryRef.current = Math.min(retryRef.current * 1.5, 10000);
        }
      };
      ws.onerror = () => {
        ws.close();
      };
    }

    connect();
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, [addEvent, setDisruption, setConnected, markLiveUpdate, qc]);
}

"use client";
import { QRCodeSVG } from "qrcode.react";
import { X, Smartphone, Copy, Check } from "lucide-react";
import { useState } from "react";

/**
 * QR-code based task lookup: encodes a deep link
 * (`/tasks?taskId=<id>`) that a phone camera can scan to jump straight to
 * that task's live details -- assignee, skill match, SLA risk, status --
 * inside the app. Meant for a physical work-order / job-ticket printout:
 * print the QR next to the task, and whoever is on-site scans it (after
 * signing in) to see their assignment instantly instead of searching for
 * it. The link is generated client-side from the current origin, so it
 * works the same in local dev, Docker, and behind the Nginx proxy.
 */
export default function TaskQrModal({ taskId, taskTitle, onClose }: { taskId: string; taskTitle: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  const url = typeof window !== "undefined" ? `${window.location.origin}/tasks?taskId=${taskId}` : "";

  function copyLink() {
    navigator.clipboard?.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div
      className="fixed inset-0 flex items-center justify-center z-50 p-4 animate-fade-rise"
      style={{ background: "rgba(10, 8, 18, 0.5)", backdropFilter: "blur(3px)", animationDuration: "0.18s" }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="card animate-scale-in p-6 w-full max-w-xs text-center"
        style={{ boxShadow: "var(--shadow-lg)" }}
      >
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-xs font-semibold" style={{ color: "var(--text-faint)" }}>
            <Smartphone size={14} /> SCAN TO OPEN
          </div>
          <button onClick={onClose} className="p-1 rounded-lg transition-colors hover:bg-[var(--bg-subtle)]" style={{ color: "var(--text-faint)" }}>
            <X size={16} />
          </button>
        </div>

        <div className="inline-block p-4 rounded-2xl" style={{ background: "white" }}>
          <QRCodeSVG value={url || "smartalloc-ai"} size={168} fgColor="#17141f" bgColor="#ffffff" level="M" />
        </div>

        <div className="mt-4">
          <div className="font-mono text-xs" style={{ color: "var(--text-faint)" }}>{taskId}</div>
          <div className="font-semibold text-sm mt-0.5">{taskTitle}</div>
        </div>

        <p className="text-xs mt-3 leading-relaxed" style={{ color: "var(--text-muted)" }}>
          Scan with a phone camera to open this task's live assignment, skill match, and SLA risk directly.
        </p>

        <button
          onClick={copyLink}
          className="mt-4 w-full flex items-center justify-center gap-1.5 text-xs font-medium px-3 py-2 rounded-xl transition-colors duration-150"
          style={{ background: "var(--bg-subtle)", color: copied ? "var(--good)" : "var(--text-muted)" }}
        >
          {copied ? <><Check size={12} /> Link copied</> : <><Copy size={12} /> Copy link</>}
        </button>
      </div>
    </div>
  );
}

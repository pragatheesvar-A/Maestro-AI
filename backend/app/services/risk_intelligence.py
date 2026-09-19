"""
Two data-driven signals that go beyond a static, reactive allocator:

1. compute_dynamic_performance -- replaces a single static
   `historical_performance_score` with a recency-weighted, evidence-based
   score computed from that employee's own TaskHistory (exponential decay,
   half-life 30 days), so a recent slump or improvement actually moves the
   number instead of a number set once at seed time and never revisited.

2. compute_unavailability_risk -- an anticipatory (not reactive) heuristic:
   estimates how likely an employee is to become unavailable soon, from two
   real signals -- how overloaded they currently are, and how often they've
   gone unavailable historically (from the Availability audit log). This is
   an explicit, inspectable heuristic, not a trained model -- it is labeled
   as such everywhere it's surfaced, per the "don't fake accuracy" rule
   applied to the SLA model.
"""
import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import TaskHistory, Employee, Availability, AvailabilityStatus

PERFORMANCE_HALF_LIFE_DAYS = 30


def _quality(h: TaskHistory) -> float:
    breach_penalty = 1.0 if not h.was_sla_breached else 0.4
    return breach_penalty * (0.5 + 0.5 * h.skill_match_at_assignment)


def compute_dynamic_performance(db: Session, employee: Employee) -> dict:
    history = (
        db.query(TaskHistory)
        .filter(TaskHistory.employee_id == employee.id)
        .order_by(TaskHistory.completed_at.desc())
        .all()
    )
    if not history:
        return {
            "score": employee.historical_performance_score, "trend": "insufficient_data",
            "sample_size": 0, "basis": "static baseline (no completed-task history yet)",
        }

    now = datetime.utcnow()
    weighted_sum, weight_total = 0.0, 0.0
    for h in history:
        completed = h.completed_at.replace(tzinfo=None) if h.completed_at.tzinfo else h.completed_at
        age_days = max(0.0, (now - completed).total_seconds() / 86400)
        w = math.exp(-age_days * math.log(2) / PERFORMANCE_HALF_LIFE_DAYS)
        weighted_sum += w * _quality(h)
        weight_total += w
    dynamic = weighted_sum / weight_total if weight_total > 0 else employee.historical_performance_score

    # Shrink toward the static prior when the sample is thin, so five years
    # of tenure isn't overridden by two data points.
    n = len(history)
    prior_weight = max(0.0, (5 - n) / 5) * 0.4
    blended = prior_weight * employee.historical_performance_score + (1 - prior_weight) * dynamic

    trend = "stable"
    if n >= 4:
        mid = n // 2
        recent_avg = sum(_quality(h) for h in history[:mid]) / mid
        older_avg = sum(_quality(h) for h in history[mid:]) / (n - mid)
        if recent_avg > older_avg + 0.05:
            trend = "improving"
        elif recent_avg < older_avg - 0.05:
            trend = "declining"

    return {
        "score": round(min(1.0, max(0.0, blended)), 3), "trend": trend, "sample_size": n,
        "basis": f"recency-weighted over {n} completed task(s), {PERFORMANCE_HALF_LIFE_DAYS}-day half-life",
    }


def compute_unavailability_risk(db: Session, employee: Employee) -> dict:
    utilization = (
        employee.current_workload_hours / employee.max_capacity_hours
        if employee.max_capacity_hours else 0.0
    )
    # Ramps 0 -> 1 as utilization climbs from 70% to 100%+ -- sustained
    # overload is a real leading indicator of burnout-driven absence.
    overload_component = max(0.0, min(1.0, (utilization - 0.7) / 0.3))

    past_events = (
        db.query(Availability)
        .filter(Availability.employee_id == employee.id, Availability.status == AvailabilityStatus.UNAVAILABLE)
        .count()
    )
    history_component = min(1.0, past_events / 3.0)

    risk = round(0.6 * overload_component + 0.4 * history_component, 3)
    tier = "HIGH" if risk >= 0.6 else "MEDIUM" if risk >= 0.3 else "LOW"
    return {
        "risk": risk, "tier": tier, "utilization": round(utilization, 3),
        "past_unavailability_events": past_events,
        "basis": "heuristic: current overload + historical unavailability frequency (not a trained model)",
    }

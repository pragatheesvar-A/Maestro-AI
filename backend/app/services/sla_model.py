"""Runtime inference wrapper for the SLA-risk and completion-time models."""
import os
import pickle
from datetime import datetime
from typing import Optional

import numpy as np

from app.ml.train_sla import SLA_MODEL_PATH, COMPLETION_MODEL_PATH, PRIORITY_MAP

_sla_bundle = None
_completion_bundle = None


def _load():
    global _sla_bundle, _completion_bundle
    if _sla_bundle is None and os.path.exists(SLA_MODEL_PATH):
        with open(SLA_MODEL_PATH, "rb") as f:
            _sla_bundle = pickle.load(f)
    if _completion_bundle is None and os.path.exists(COMPLETION_MODEL_PATH):
        with open(COMPLETION_MODEL_PATH, "rb") as f:
            _completion_bundle = pickle.load(f)


def _fallback_risk(complexity, remaining_time, workload_ratio, skill_match, priority_num) -> float:
    """Deterministic formula fallback if the trained model artifact is missing."""
    time_pressure = min(2.0, (complexity * 40) / max(remaining_time, 1))
    score = 0.4 * time_pressure / 2 + 0.25 * workload_ratio + 0.25 * (1 - skill_match) + 0.1 * (priority_num / 3)
    return float(max(0.02, min(0.98, score)))


def predict_sla_risk_and_completion(
    task_complexity: float,
    remaining_time_hours: float,
    employee_workload_ratio: float,
    skill_match: float,
    task_priority: str,
    employee_experience_years: float,
    historical_completion_ratio: float = 1.0,
) -> dict:
    _load()
    priority_num = PRIORITY_MAP.get(task_priority, 1)
    est_hours = max(1.0, task_complexity * 40 * (1.6 - skill_match) * historical_completion_ratio
                     * (1 + 0.4 * employee_workload_ratio))
    features = np.array([[
        task_complexity, remaining_time_hours, employee_workload_ratio, est_hours,
        skill_match, historical_completion_ratio, priority_num, employee_experience_years,
    ]])

    if _sla_bundle is not None:
        risk = float(_sla_bundle["model"].predict_proba(features)[0][1])
    else:
        risk = _fallback_risk(task_complexity, remaining_time_hours, employee_workload_ratio, skill_match, priority_num)

    if _completion_bundle is not None:
        completion_hours = float(_completion_bundle["model"].predict(features)[0])
    else:
        completion_hours = est_hours

    return {
        "sla_risk_probability": round(risk, 4),
        "predicted_completion_hours": round(max(0.5, completion_hours), 2),
        "model_version": "synthetic-v1" if _sla_bundle is not None else "deterministic-fallback-v1",
    }


def remaining_hours_until_deadline(deadline: Optional[datetime], sla_hours: float) -> float:
    if deadline is None:
        return sla_hours
    delta = (deadline - datetime.utcnow()).total_seconds() / 3600.0
    return max(0.5, delta)

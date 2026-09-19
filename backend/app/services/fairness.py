"""Workload fairness metrics: Jain's fairness index, Gini coefficient, variance."""
from typing import List, Tuple
import statistics


def jain_fairness_index(values: List[float]) -> float:
    if not values or all(v == 0 for v in values):
        return 1.0
    n = len(values)
    num = sum(values) ** 2
    den = n * sum(v * v for v in values)
    return round(num / den, 4) if den else 1.0


def gini_coefficient(values: List[float]) -> float:
    if not values or all(v == 0 for v in values):
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    cum = 0.0
    for i, v in enumerate(sorted_vals, start=1):
        cum += i * v
    total = sum(sorted_vals)
    if total == 0:
        return 0.0
    gini = (2 * cum) / (n * total) - (n + 1) / n
    return round(max(0.0, min(1.0, gini)), 4)


def workload_variance(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(statistics.pvariance(values), 4)


def utilization_ratios(workload_hours: List[float], capacity_hours: List[float]) -> List[float]:
    ratios = []
    for w, c in zip(workload_hours, capacity_hours):
        ratios.append(w / c if c > 0 else 0.0)
    return ratios


def fairness_penalty_for_candidate(candidate_utilization: float, mean_utilization: float) -> float:
    """
    Higher penalty for assigning to an employee already well above the team's
    mean utilization -- discourages piling work onto the same high performer.
    Returned in 0..1, higher = worse (more unfair) choice.
    """
    delta = candidate_utilization - mean_utilization
    return max(0.0, min(1.0, 0.5 + delta))

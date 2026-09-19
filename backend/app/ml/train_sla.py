"""
Trains the SLA-risk classifier and completion-time regressor on a clearly
labeled SYNTHETIC dataset (per spec: "If realistic training data is
unavailable, generate a clearly labeled synthetic dataset ... DO NOT fake
real-world accuracy").

Substitution note: the spec asks for XGBoost/LightGBM. Those require
platform-specific native wheels that are not reliably installable in a
restricted/offline hackathon sandbox, so we use scikit-learn's
GradientBoostingClassifier / GradientBoostingRegressor -- the closest
stable, pure-Python-wheel equivalent (same gradient-boosted-trees family).
The training/feature code is isolated in this module so swapping in real
xgboost/lightgbm later is a ~5 line change.

Features used (per spec):
  task_complexity, remaining_time_hours, employee_workload_ratio,
  estimated_completion_hours, skill_match, historical_completion_ratio,
  task_priority_numeric, employee_experience_years

Run: python -m app.ml.train_sla
"""
import os
import pickle
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, mean_absolute_error

MODEL_DIR = os.path.dirname(__file__)
SLA_MODEL_PATH = os.path.join(MODEL_DIR, "sla_risk_model.pkl")
COMPLETION_MODEL_PATH = os.path.join(MODEL_DIR, "completion_time_model.pkl")

PRIORITY_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
FEATURE_NAMES = [
    "task_complexity", "remaining_time_hours", "employee_workload_ratio",
    "estimated_completion_hours", "skill_match", "historical_completion_ratio",
    "task_priority_numeric", "employee_experience_years",
]


def generate_synthetic_dataset(n=4000, seed=42):
    rng = np.random.default_rng(seed)
    complexity = rng.uniform(0.1, 1.0, n)
    remaining_time = rng.uniform(2, 200, n)
    workload_ratio = rng.uniform(0.0, 1.3, n)
    skill_match = rng.uniform(0.2, 1.0, n)
    experience = rng.uniform(0.5, 15, n)
    priority = rng.integers(0, 4, n)
    historical_ratio = np.clip(rng.normal(1.0, 0.25, n), 0.5, 2.5)

    base_hours = complexity * 40 * (1.6 - skill_match) * historical_ratio
    estimated_completion = np.clip(base_hours * (1 + 0.4 * workload_ratio), 1, 300)

    # Synthetic ground truth: risk increases when estimated completion
    # approaches/exceeds remaining time, when workload is high, skill match
    # low, and priority high (tighter tolerance expected for urgent tasks).
    time_pressure = estimated_completion / np.maximum(remaining_time, 1)
    risk_score = (
        0.45 * np.clip(time_pressure, 0, 2) / 2
        + 0.2 * workload_ratio
        + 0.2 * (1 - skill_match)
        + 0.1 * (priority / 3)
        + 0.05 * (1 - np.clip(experience / 15, 0, 1))
    )
    risk_prob = 1 / (1 + np.exp(-6 * (risk_score - 0.5)))
    labels = rng.binomial(1, np.clip(risk_prob, 0.02, 0.98))

    X = np.column_stack([
        complexity, remaining_time, workload_ratio, estimated_completion,
        skill_match, historical_ratio, priority, experience,
    ])
    return X, labels, estimated_completion


def train_and_save():
    X, y_risk, y_completion = generate_synthetic_dataset()
    X_train, X_test, y_train, y_test = train_test_split(X, y_risk, test_size=0.2, random_state=42)

    clf = GradientBoostingClassifier(n_estimators=120, max_depth=3, learning_rate=0.1, random_state=42)
    clf.fit(X_train, y_train)
    auc = roc_auc_score(y_test, clf.predict_proba(X_test)[:, 1])

    Xc_train, Xc_test, yc_train, yc_test = train_test_split(X, y_completion, test_size=0.2, random_state=42)
    reg = GradientBoostingRegressor(n_estimators=120, max_depth=3, learning_rate=0.1, random_state=42)
    reg.fit(Xc_train, yc_train)
    mae = mean_absolute_error(yc_test, reg.predict(Xc_test))

    with open(SLA_MODEL_PATH, "wb") as f:
        pickle.dump({"model": clf, "features": FEATURE_NAMES, "synthetic_auc": auc}, f)
    with open(COMPLETION_MODEL_PATH, "wb") as f:
        pickle.dump({"model": reg, "features": FEATURE_NAMES, "synthetic_mae": mae}, f)

    print(f"[train_sla] SLA risk classifier trained on SYNTHETIC data. Holdout AUC={auc:.3f}")
    print(f"[train_sla] Completion-time regressor trained on SYNTHETIC data. Holdout MAE={mae:.2f}h")
    print("[train_sla] NOTE: metrics reflect a synthetic dataset only, not real-world accuracy.")


if __name__ == "__main__":
    train_and_save()

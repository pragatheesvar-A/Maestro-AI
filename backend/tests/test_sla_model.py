from app.services.sla_model import predict_sla_risk_and_completion


def test_sla_risk_is_probability():
    result = predict_sla_risk_and_completion(
        task_complexity=0.5, remaining_time_hours=40, employee_workload_ratio=0.3,
        skill_match=0.8, task_priority="MEDIUM", employee_experience_years=5,
    )
    assert 0.0 <= result["sla_risk_probability"] <= 1.0
    assert result["predicted_completion_hours"] > 0
    assert result["model_version"] in ("synthetic-v1", "deterministic-fallback-v1")


def test_high_pressure_scenario_yields_higher_risk_than_low_pressure():
    high_pressure = predict_sla_risk_and_completion(
        task_complexity=0.95, remaining_time_hours=2, employee_workload_ratio=1.1,
        skill_match=0.2, task_priority="CRITICAL", employee_experience_years=0.5,
    )
    low_pressure = predict_sla_risk_and_completion(
        task_complexity=0.2, remaining_time_hours=200, employee_workload_ratio=0.1,
        skill_match=0.95, task_priority="LOW", employee_experience_years=10,
    )
    assert high_pressure["sla_risk_probability"] > low_pressure["sla_risk_probability"]

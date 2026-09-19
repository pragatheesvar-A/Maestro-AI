from app.services.fairness import jain_fairness_index, gini_coefficient, workload_variance, utilization_ratios


def test_jain_index_perfectly_fair():
    assert jain_fairness_index([10, 10, 10, 10]) == 1.0


def test_jain_index_unfair_allocation():
    idx = jain_fairness_index([40, 0, 0, 0])
    assert idx < 0.5


def test_jain_index_handles_all_zero():
    assert jain_fairness_index([0, 0, 0]) == 1.0


def test_gini_zero_for_equal_distribution():
    assert gini_coefficient([5, 5, 5, 5]) == 0.0


def test_gini_high_for_unequal_distribution():
    g = gini_coefficient([100, 0, 0, 0])
    assert g > 0.5


def test_workload_variance_zero_for_uniform():
    assert workload_variance([20, 20, 20]) == 0.0


def test_utilization_ratios_handles_zero_capacity():
    ratios = utilization_ratios([10, 5], [0, 10])
    assert ratios == [0.0, 0.5]

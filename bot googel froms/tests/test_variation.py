from engine.variation_engine import create_scenarios, find_duplicates


def test_scenarios_are_reproducible_and_have_distinct_ids() -> None:
    first = create_scenarios(7, seed=42)
    second = create_scenarios(7, seed=42)
    assert first == second
    assert len({scenario["scenario_id"] for scenario in first}) == 7


def test_duplicate_detection() -> None:
    prior = [{"scenario_id": "TEST-001", "answers": [{"answer": "Standard Validation"}]}]
    current = {"scenario_id": "TEST-002", "answers": [{"answer": "Standard Validation"}]}
    assert find_duplicates(current, prior) == ["TEST-001"]


def test_scenario_count_must_be_positive() -> None:
    try:
        create_scenarios(0)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected zero scenarios to be rejected.")

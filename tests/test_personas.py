import pytest

from bot.personas import (
    REQUIRED_FIELDS,
    SCENARIOS_DIR,
    Scenario,
    ScenarioError,
    get_scenario,
    load_all_scenarios,
    load_scenario,
)

REQUIRED_CATEGORIES = {"scheduling", "rescheduling", "refill", "information", "edge_case"}


def test_scenarios_dir_has_at_least_ten_scenarios():
    scenarios = load_all_scenarios()
    assert len(scenarios) >= 10


def test_all_shipped_scenarios_are_valid():
    scenarios = load_all_scenarios()
    for scenario in scenarios:
        assert isinstance(scenario, Scenario)
        for f in REQUIRED_FIELDS:
            assert getattr(scenario, f), f"{scenario.source_path}: {f} is empty"


def test_shipped_scenarios_cover_all_required_categories():
    categories = {s.category for s in load_all_scenarios()}
    missing = REQUIRED_CATEGORIES - categories
    assert not missing, f"missing scenario categories: {missing}"


def test_scenario_ids_are_unique():
    scenarios = load_all_scenarios()
    ids = [s.id for s in scenarios]
    assert len(ids) == len(set(ids))


def test_get_scenario_returns_matching_scenario():
    scenario = get_scenario("simple_scheduling_new_patient")
    assert scenario.title == "New patient books a first appointment"


def test_get_scenario_raises_for_unknown_id():
    with pytest.raises(ScenarioError):
        get_scenario("does_not_exist")


def test_system_prompt_includes_persona_and_goal_and_opening_line():
    scenario = get_scenario("simple_scheduling_new_patient")
    prompt = scenario.system_prompt
    assert scenario.goal in prompt
    assert scenario.opening_line in prompt
    assert "never" in prompt.lower()  # never reveal it's an AI/test


def test_load_scenario_missing_required_field(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("id: x\ntitle: y\n", encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(bad)


def test_load_scenario_not_a_mapping(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_scenario(bad)


def test_load_all_scenarios_rejects_duplicate_ids(tmp_path):
    content = (
        "id: dup\ntitle: t\ncategory: c\npersona: p\ngoal: g\nopening_line: o\n"
    )
    (tmp_path / "a.yaml").write_text(content, encoding="utf-8")
    (tmp_path / "b.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(ScenarioError):
        load_all_scenarios(tmp_path)


def test_scenarios_dir_constant_points_at_real_directory():
    assert SCENARIOS_DIR.is_dir()

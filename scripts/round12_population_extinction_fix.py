from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/sao_mcp/runtime/population_runtime.py",
    '''            if movement is None:\n                if not cohort.settled or cohort.location_id not in self.world_map.locations:\n                    raise RuntimeError(f"settled population cohort lacks an authoritative location: {cohort_id}")\n                location = self.world_map.locations[cohort.location_id]\n                if cohort.floor_number != location.floor_number:\n                    raise RuntimeError(f"population cohort floor/location mismatch: {cohort_id}")\n                if not self.world.floors[location.floor_number].unlocked:\n                    raise RuntimeError(f"population cohort is settled on a locked floor: {cohort_id}")\n                continue\n''',
    '''            if movement is None:\n                if cohort.headcount == 0 and not cohort.settled:\n                    if cohort.floor_number is not None or cohort.location_id is not None:\n                        raise RuntimeError(f"extinct population cohort has partial location state: {cohort_id}")\n                    continue\n                if not cohort.settled or cohort.location_id not in self.world_map.locations:\n                    raise RuntimeError(f"living settled population cohort lacks an authoritative location: {cohort_id}")\n                location = self.world_map.locations[cohort.location_id]\n                if cohort.floor_number != location.floor_number:\n                    raise RuntimeError(f"population cohort floor/location mismatch: {cohort_id}")\n                if not self.world.floors[location.floor_number].unlocked:\n                    raise RuntimeError(f"population cohort is settled on a locked floor: {cohort_id}")\n                continue\n''',
)

path = Path("tests/test_population_abstraction.py")
text = path.read_text(encoding="utf-8")
addition = r'''


def test_population_cohort_can_be_extinguished_in_transit_without_creating_a_ghost_location():
    runtime = PopulationAincradRuntime(seed=515)
    runtime.add_population_cohort("doomed_patrol", "frontline", 5, TOWN, 6.0, "field_patrol")
    runtime.schedule_population_movement("doomed_patrol", WEST_FIELD, reason="field_patrol")
    assert runtime.population.cohorts["doomed_patrol"].location_id is None

    runtime.apply_population_losses("doomed_patrol", 5, cause="route_ambush")
    state = runtime.player_population_state()
    cohort = runtime.population.cohorts["doomed_patrol"]
    assert cohort.headcount == 0
    assert cohort.location_id is None and cohort.floor_number is None
    assert "doomed_patrol" not in runtime.population_movements
    assert state["abstract_registered_players"] == 5
    assert state["abstract_living_players"] == 0
    assert state["abstract_cumulative_deaths"] == 5
    assert state["conservation_balance"] == 0
    assert runtime.population_location_state(TOWN)["headcount"] == 0
    assert runtime.population_location_state(WEST_FIELD)["headcount"] == 0

    restored = import_runtime(export_runtime(runtime))
    restored_state = restored.player_population_state()
    assert restored_state["abstract_registered_players"] == 5
    assert restored_state["abstract_living_players"] == 0
    assert restored_state["abstract_cumulative_deaths"] == 5
    assert restored.population.cohorts["doomed_patrol"].location_id is None
'''
if "test_population_cohort_can_be_extinguished_in_transit_without_creating_a_ghost_location" in text:
    raise RuntimeError("transit-extinction test already exists")
path.write_text(text.rstrip() + addition + "\n", encoding="utf-8")

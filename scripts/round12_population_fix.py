from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# PopulationCohortState is now the explicit movement authority for anonymous cohorts.
# Keep the global location-write gate strict and register that authority by name rather than bypassing it.
replace_once(
    "tests/test_movement_authority_source.py",
    '''# These modules are the only places allowed to commit live world-location mutation.\n# Scenario/services must call one of these authorities rather than editing location_id directly.\nLOCATION_AUTHORITY_FILES = {\n    Path("rules/travel.py"),\n''',
    '''# These modules are the only places allowed to commit live world-location mutation.\n# Scenario/services must call one of these authorities rather than editing location_id directly.\n# rules/population.py owns only anonymous PopulationCohortState settlement/transit state.\nLOCATION_AUTHORITY_FILES = {\n    Path("rules/travel.py"),\n    Path("rules/population.py"),\n''',
)

# A WAITING movement is still physically settled at its current location. Only an ACTIVE graph leg
# removes the cohort from location/floor summaries.
replace_once(
    "src/sao_mcp/runtime/population_runtime.py",
    '''    def _settled_cohorts_at(self, location_id: str) -> list[PopulationCohortState]:\n        return [\n            cohort\n            for cohort in self.population.cohorts.values()\n            if cohort.location_id == location_id and self._movement(cohort.cohort_id) is None\n        ]\n''',
    '''    def _settled_cohorts_at(self, location_id: str) -> list[PopulationCohortState]:\n        return [\n            cohort\n            for cohort in self.population.cohorts.values()\n            if cohort.location_id == location_id\n            and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)\n        ]\n''',
)
replace_once(
    "src/sao_mcp/runtime/population_runtime.py",
    '''        cohorts = [\n            cohort\n            for cohort in self.population.cohorts.values()\n            if cohort.floor_number == floor_number and self._movement(cohort.cohort_id) is None\n        ]\n''',
    '''        cohorts = [\n            cohort\n            for cohort in self.population.cohorts.values()\n            if cohort.floor_number == floor_number\n            and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)\n        ]\n''',
)
replace_once(
    "src/sao_mcp/runtime/population_runtime.py",
    '''                if cohort.location_id is not None and self._movement(cohort.cohort_id) is None\n''',
    '''                if cohort.location_id is not None\n                and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)\n''',
)
replace_once(
    "src/sao_mcp/runtime/population_runtime.py",
    '''                if cohort.floor_number is not None and self._movement(cohort.cohort_id) is None\n''',
    '''                if cohort.floor_number is not None\n                and (self._movement(cohort.cohort_id) is None or not self._movement(cohort.cohort_id).active)\n''',
)

replace_once(
    "tests/test_population_abstraction.py",
    '''    assert movement is not None and not movement.active\n    assert movement.wait_reason == "target_floor_gate_inactive"\n    assert runtime.population.cohorts["frontier"].location_id == TOWN\n\n    runtime.floor_boss_defeated(1)\n''',
    '''    assert movement is not None and not movement.active\n    assert movement.wait_reason == "target_floor_gate_inactive"\n    assert runtime.population.cohorts["frontier"].location_id == TOWN\n    waiting_state = runtime.player_population_state()\n    assert waiting_state["abstract_waiting_movement_players"] == 25\n    assert waiting_state["abstract_in_transit_players"] == 0\n    assert runtime.population_location_state(TOWN)["headcount"] == 25\n    assert runtime.population_floor_state(1)["headcount"] == 25\n\n    runtime.floor_boss_defeated(1)\n''',
)

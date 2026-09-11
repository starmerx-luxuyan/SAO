from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected fix anchor missing in {path}: {old[:140]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


# Expiry at the exact hourly quest boundary is resolved after that boundary's progress/generation,
# before the post-tick authority assertion. Non-hour expiries remain handled by the scheduler hook.
path = "src/sao_mcp/runtime/quest_ecology_runtime.py"
replace_once(
    path,
'''        self._generate_monster_pressure_contracts()\n        self._generate_market_shortage_contracts(tick_ms)\n        self.next_quest_ecology_tick_at_ms += QUEST_ECOLOGY_TICK_MS\n        self.assert_quest_ecology_authority()\n''',
'''        self._generate_monster_pressure_contracts()\n        self._generate_market_shortage_contracts(tick_ms)\n        self._expire_contracts(tick_ms)\n        self.next_quest_ecology_tick_at_ms += QUEST_ECOLOGY_TICK_MS\n        self.assert_quest_ecology_authority()\n''',
)

# Respect combat recovery in the multi-target verification encounter instead of weakening Timeline rules.
path = "tests/test_quest_ecology.py"
replace_once(
    path,
'''        assert result.hit\n    assert runtime.world_events.occurrences[contract.occurrence_id].status is WorldEventStatus.RESOLVED\n''',
'''        assert result.hit\n        if monster is not monsters[-1] and winner.recovery_until_ms > encounter.time_ms:\n            runtime.advance_encounter(\n                encounter.encounter_id, winner.recovery_until_ms - encounter.time_ms\n            )\n    assert runtime.world_events.occurrences[contract.occurrence_id].status is WorldEventStatus.RESOLVED\n''',
)

# The persistence invariant is that ad-hoc executable rules do not persist. Built-in runtime rules
# legitimately change as new authoritative runtime layers are added.
path = "tests/test_world_event_runtime.py"
replace_once(
    path,
'''    assert restored.world_event_state()["registered_rule_ids"] == ["floor22.witch_return"]\n''',
'''    registered = restored.world_event_state()["registered_rule_ids"]\n    assert "test.persist" not in registered\n    assert set(registered) == {"quest_ecology_contract", "floor22.witch_return"}\n''',
)

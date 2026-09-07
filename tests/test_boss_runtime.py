from sao_mcp.domain.models import EntityKind
from sao_mcp.runtime.aincrad_runtime import AincradRuntime


def _raid():
    runtime = AincradRuntime(seed=1)
    player = runtime.create_character("Raider", level=8)
    player.skill_proficiencies["one_hand_sword"] = 700
    encounter, boss = runtime.start_floor_boss_encounter(
        [player.actor_id],
        enforce_location=False,
    )
    return runtime, player, encounter, boss


def _minions(encounter, boss_id):
    return [
        actor
        for actor in encounter.participants.values()
        if actor.metadata.get("boss_parent_id") == boss_id
    ]


def test_illfang_starts_with_four_bars_and_three_sentinels():
    runtime, player, encounter, boss = _raid()
    state = runtime.boss_bar_state(boss)
    assert state["hpBars"] == 4
    assert state["phase"] == "axe_buckler"
    assert len(_minions(encounter, boss.actor_id)) == 3
    assert state["sentinelsSpawned"] == 3
    assert all(actor.kind is EntityKind.MONSTER for actor in _minions(encounter, boss.actor_id))


def test_first_hp_bar_depletion_spawns_three_more_sentinels_automatically():
    runtime, player, encounter, boss = _raid()
    boss.hp = 10_801  # One point above the first 3,600-HP bar boundary.
    result = runtime.attack(
        encounter.encounter_id,
        player.actor_id,
        boss.actor_id,
        defense="none",
        seed=1,
    )
    assert result.hit
    assert runtime.boss_bar_state(boss)["depletedBars"] >= 1
    assert len(_minions(encounter, boss.actor_id)) == 6
    assert any(event.event_type == "boss_hp_bar_depleted" for event in encounter.events)


def test_entering_fourth_bar_switches_illfang_to_hidden_nodachi_phase():
    runtime, player, encounter, boss = _raid()
    # Reconstruct a legitimate near-third-boundary state without simulating thousands of raid hits.
    boss.metadata["boss_depleted_bars"] = 2
    boss.hp = 3_601
    result = runtime.attack(
        encounter.encounter_id,
        player.actor_id,
        boss.actor_id,
        defense="none",
        seed=1,
    )
    assert result.hit
    assert runtime.boss_phase(boss).phase_id == "nodachi"
    weapon_id = boss.equipment["weapon"]
    assert boss.inventory[weapon_id].template_id == "illfang_nodachi"
    assert "offhand" not in boss.equipment
    assert any(event.event_type == "boss_phase_changed" for event in encounter.events)


def test_killing_floor_boss_marks_floor_and_awards_last_attack_bonus():
    runtime, player, encounter, boss = _raid()
    boss.metadata["boss_depleted_bars"] = 3
    boss.hp = 1
    result = runtime.attack(
        encounter.encounter_id,
        player.actor_id,
        boss.actor_id,
        defense="none",
        seed=1,
    )
    assert result.hit
    assert not boss.alive
    assert runtime.world.floors[1].floor_boss_defeated
    assert runtime.world.floors[1].scheduled_gate_activation_at_ms is not None
    assert any(item.template_id == "coat_of_midnight" for item in player.inventory.values())
    assert sum(event.event_type == "last_attack_bonus_awarded" for event in encounter.events) == 1


def test_boss_telegraph_resolves_after_reaction_window():
    runtime, player, encounter, boss = _raid()
    before = player.hp
    event = runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_overhead_cleave",
        [player.actor_id],
    )
    assert event.event_type == "boss_action_telegraphed"
    pending = boss.metadata["pending_boss_action"]
    assert pending["execute_at_ms"] > encounter.time_ms
    result = runtime.resolve_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        defenses={player.actor_id: "none"},
        seed=1,
    )
    assert result["resolved"]
    assert "pending_boss_action" not in boss.metadata
    assert player.hp < before
    assert any(event.event_type == "boss_action_resolved" for event in encounter.events)


def test_stagger_covering_execute_time_interrupts_boss_telegraph():
    runtime, player, encounter, boss = _raid()
    runtime.telegraph_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        "illfang_overhead_cleave",
        [player.actor_id],
    )
    execute_at = boss.metadata["pending_boss_action"]["execute_at_ms"]
    boss.recovery_until_ms = execute_at + 200
    before = player.hp
    result = runtime.resolve_boss_action(
        encounter.encounter_id,
        boss.actor_id,
        defenses={player.actor_id: "none"},
        seed=1,
    )
    assert result["interrupted"]
    assert player.hp == before
    assert any(event.event_type == "boss_action_interrupted" for event in encounter.events)

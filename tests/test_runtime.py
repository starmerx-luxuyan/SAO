from sao_mcp.domain.models import CursorColor
from sao_mcp.runtime.engine import GameRuntime


def test_runtime_attack_builds_threat_and_switch_opening():
    rt = GameRuntime(seed=7)
    a = rt.create_character("A", level=5)
    b = rt.create_character("B", level=5)
    party = rt.create_party(a.actor_id)
    rt.join_party(party.party_id, b.actor_id)
    monster = rt.create_training_monster(level=4)
    enc = rt.start_encounter([a.actor_id, b.actor_id, monster.actor_id])

    result = rt.attack(enc.encounter_id, a.actor_id, monster.actor_id, defense="none", seed=5)
    assert result.legal
    assert enc.last_attacker_by_target.get(monster.actor_id) == a.actor_id or not result.hit
    if result.hit:
        assert rt.monster_target(enc.encounter_id, monster.actor_id) == a.actor_id
        event = rt.switch(enc.encounter_id, a.actor_id, b.actor_id, monster.actor_id)
        assert event.event_type == "switch"
        assert monster.ai_reaction_until_ms > enc.time_ms


def test_safe_zone_blocks_hostile_damage_without_crime():
    rt = GameRuntime(seed=1)
    a = rt.create_character("A")
    b = rt.create_character("B")
    enc = rt.start_encounter([a.actor_id, b.actor_id], safe_zone=True, zone_id="town")
    before = b.hp
    result = rt.attack(enc.encounter_id, a.actor_id, b.actor_id, defense="none", seed=1)
    assert not result.legal
    assert b.hp == before
    assert a.cursor is CursorColor.GREEN


def test_illegal_out_of_range_request_does_not_create_crime_state():
    rt = GameRuntime(seed=1)
    a = rt.create_character("A")
    b = rt.create_character("B")
    enc = rt.start_encounter([a.actor_id, b.actor_id])
    result = rt.attack(enc.encounter_id, a.actor_id, b.actor_id, defense="none", distance_m=999, seed=1)
    assert not result.legal
    assert a.cursor is CursorColor.GREEN


def test_hud_server_module_imports():
    import sao_mcp.server as server
    assert server.mcp is not None

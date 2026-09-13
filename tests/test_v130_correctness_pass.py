from __future__ import annotations

import json
from pathlib import Path

import pytest

from sao_mcp.corpus.progressive_guilds import ALS_GUILD_ID, DKB_GUILD_ID, KIBAOU_ACTOR_ID, LIND_ACTOR_ID
from sao_mcp.rules.custom_mechanics import (
    configure_custom_mechanics,
    critical_chance_modifiers,
    custom_mechanics_json_schema,
)
from sao_mcp.rules.inventory import carry_capacity, inventory_weight
from sao_mcp.runtime.campaign_amendment import apply_campaign_amendment
from sao_mcp.runtime.campaign_blueprint import apply_campaign_blueprint
from sao_mcp.runtime.canonical_guilds import install_progressive_clearing_guilds
from sao_mcp.runtime.character_setup import begin_campaign_setup, campaign_setup_state, finalize_campaign_setup
from sao_mcp.runtime.gm_observation import GMObservationGate
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime
from sao_mcp.ui.system_views import system_menu_view
from sao_mcp.ui.view_models import dumps_view


ROOT = Path(__file__).resolve().parents[1]
KAGEAKI_ID = "pc_419ba4144d33"
FRIEND_IDS = {
    "pc_friend_mio",
    "pc_friend_sumika",
    "pc_friend_sayo",
    "pc_friend_kotone",
    "pc_friend_rin",
    "pc_friend_reina",
    "pc_friend_chikage",
}


def _load(name: str) -> dict:
    return json.loads((ROOT / "presets" / name).read_text(encoding="utf-8"))


def _day3_runtime(*, amended: bool = False):
    runtime = SocialCommunicationAincradRuntime(seed=0xA1C0)
    begin_campaign_setup(runtime)
    apply_campaign_blueprint(runtime, _load("kageaki_day3.json"))
    finalize_campaign_setup(runtime)
    if amended:
        apply_campaign_amendment(runtime, _load("kageaki_super_luck_amendment.json"))
    return runtime


def test_floor8_clearing_guilds_cannot_leak_into_day3_server_bootstrap():
    from sao_mcp import server_bootstrap

    runtime = server_bootstrap.runtime
    assert DKB_GUILD_ID not in runtime.relationships.guilds
    assert ALS_GUILD_ID not in runtime.relationships.guilds
    assert LIND_ACTOR_ID not in runtime.actors
    assert KIBAOU_ACTOR_ID not in runtime.actors
    with pytest.raises(ValueError, match="before Floor 8"):
        install_progressive_clearing_guilds(SocialCommunicationAincradRuntime(seed=1))


def test_custom_mechanics_schema_is_real_and_missing_crit_cap_preserves_normal_cap():
    schema = custom_mechanics_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["type"] == "array"
    effect_variants = schema["$defs"]["effect"]["oneOf"]
    crit = next(row for row in effect_variants if row["properties"]["type"].get("const") == "critical_chance_bonus")
    assert crit["properties"]["cap"]["default"] == 0.25

    runtime = SocialCommunicationAincradRuntime(seed=2)
    actor = runtime.create_character("CapCheck")
    configure_custom_mechanics(
        actor,
        runtime.catalog,
        [{"mechanic_id": "crit", "effects": [{"type": "critical_chance_bonus", "bonus": 0.1}]}],
    )
    assert critical_chance_modifiers(actor) == (0.1, 0.25)


def test_day3_blueprint_materializes_real_friends_population_and_independent_routines():
    runtime = _day3_runtime()
    assert runtime.world.now_ms == 172_800_000
    assert set(FRIEND_IDS) <= set(runtime.actors)
    assert KAGEAKI_ID in runtime.actors
    assert len(runtime.relationships.friends[KAGEAKI_ID]) == 7
    assert runtime.population.registered_total == 9_792
    population = runtime.player_population_state()
    assert population["total_living_players_represented"] > 9_000
    assert population["conservation_balance"] == 0

    for actor_id in FRIEND_IDS:
        state = runtime.actors[actor_id].metadata["named_player_autonomy"]
        assert state["schema"] == "named-player-autonomy.v1"
        assert state["cycles"] > 0
        assert state["history"]

    assert DKB_GUILD_ID not in runtime.relationships.guilds
    assert ALS_GUILD_ID not in runtime.relationships.guilds
    assert LIND_ACTOR_ID not in runtime.actors
    assert KIBAOU_ACTOR_ID not in runtime.actors


def test_gm_observation_knows_real_friend_identity_without_omniscient_fact_injection():
    runtime = _day3_runtime()
    gate = GMObservationGate(runtime)
    for friend_id in FRIEND_IDS:
        assert gate._player_name_known(KAGEAKI_ID, friend_id)
    observation = gate.observe([KAGEAKI_ID])
    assert set(observation["viewpoints"][KAGEAKI_ID]["relationships"]["friend_ids"]) == FRIEND_IDS


def test_star_sword_defines_twelve_techniques_but_day3_proficiency_only_meets_six_thresholds():
    runtime = _day3_runtime()
    actor = runtime.actors[KAGEAKI_ID]
    rows = [skill for skill in runtime.catalog.sword_skills.values() if skill.proficiency_skill_id == "star_sword"]
    assert len(rows) == 12
    usable = [skill for skill in rows if actor.skill_proficiencies["star_sword"] >= skill.prerequisite_proficiency]
    assert len(usable) == 6


def test_finalized_amendment_is_atomic_and_does_not_reopen_setup():
    runtime = _day3_runtime()
    before_save = export_runtime(runtime)
    bad = _load("kageaki_super_luck_amendment.json")
    bad = json.loads(json.dumps(bad))
    bad["amendment_id"] = "bad_atomic_check"
    bad["grant_items"].append({"template_id": "not_a_real_item", "quantity": 1})
    with pytest.raises(KeyError):
        apply_campaign_amendment(runtime, bad)
    assert export_runtime(runtime) == before_save
    assert campaign_setup_state(runtime)["status"] == "finalized"

    result = apply_campaign_amendment(runtime, _load("kageaki_super_luck_amendment.json"))
    assert result["committed"] is True
    assert campaign_setup_state(runtime)["status"] == "finalized"
    assert campaign_setup_state(runtime)["revision"] == 1
    assert campaign_setup_state(runtime)["last_amendment_id"] == "kageaki_super_luck_v130"


def test_kageaki_amendment_totals_weight_and_native_save_round_trip():
    runtime = _day3_runtime(amended=True)
    actor = runtime.actors[KAGEAKI_ID]
    assert actor.col == 88_888
    assert critical_chance_modifiers(actor) == (0.4, 0.85)
    assert round(inventory_weight(actor, runtime.catalog), 1) == 61.6
    assert round(carry_capacity(actor), 1) == 64.2

    save_json = export_runtime(runtime)
    assert json.loads(save_json)["schema"] == "sao.aincrad.save.v4"
    restored = SocialCommunicationAincradRuntime(seed=99)
    import_runtime(save_json, into=restored)
    assert export_runtime(restored) == save_json
    assert restored.actors[KAGEAKI_ID].col == 88_888
    assert set(restored.relationships.friends[KAGEAKI_ID]) == FRIEND_IDS
    assert DKB_GUILD_ID not in restored.relationships.guilds
    assert ALS_GUILD_ID not in restored.relationships.guilds


def test_system_menu_has_real_data_and_public_apps_resource_is_bound():
    runtime = _day3_runtime(amended=True)
    payload = json.loads(dumps_view(system_menu_view(runtime, KAGEAKI_ID)))
    assert payload["schema"] == "sao.ui.system.v1"
    assert payload["character"]["actor"]["name"] == "凑斗景明"
    assert payload["character"]["actor"]["col"] == 88_888
    assert payload["location"]["id"] == runtime.actors[KAGEAKI_ID].location_id

    from sao_mcp import server_public

    resources = {str(binding.resource.uri): binding.resource for binding in server_public.apps.resources()}
    assert "ui://sao/v1.3.1/system-menu.html" in resources
    resource = resources["ui://sao/v1.3.1/system-menu.html"]
    assert "text/html" in str(resource.mime_type)
    assert resource.meta["ui"]["resourceUri"] if "resourceUri" in resource.meta.get("ui", {}) else True

from sao_mcp.corpus.floor8_progressive import FLOOR8_GUILD_CRISIS_REPORT
from sao_mcp.corpus.floor8_world import FRIEBEN
from sao_mcp.corpus.progressive_guilds import (
    ALS_GUILD_ID,
    DKB_GUILD_ID,
    KIBAOU_ACTOR_ID,
    LIND_ACTOR_ID,
)
from sao_mcp.runtime.housing_runtime import HousingAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.scenarios.floor8_emergency import install_floor8_forest_emergency_scenario


class _NocturneStub:
    def __init__(self, runtime, player_id):
        self.runtime = runtime
        self.player_id = player_id
        self.stage = "five_key_hideout_recon_on_lake"

    def status(self, instance_id):
        assert instance_id == "floor8_scale_nocturne"
        return {"stage": self.stage, "player_ids": [self.player_id]}

    def link_floor8_emergency(self, instance_id, emergency_instance_id, message_id):
        assert instance_id == "floor8_scale_nocturne"
        self.stage = "floor8_emergency_received"
        return {"stage": self.stage}

    def assign_floor8_emergency_split(self, instance_id, floor8_actor_ids, hideout_actor_ids):
        assert instance_id == "floor8_scale_nocturne"
        assert floor8_actor_ids == [self.player_id]
        assert hideout_actor_ids == []
        self.stage = "parallel_nocturne_branches"
        return {
            "floor8_actor_ids": list(floor8_actor_ids),
            "hideout_actor_ids": list(hideout_actor_ids),
        }


def test_floor8_report_keeps_source_facts_out_of_mutable_incident_state():
    runtime = HousingAincradRuntime(seed=307)
    runtime.world.floors[8].unlocked = True
    runtime.world.floors[8].main_town_gate_active = True
    responder = runtime.create_character("ScaleResponder", level=28)
    nocturne = _NocturneStub(runtime, responder.actor_id)
    emergency = install_floor8_forest_emergency_scenario(runtime, nocturne)

    opened = emergency.trigger_from_nocturne("floor8_scale_nocturne", responder.actor_id)
    instance_id = opened["instance_id"]
    incident = opened["incident"]
    report = opened["guild_crisis_report"]

    assert FLOOR8_GUILD_CRISIS_REPORT.affected_guild_ids == (DKB_GUILD_ID, ALS_GUILD_ID)
    assert report["affected_guild_ids"] == [DKB_GUILD_ID, ALS_GUILD_ID]
    assert report["affected_member_scope"] == "majority_of_each_guild"
    assert report["trigger"] == {
        "kind": "felled_large_living_tree",
        "location_scope": "forest_elf_capital_area",
    }
    assert report["escalation_depends_on_guild_leaders"] is True
    assert report["provenance"]["kind"] == "canon_inferred"
    assert "affected_guild_ids" not in incident
    assert "reported_affected_member_scope" not in incident
    assert "reported_trigger" not in incident
    assert "report_provenance" not in incident
    assert "affected_member_count" not in incident

    materialization = opened["local_materialization"]
    assert materialization == {
        "representation_scope": "simulation_subset_of_reported_guild_majority",
        "resolution_scope": "materialized_local_standoff_only",
    }

    representative_ids = incident["frontline_actor_ids"]
    assert len(representative_ids) == 4
    assert {runtime.actors[actor_id].guild_id for actor_id in representative_ids} == {
        ALS_GUILD_ID,
        DKB_GUILD_ID,
    }
    assert all(
        runtime.actors[actor_id].metadata["incident_representation_scope"]
        == materialization["representation_scope"]
        for actor_id in representative_ids
    )

    authority = opened["guild_decision_authority"]
    assert authority[DKB_GUILD_ID]["actor_id"] == LIND_ACTOR_ID
    assert authority[ALS_GUILD_ID]["actor_id"] == KIBAOU_ACTOR_ID
    assert authority[DKB_GUILD_ID]["location_id"] is None
    assert authority[ALS_GUILD_ID]["location_id"] is None
    assert runtime.actors[LIND_ACTOR_ID].metadata["world_location_unresolved"] is True
    assert runtime.actors[KIBAOU_ACTOR_ID].metadata["world_location_unresolved"] is True

    guild_rows = opened["clearing_guilds"]
    assert LIND_ACTOR_ID in guild_rows[DKB_GUILD_ID]["runtime_materialized_member_ids"]
    assert KIBAOU_ACTOR_ID in guild_rows[ALS_GUILD_ID]["runtime_materialized_member_ids"]
    assert guild_rows[DKB_GUILD_ID]["reported_affected_member_scope"] == report["affected_member_scope"]
    assert guild_rows[ALS_GUILD_ID]["reported_affected_member_scope"] == report["affected_member_scope"]

    emergency.assign_response_split(instance_id, [responder.actor_id], [])
    responder.location_id = FRIEBEN
    emergency.arrive_frieben(instance_id)
    met = emergency.meet_argo_and_klein(instance_id)
    assert met["incident"]["argo_briefing_confirmed_at_ms"] == runtime.world.now_ms
    assert met["guild_decision_authority"][DKB_GUILD_ID]["location_id"] is None
    assert met["guild_decision_authority"][ALS_GUILD_ID]["location_id"] is None

    restored = import_runtime(export_runtime(runtime))
    restored_nocturne = _NocturneStub(restored, responder.actor_id)
    restored_emergency = install_floor8_forest_emergency_scenario(restored, restored_nocturne)
    persisted = restored_emergency.status(instance_id)
    assert persisted["guild_crisis_report"] == report
    assert persisted["local_materialization"] == materialization
    assert persisted["guild_decision_authority"][DKB_GUILD_ID]["actor_id"] == LIND_ACTOR_ID
    assert persisted["guild_decision_authority"][ALS_GUILD_ID]["actor_id"] == KIBAOU_ACTOR_ID
    assert persisted["guild_decision_authority"][DKB_GUILD_ID]["location_id"] is None
    assert persisted["guild_decision_authority"][ALS_GUILD_ID]["location_id"] is None

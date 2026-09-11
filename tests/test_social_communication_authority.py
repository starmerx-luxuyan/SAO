from __future__ import annotations

import ast
from pathlib import Path

from sao_mcp.rules.social_communication import SocialDeliveryState
from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "src/sao_mcp/scenarios"


def test_social_communication_is_one_single_inheritance_layer_above_quest_ecology():
    assert SocialCommunicationAincradRuntime.__bases__ == (QuestEcologyAincradRuntime,)


def test_social_delivery_carries_transport_provenance_not_duplicate_fact_value_or_actor_state():
    fields = set(SocialDeliveryState.__dataclass_fields__)
    assert "value" not in fields
    assert "belief" not in fields
    assert "actor_location_id" not in fields
    assert "guild_members" not in fields
    assert "inventory" not in fields
    assert {"source_event_id", "received_event_id", "fact_id"}.issubset(fields)


def test_scenarios_cannot_mutate_social_delivery_or_cursor_authorities_directly():
    forbidden = {
        "social_deliveries",
        "social_knowledge_cursor",
        "social_quest_cursor",
        "next_social_tick_at_ms",
        "_schedule_social_delivery",
        "_deliver_social_fact",
        "advance_social_communication_tick",
        "argo_publishable_event_ids",
    }
    violations = []
    for path in SCENARIOS.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in forbidden:
                violations.append(f"{path.name}:{node.lineno}:{node.attr}")
    assert violations == []


def test_server_bootstrap_uses_social_communication_as_authoritative_top_runtime():
    source = (ROOT / "src/sao_mcp/server_bootstrap.py").read_text(encoding="utf-8")
    assert "SocialCommunicationAincradRuntime" in source
    assert "QuestEcologyAincradRuntime(seed=0xA1C0)" not in source
    assert "register_social_autonomy_tools" in source


def test_social_server_has_actions_and_observation_without_direct_knowledge_mutation_surface():
    source = (ROOT / "src/sao_mcp/server_social_autonomy.py").read_text(encoding="utf-8")
    for name in (
        "send_known_fact_message",
        "post_guild_fact_notice",
        "spread_local_rumor",
        "subscribe_argo_intelligence",
        "brief_argo",
        "get_social_communication_state",
    ):
        assert f"def {name}" in source
    assert "_record_knowledge_event" not in source
    assert "social_deliveries[" not in source

from __future__ import annotations

import inspect
from types import SimpleNamespace

from sao_mcp.runtime.player_runline import PlayerRunline


class Plan:
    def __init__(self, action):
        self.actions = (action,)


class FakeDecision:
    def __init__(self):
        self.calls = []

    def decide(self, observation, actions):
        self.calls.append((observation["revision"], actions[0]["op"]))
        return Plan(dict(actions[0]))


class FakeExecutor:
    def __init__(self):
        self.revision = 0
        self.calls = []
        self.recovery = 0
        self.encounter_time = 0
        self.active = False
        self.runtime = None

    @staticmethod
    def supported_actions():
        return {
            "travel",
            "timeline_attack",
            "advance_encounter",
            "process_timeline",
        }

    def observe(self, actor_ids):
        actor_id = actor_ids[0]
        encounters = {}
        if self.active:
            encounters["enc"] = {
                "active": True,
                "time_ms": self.encounter_time,
                "participants": {actor_id: {}},
            }
        return {
            "revision": self.revision,
            "world_now_ms": self.revision,
            "viewpoints": {
                actor_id: {
                    "observer": {
                        "actor_id": actor_id,
                        "committed_until_ms": self.recovery,
                        "recovery_until_ms": self.recovery,
                    },
                    "visible_entities": [],
                    "encounters": encounters,
                }
            },
        }

    def execute(self, actions, observer_actor_ids, world_tick_ms=999):
        assert world_tick_ms == 0
        action = dict(actions[0])
        self.calls.append(action)
        self.revision += 1
        if action["op"] == "timeline_attack":
            self.active = True
            self.recovery = 100
            self.encounter_time = 20
            self.runtime.queued_player_attacks["enc"] = [SimpleNamespace(impact_at_ms=100)]
        elif action["op"] == "process_timeline":
            self.encounter_time = 100
            self.recovery = 140
            self.runtime.queued_player_attacks["enc"] = []
        elif action["op"] == "advance_encounter":
            self.encounter_time += action["elapsed_ms"]
        return {"ok": True, "action": action}


class FakeEconomy:
    def __init__(self):
        self.buys = []

    def buy_from_vendor(self, actor, vendor_id, template_id, quantity, catalog, actor_location_id):
        row = (actor.actor_id, vendor_id, template_id, quantity, actor_location_id)
        self.buys.append(row)
        return {"bought": row}


class FakeRuntime:
    def __init__(self):
        actor = SimpleNamespace(
            actor_id="pc",
            location_id="town",
            inventory={},
            skill_proficiencies={},
            equipped_skills=[],
            metadata={"unlocked_special_skills": []},
        )
        self.actors = {"pc": actor}
        self.economy = FakeEconomy()
        self.catalog = object()
        self.queued_player_attacks = {}
        self.encounters = {}


def menu(runtime, actor_id, encounter_id):
    return {
        "character": {"inventory": []},
        "vendors": [
            {
                "vendor_id": "shop",
                "listings": [{"template_id": "bread", "stock": 10}],
            }
        ],
        "forge": {"available": False, "blacksmithSkillEquipped": False, "recipes": []},
        "skillManagement": {"slotsUsed": 0, "slotsTotal": 1, "skills": []},
        "party": None,
    }


def make_runline():
    runtime = FakeRuntime()
    executor = FakeExecutor()
    executor.runtime = runtime
    decision = FakeDecision()
    return PlayerRunline(runtime, executor, decision, menu), runtime, executor, decision


def test_contract_hides_engine_timing_ops_and_world_tick():
    contract = PlayerRunline.contract()
    assert "advance_encounter" not in contract["actions"]
    assert "process_timeline" not in contract["actions"]
    assert contract["world_tick_input"] is False
    assert "world_tick_ms" not in inspect.signature(PlayerRunline.execute).parameters


def test_compound_turn_reobserves_and_regates_each_action():
    runline, runtime, executor, decision = make_runline()
    result = runline.execute(
        "pc",
        [
            {"op": "travel", "destination_id": "x"},
            {"op": "travel", "destination_id": "y"},
        ],
    )
    assert [op for _, op in decision.calls] == ["travel", "travel"]
    assert decision.calls[1][0] > decision.calls[0][0]
    assert result["system_menu"]["party"] is None


def test_timeline_attack_owns_settle_sequence_inside_runtime_line():
    runline, runtime, executor, decision = make_runline()
    result = runline.execute(
        "pc",
        [{"op": "timeline_attack", "encounter_id": "enc", "target_id": "mob"}],
    )
    assert [call["op"] for call in executor.calls] == [
        "timeline_attack",
        "process_timeline",
        "advance_encounter",
    ]
    assert executor.calls[2]["elapsed_ms"] == 40
    assert executor.encounter_time == 140
    assert result["steps"][0]["settle"]["kind"] == "decision_boundary"
    assert result["steps"][0]["settle"]["elapsed_ms"] == 120


def test_vendor_purchase_uses_same_gate_and_refresh_line():
    runline, runtime, executor, decision = make_runline()
    result = runline.execute(
        "pc",
        [{"op": "buy_vendor", "vendor_id": "shop", "template_id": "bread", "quantity": 2}],
    )
    assert runtime.economy.buys == [("pc", "shop", "bread", 2, "town")]
    assert result["steps"][0]["op"] == "buy_vendor"


def test_engine_ops_are_rejected_from_public_actions():
    runline, *_ = make_runline()
    try:
        runline.execute("pc", [{"op": "process_timeline", "encounter_id": "enc"}])
    except ValueError as exc:
        assert "engine-owned" in str(exc)
    else:
        raise AssertionError("engine-owned op must not be publicly requestable")


def test_transfer_gate_ignores_npc_and_unknown_player_rows_without_actor_ids():
    runline, runtime, executor, decision = make_runline()
    runtime.actors["pc"].inventory["item"] = SimpleNamespace()
    observation = executor.observe(["pc"])
    observation["viewpoints"]["pc"]["visible_entities"] = [
        {"npc_id": "npc_shop", "display_name": "Merchant", "kind": "npc"},
        {"scene_ref": "unknown_player_1", "display_name": "Unknown Player", "kind": "player"},
        {"actor_id": "friend", "display_name": "Friend", "kind": "player"},
    ]
    menu_view = {
        "character": {"inventory": [{"instanceId": "item", "equipped": False}]},
        "vendors": [],
        "forge": {"available": False, "blacksmithSkillEquipped": False, "recipes": []},
        "skillManagement": {"slotsUsed": 0, "slotsTotal": 1, "skills": []},
        "party": None,
    }
    runline._ground_extension(
        "pc",
        {"op": "transfer_item", "instance_id": "item", "destination_id": "friend"},
        observation,
        menu_view,
    )

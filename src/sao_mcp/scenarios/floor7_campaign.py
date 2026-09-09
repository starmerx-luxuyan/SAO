from __future__ import annotations

from sao_mcp.corpus.floor7 import SWORD_OF_VOLUPTA_ID
from sao_mcp.corpus.floor7_pursuit import RUBY_KEY_ID
from sao_mcp.rules.nightfolk import CIVIS_NOCTE


class Floor7CampaignScenario:
    """Validate the authoritative cross-scenario state that Floor 8 inherits from Floor 7."""

    def __init__(self, runtime, pursuit, aghyellr) -> None:
        if pursuit.runtime is not runtime or aghyellr.runtime is not runtime:
            raise RuntimeError("Floor 7 campaign services must share the authoritative runtime")
        self.runtime = runtime
        self.pursuit = pursuit
        self.aghyellr = aghyellr

    def _inventory_owner(self, instance_id: str):
        owners = [actor for actor in self.runtime.actors.values() if instance_id in actor.inventory]
        if len(owners) != 1:
            raise RuntimeError(f"item instance {instance_id} must have exactly one inventory owner")
        return owners[0]

    def handoff(self, harin_instance_id: str, aghyellr_instance_id: str) -> dict:
        pursuit_state = self.pursuit.status(harin_instance_id)
        raid_state = self.aghyellr.raid_status(aghyellr_instance_id)

        if pursuit_state["stage"] != "boss_room_reached":
            raise ValueError("the Harin pursuit has not reached the Floor 7 Boss Room")
        if pursuit_state["fallen_sacred_key_count"] != 5:
            raise ValueError("the Fallen Elves do not yet control all five sacred keys")
        if pursuit_state["ruby_key_status"] != "fallen_control":
            raise ValueError("the Floor 7 Ruby Key is not in Fallen Elf control")

        ruby_owner = self._inventory_owner(pursuit_state["ruby_key_instance_id"])
        ruby = ruby_owner.inventory[pursuit_state["ruby_key_instance_id"]]
        if ruby.template_id != RUBY_KEY_ID:
            raise RuntimeError("the recorded Ruby Key instance has the wrong template")
        if not ruby_owner.metadata.get("fallen_elf") or ruby.metadata.get("fallen_control") is not True:
            raise RuntimeError("the Ruby Key handoff claims Fallen control without a real Fallen holder")

        if raid_state["boss_alive"]:
            raise ValueError("Aghyellr is still alive")
        floor7 = self.runtime.world.floors[7]
        if not floor7.floor_boss_defeated:
            raise RuntimeError("Aghyellr is defeated but Floor 7 is not marked cleared")
        if raid_state["nirrnir"]["stage"] != "cured":
            raise ValueError("Nirrnir has not been cured")
        nirrnir_id = raid_state["nirrnir_actor_id"]
        if nirrnir_id is None or nirrnir_id != raid_state["nirrnir"]["nirrnir_actor_id"]:
            raise RuntimeError("Aghyellr raid and poison story disagree on Nirrnir identity")

        if len(raid_state["civis_actor_ids"]) != 1:
            raise ValueError("the Floor 7 handoff requires exactly one Civis Nocte transformation")
        civis_id = raid_state["civis_actor_ids"][0]
        civis = self.runtime.actors[civis_id]
        if civis.metadata.get("night_rank") != CIVIS_NOCTE:
            raise RuntimeError("the recorded Floor 7 Civis actor is not actually Civis Nocte")
        if civis.metadata.get("night_master_actor_id") != nirrnir_id:
            raise RuntimeError("the Floor 7 Civis master relation does not point to Nirrnir")

        if len(raid_state["doleful_nocturne_revealed_instance_ids"]) != 1:
            raise ValueError("Doleful Nocturne has not been revealed on the Floor 7 route")
        sword_id = raid_state["doleful_nocturne_revealed_instance_ids"][0]
        sword_owner = self._inventory_owner(sword_id)
        sword = sword_owner.inventory[sword_id]
        if sword.template_id != SWORD_OF_VOLUPTA_ID:
            raise RuntimeError("the revealed Doleful Nocturne instance has the wrong public template")
        if sword.metadata.get("true_identity_revealed") is not True or sword.metadata.get("true_name") != "Doleful Nocturne":
            raise RuntimeError("the recorded Doleful Nocturne instance is not actually revealed")

        if raid_state["blood_jars_collected"] != 17 or len(raid_state["blood_jar_instance_ids"]) != 17:
            raise RuntimeError("Aghyellr's seventeen-jar dragon-blood drop is incomplete")
        cure_id = raid_state["nirrnir"]["cure_blood_instance_id"]
        if cure_id not in raid_state["blood_jar_instance_ids"]:
            raise RuntimeError("Nirrnir was not cured with blood from this Aghyellr raid")
        if any(cure_id in actor.inventory for actor in self.runtime.actors.values()):
            raise RuntimeError("the dragon-blood jar used to cure Nirrnir still exists in an inventory")

        floor8 = self.runtime.world.floors[8]
        if not floor8.unlocked and floor7.scheduled_gate_activation_at_ms is None:
            raise RuntimeError("Floor 7 is cleared but Floor 8 has neither opened nor been scheduled to open")

        return {
            "floor7Cleared": True,
            "fallenSacredKeyCount": 5,
            "fourKeyBagOwner": pursuit_state["target_key_bag_matches"][0],
            "rubyKeyInstanceId": ruby.instance_id,
            "rubyKeyOwnerId": ruby_owner.actor_id,
            "nirrnirActorId": nirrnir_id,
            "nirrnirCured": True,
            "civisActorId": civis_id,
            "dolefulNocturneInstanceId": sword_id,
            "dolefulNocturneOwnerId": sword_owner.actor_id,
            "aghyellrBloodJarCount": raid_state["blood_jars_collected"],
            "aghyellrBloodJarsRemaining": raid_state["blood_jars_remaining_in_campaign"],
            "floor8Unlocked": floor8.unlocked,
            "floor8GateScheduledAtMs": floor7.scheduled_gate_activation_at_ms,
            "fiveKeyPursuitContinues": True,
        }


def install_floor7_campaign_scenario(runtime, pursuit, aghyellr) -> Floor7CampaignScenario:
    return Floor7CampaignScenario(runtime, pursuit, aghyellr)

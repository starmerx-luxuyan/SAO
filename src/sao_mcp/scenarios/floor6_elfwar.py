from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6_ambush import IRON_KEY_ID
from sao_mcp.corpus.floor6_elfwar import (
    AGATE_KEY_ID,
    BOUHROUM_ID,
    GINDO_ID,
    KIZMEL_ID,
    KYSARAH_ID,
    KYSARAH_KATANA_ID,
    MEDITATION_SKILL_ID,
    SACRED_KEY_BAG_ID,
    TSUMUJIGURUMA_ID,
)
from sao_mcp.corpus.floor6_finale import COMBINED_IRON_KEY_ID
from sao_mcp.corpus.floor6_trials import MYIA_ID, THEANO_IRON_KEY_ID
from sao_mcp.domain.models import (
    CombatantState,
    CursorColor,
    EntityKind,
    ItemInstance,
    StatusEffectState,
    StatusType,
)
from sao_mcp.rules.group_travel import (
    complete_routed_travel_within_window,
    group_travel_record,
    routed_travel_window_record,
    travel_route_together,
)
from sao_mcp.rules.inventory import add_item, locate_item_container


CASTLE_GALEY = "floor_6_castle_galey"
LAKE_TALPHA = "floor_6_lake_talpha"
AGATE_SHRINE = "floor_6_agate_key_shrine"
STORYTELLER_SUMMIT = "floor_6_castle_galey_storyteller_summit"
CASTLE_SPRING = "floor_6_castle_galey_spirit_tree_spring"
QUSACK_RESCUE_CAVE = "floor_6_qusack_rescue_cave"

BOUHROUM_TRIAL_MS = 3 * 60 * 60 * 1000
KYSARAH_KNOCKBACK_MS = 1500


class Floor6ElfWarScenario:
    """Castle Galey release-route chapter through the Qusack rescue and Kysarah key theft."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor6_elfwar_states", {})

    def _state(self, actor_id: str) -> dict:
        try:
            return self._states()[actor_id]
        except KeyError as exc:
            raise ValueError("Floor 6 Castle Galey route has not been started") from exc

    def start_castle_galey_route(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != CASTLE_GALEY:
            raise ValueError("the Floor 6 Elf War chapter begins on arrival at Castle Galey")
        self.runtime.interact_npc(actor_id, KIZMEL_ID)
        self._states().setdefault(
            actor_id,
            {
                "actor_id": actor_id,
                "stage": "retrieve_agate_key",
                "started_at_ms": self.runtime.world.now_ms,
                "agate_key_instance_id": None,
                "agate_key_returned": False,
                "bouhroum_trial_complete": False,
                "gindo_actor_id": None,
                "gindo_qusack_route": None,
                "myia_qusack_route": None,
                "kizmel_actor_id": None,
                "kizmel_return_route": [],
                "kysarah_actor_id": None,
                "sacred_key_bag_instance_id": None,
                "combined_iron_key_instance_id": None,
            },
        )
        return self.status(actor_id)

    def retrieve_agate_key(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "retrieve_agate_key":
            raise ValueError("the Agate Key retrieval is not the current Elf War stage")
        if actor.location_id != AGATE_SHRINE:
            raise ValueError("the Agate Key is recovered at its southern shrine")
        item = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=AGATE_KEY_ID,
            owner_id=actor_id,
            metadata={"shrine_puzzle_solved": True},
        )
        add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        state["agate_key_instance_id"] = item.instance_id
        state["stage"] = "return_agate_key_to_castle"
        return self.status(actor_id)

    def return_agate_key(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "return_agate_key_to_castle" or actor.location_id != CASTLE_GALEY:
            raise ValueError("the recovered Agate Key must be returned to Castle Galey")
        item = actor.inventory.pop(state["agate_key_instance_id"])
        item.owner_id = None
        item.metadata["returned_to_castle_galey"] = True
        state["agate_key_returned"] = True
        state["stage"] = "bouhroum_trial_available"
        return self.status(actor_id)

    def complete_bouhroum_trial(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "bouhroum_trial_available":
            raise ValueError("the Castle Galey route has not reached Bouhroum's trial")
        if actor.location_id != STORYTELLER_SUMMIT:
            raise ValueError("Bouhroum's Meditation trial is performed at his summit above Castle Galey")
        self.runtime.interact_npc(actor_id, BOUHROUM_ID)
        self.runtime.advance_world(BOUHROUM_TRIAL_MS)
        actor.skill_proficiencies[MEDITATION_SKILL_ID] = max(
            500.0,
            actor.skill_proficiencies.get(MEDITATION_SKILL_ID, 0.0),
        )
        if MEDITATION_SKILL_ID not in actor.equipped_skills:
            actor.equipped_skills.append(MEDITATION_SKILL_ID)
        actor.metadata.setdefault("skill_mods", {}).setdefault(MEDITATION_SKILL_ID, [])
        if "awakening" not in actor.metadata["skill_mods"][MEDITATION_SKILL_ID]:
            actor.metadata["skill_mods"][MEDITATION_SKILL_ID].append("awakening")
        state["bouhroum_trial_complete"] = True
        state["stage"] = "castle_galey_attack_pending"
        state["bouhroum_trial_completed_at_ms"] = self.runtime.world.now_ms
        return self.status(actor_id)

    def _create_gindo_actor(self) -> CombatantState:
        actor_id = f"namedplayer_gindo_{uuid.uuid4().hex[:10]}"
        gindo = CombatantState(
            actor_id=actor_id,
            name="Gindo",
            kind=EntityKind.PLAYER,
            level=31,
            max_hp=7600,
            hp=7600,
            strength=68,
            agility=38,
            armor=260,
            evasion=7,
            cursor=CursorColor.GREEN,
            location_id=CASTLE_SPRING,
            skill_proficiencies={"spear": 630.0, "parry": 350.0},
            metadata={
                "npc_definition_id": GINDO_ID,
                "named_player_npc": True,
                "qusack_leader": True,
                "coerced_by_pk_group": True,
                "combat_stats_provenance": "simulation",
            },
        )
        weapon_template = self.runtime.catalog.weapons["starter_spear"]
        weapon = ItemInstance(
            instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
            template_id=weapon_template.template_id,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
        )
        gindo.inventory[weapon.instance_id] = weapon
        gindo.equipment["weapon"] = weapon.instance_id
        self.runtime.actors[actor_id] = gindo
        return gindo

    def trigger_castle_galey_attack(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "castle_galey_attack_pending" or actor.location_id != CASTLE_GALEY:
            raise ValueError("the Fallen Elf attack begins after the Bouhroum chapter at Castle Galey")
        gindo = self._create_gindo_actor()
        state["gindo_actor_id"] = gindo.actor_id
        state["stage"] = "spirit_tree_spring_poisoned"
        state["castle_attack_started_at_ms"] = self.runtime.world.now_ms
        self.runtime.world.global_flags["floor6_castle_galey_spirit_tree_poisoned"] = True
        self.runtime.world.global_flags["floor6_castle_galey_weakness_active"] = True
        return self.status(actor_id)

    def purify_spirit_tree_spring(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "spirit_tree_spring_poisoned" or actor.location_id != CASTLE_SPRING:
            raise ValueError("the poisoned spirit-tree spring must be reached during the Castle Galey attack")
        gindo = self.runtime.actors[state["gindo_actor_id"]]
        gindo.metadata["coercion_revealed"] = True
        gindo.metadata["qusack_hostages_revealed"] = True
        self.runtime.world.global_flags["floor6_castle_galey_spirit_tree_poisoned"] = False
        self.runtime.world.global_flags["floor6_castle_galey_weakness_active"] = False
        state["stage"] = "borrow_sacred_keys_for_qusack_rescue"
        state["spring_purified_at_ms"] = self.runtime.world.now_ms
        return self.status(actor_id)

    def borrow_sacred_key_bag(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "borrow_sacred_keys_for_qusack_rescue" or actor.location_id != CASTLE_GALEY:
            raise ValueError("the four sacred keys are borrowed at Castle Galey after the attack is contained")
        bag = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=SACRED_KEY_BAG_ID,
            owner_id=actor_id,
            metadata={"sacred_key_count": 4, "loaned_by_bouhroum": True},
        )
        add_item(actor, bag, self.runtime.catalog, allow_overweight=True)
        state["sacred_key_bag_instance_id"] = bag.instance_id
        state["stage"] = "rescue_qusack"
        return self.status(actor_id)

    def _create_kizmel_actor(self) -> CombatantState:
        actor_id = f"questnpc_kizmel_{uuid.uuid4().hex[:12]}"
        kizmel = CombatantState(
            actor_id=actor_id,
            name="Kizmel",
            kind=EntityKind.NPC,
            level=43,
            max_hp=9000,
            hp=9000,
            strength=72,
            agility=70,
            armor=285,
            evasion=15,
            cursor=CursorColor.YELLOW,
            location_id=QUSACK_RESCUE_CAVE,
            skill_proficiencies={"one_hand_sword": 760.0, "parry": 590.0},
            metadata={
                "npc_definition_id": KIZMEL_ID,
                "dark_elf_royal_guard": True,
                "combat_stats_provenance": "simulation",
            },
        )
        weapon_template = self.runtime.catalog.weapons["starter_one_hand_sword"]
        weapon = ItemInstance(
            instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
            template_id=weapon_template.template_id,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
            metadata={"descriptive_weapon": True},
        )
        kizmel.inventory[weapon.instance_id] = weapon
        kizmel.equipment["weapon"] = weapon.instance_id
        self.runtime.actors[actor_id] = kizmel
        return kizmel

    def start_qusack_rescue(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "rescue_qusack" or actor.location_id != QUSACK_RESCUE_CAVE:
            raise ValueError("the Qusack rescue occurs at the hostage cave")
        gindo = self.runtime.actors[state["gindo_actor_id"]]
        gindo_route = complete_routed_travel_within_window(
            self.runtime,
            [gindo.actor_id],
            QUSACK_RESCUE_CAVE,
            started_at_ms=int(state["spring_purified_at_ms"]),
        )
        state["gindo_qusack_route"] = routed_travel_window_record(gindo_route)
        kizmel = self._create_kizmel_actor()
        state["kizmel_actor_id"] = kizmel.actor_id
        state["stage"] = "qusack_released_kysarah_pending"
        state["qusack_hostages_released"] = True
        return self.status(actor_id)

    def _create_kysarah_actor(self) -> CombatantState:
        actor_id = f"questnpc_kysarah_{uuid.uuid4().hex[:12]}"
        weapon_template = self.runtime.catalog.weapons[KYSARAH_KATANA_ID]
        kysarah = CombatantState(
            actor_id=actor_id,
            name="Kysarah the Ransacker",
            kind=EntityKind.NPC,
            level=55,
            max_hp=15_000,
            hp=15_000,
            strength=115,
            agility=88,
            armor=360,
            evasion=20,
            cursor=CursorColor.YELLOW,
            location_id=QUSACK_RESCUE_CAVE,
            skill_proficiencies={"katana": 850.0, "parry": 780.0},
            metadata={
                "npc_definition_id": KYSARAH_ID,
                "fallen_elf_adjutant": True,
                "combat_stats_provenance": "simulation",
            },
        )
        weapon = ItemInstance(
            instance_id=f"weapon_{uuid.uuid4().hex[:12]}",
            template_id=KYSARAH_KATANA_ID,
            owner_id=actor_id,
            durability=weapon_template.base_durability,
            max_durability=weapon_template.base_durability,
        )
        kysarah.inventory[weapon.instance_id] = weapon
        kysarah.equipment["weapon"] = weapon.instance_id
        self.runtime.actors[actor_id] = kysarah
        return kysarah

    def trigger_kysarah_key_theft(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "qusack_released_kysarah_pending" or actor.location_id != QUSACK_RESCUE_CAVE:
            raise ValueError("Kysarah's theft occurs immediately after the Qusack rescue")
        bag_id = state["sacred_key_bag_instance_id"]
        if bag_id not in actor.inventory:
            raise ValueError("the borrowed bag of four sacred keys is no longer held by the player")
        cylon_key = next((item for item in actor.inventory.values() if item.template_id == IRON_KEY_ID), None)
        if cylon_key is None:
            raise ValueError("Cylon's iron key is required for the canonical Kysarah theft")

        stachion_state = self.runtime.world.global_flags.get("floor6_stachion_quest_states", {}).get(actor_id, {})
        myia_id = stachion_state.get("myia_actor_id")
        if not myia_id or myia_id not in self.runtime.actors:
            raise ValueError("Myia must have joined the release route before Kysarah steals the paired keys")
        myia = self.runtime.actors[myia_id]
        theano_key = next((item for item in myia.inventory.values() if item.template_id == THEANO_IRON_KEY_ID), None)
        if theano_key is None:
            raise ValueError("Myia is no longer carrying Theano's paired iron key")
        myia_started_at_ms = stachion_state.get("myia_met_at_ms")
        if myia_started_at_ms is None:
            raise RuntimeError("Myia release-route state has no authoritative meeting time")
        myia_route = complete_routed_travel_within_window(
            self.runtime,
            [myia.actor_id],
            QUSACK_RESCUE_CAVE,
            started_at_ms=int(myia_started_at_ms),
        )
        state["myia_qusack_route"] = routed_travel_window_record(myia_route)

        kysarah = self._create_kysarah_actor()
        gindo = self.runtime.actors[state["gindo_actor_id"]]
        kizmel = self.runtime.actors[state["kizmel_actor_id"]]
        participants = [actor_id, myia.actor_id, gindo.actor_id, kizmel.actor_id, kysarah.actor_id]
        encounter = self.runtime.start_encounter(participants, zone_id=QUSACK_RESCUE_CAVE, safe_zone=False)
        state["kysarah_encounter_id"] = encounter.encounter_id
        state["kysarah_actor_id"] = kysarah.actor_id

        for target in (actor, myia, gindo, kizmel):
            target.statuses = [status for status in target.statuses if status.stack_key != "kysarah_tsumujiguruma"]
            target.statuses.append(
                StatusEffectState(
                    effect_id=f"kysarah_tsumujiguruma:{target.actor_id}:{encounter.time_ms}",
                    status_type=StatusType.STAGGER,
                    source_id=kysarah.actor_id,
                    remaining_ms=KYSARAH_KNOCKBACK_MS,
                    magnitude=1.0,
                    tick_interval_ms=KYSARAH_KNOCKBACK_MS,
                    until_next_tick_ms=KYSARAH_KNOCKBACK_MS,
                    stack_key="kysarah_tsumujiguruma",
                    tags=("tsumujiguruma", "katana", "omnidirectional_knockback"),
                )
            )
        self.runtime._append(
            encounter,
            "kysarah_tsumujiguruma",
            kysarah.actor_id,
            None,
            sword_skill_id=TSUMUJIGURUMA_ID,
            affected_actor_ids=[actor.actor_id, myia.actor_id, gindo.actor_id, kizmel.actor_id],
        )
        self.runtime.advance_encounter(encounter.encounter_id, KYSARAH_KNOCKBACK_MS)

        bag = actor.inventory.pop(bag_id)
        bag.owner_id = kysarah.actor_id
        bag.metadata["stolen_by_kysarah"] = True
        kysarah.inventory[bag.instance_id] = bag

        actor.inventory.pop(cylon_key.instance_id)
        myia.inventory.pop(theano_key.instance_id)
        combined = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=COMBINED_IRON_KEY_ID,
            owner_id=kysarah.actor_id,
            metadata={
                "component_instance_ids": [cylon_key.instance_id, theano_key.instance_id],
                "component_template_ids": [IRON_KEY_ID, THEANO_IRON_KEY_ID],
                "repelling_charm_broken": True,
                "repelling_charm_broken_by": KYSARAH_ID,
                "combined_by_force": True,
            },
        )
        kysarah.inventory[combined.instance_id] = combined
        cylon_key.owner_id = None
        cylon_key.metadata["consumed_into_combined_iron_key"] = combined.instance_id
        theano_key.owner_id = None
        theano_key.metadata["consumed_into_combined_iron_key"] = combined.instance_id

        kysarah.metadata["retreated_with_stolen_keys"] = True
        encounter.participants = {actor_id: actor}
        encounter.positions = {actor_id: encounter.positions.get(actor_id, (-1.15, 0.0))}
        kizmel_route = travel_route_together(self.runtime, [kizmel.actor_id], CASTLE_GALEY)
        state["kizmel_return_route"] = [group_travel_record(segment) for segment in kizmel_route]
        gindo.metadata["qusack_departing_floor6"] = True
        state["stage"] = "kysarah_stole_and_combined_keys"
        state["combined_iron_key_instance_id"] = combined.instance_id
        state["kysarah_theft_at_ms"] = self.runtime.world.now_ms
        self.runtime.world.global_flags["floor6_kysarah_combined_iron_key_created"] = True
        self.runtime.world.global_flags["floor6_combined_iron_key_instance_id"] = combined.instance_id
        return self.status(actor_id)

    def status(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        actor = self.runtime.actors[actor_id]
        combined_id = self.runtime.world.global_flags.get("floor6_combined_iron_key_instance_id")
        located = locate_item_container(self.runtime.actors, combined_id) if combined_id else None
        combined_holder = None
        combined_exists = located is not None
        if located is not None:
            container, combined = located
            if combined.template_id != COMBINED_IRON_KEY_ID:
                raise RuntimeError("Floor 6 combined-key instance ID points to the wrong item template")
            if combined.owner_id is not None and combined.owner_id != container.actor_id:
                raise RuntimeError("Floor 6 combined key owner_id disagrees with its authoritative inventory container")
            combined_holder = combined.owner_id
        return {
            **state,
            "player_location_id": actor.location_id,
            "meditation_proficiency": actor.skill_proficiencies.get(MEDITATION_SKILL_ID, 0.0),
            "awakening_unlocked": "awakening" in actor.metadata.get("skill_mods", {}).get(MEDITATION_SKILL_ID, []),
            "spirit_tree_poisoned": bool(self.runtime.world.global_flags.get("floor6_castle_galey_spirit_tree_poisoned")),
            "castle_weakness_active": bool(self.runtime.world.global_flags.get("floor6_castle_galey_weakness_active")),
            "combined_iron_key_instance_id": combined_id,
            "combined_iron_key_holder_id": combined_holder,
            "combined_iron_key_exists": combined_exists,
            "next_stage": (
                "cross Lake Talpha and recover the Agate Key" if state["stage"] == "retrieve_agate_key"
                else "return the Agate Key to Castle Galey" if state["stage"] == "return_agate_key_to_castle"
                else "complete Bouhroum's three-hour Meditation trial" if state["stage"] == "bouhroum_trial_available"
                else "return to Castle Galey for the Fallen Elf attack" if state["stage"] == "castle_galey_attack_pending"
                else "purify the spirit-tree spring and confront Gindo" if state["stage"] == "spirit_tree_spring_poisoned"
                else "borrow the sacred-key bag for the Qusack rescue" if state["stage"] == "borrow_sacred_keys_for_qusack_rescue"
                else "go to the Qusack hostage cave" if state["stage"] == "rescue_qusack"
                else "resolve Kysarah's attack and key theft" if state["stage"] == "qusack_released_kysarah_pending"
                else "follow Theano's southern Golden Cube sighting" if state["stage"] == "kysarah_stole_and_combined_keys"
                else None
            ),
        }


def install_floor6_elfwar_scenario(runtime) -> Floor6ElfWarScenario:
    required_items = {AGATE_KEY_ID, SACRED_KEY_BAG_ID, IRON_KEY_ID, THEANO_IRON_KEY_ID, COMBINED_IRON_KEY_ID}
    for template_id in required_items:
        runtime.catalog.item(template_id)
    if MEDITATION_SKILL_ID not in runtime.catalog.skills or TSUMUJIGURUMA_ID not in runtime.catalog.sword_skills:
        raise RuntimeError("Floor 6 Meditation/Tsumujiguruma corpus was not loaded")
    for npc_id in (KIZMEL_ID, BOUHROUM_ID, GINDO_ID, KYSARAH_ID, MYIA_ID):
        if npc_id not in runtime.npcs.definitions:
            raise RuntimeError("Floor 6 Castle Galey NPC corpus was not loaded")
    return Floor6ElfWarScenario(runtime)

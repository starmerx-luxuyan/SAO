from __future__ import annotations

import math
import uuid

from sao_mcp.corpus.floor7 import AGHYELLR_ID, NIRRNIR_ID, SWORD_OF_VOLUPTA_ID
from sao_mcp.corpus.floor7_nirrnir import FRESH_AGHYELLR_BLOOD_ID, apply_floor7_nirrnir_corpus
from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import (
    CombatantState,
    CursorColor,
    EntityKind,
    ItemInstance,
    Provenance,
    ProvenanceKind,
    StatusEffectState,
    StatusType,
    ZoneKind,
)
from sao_mcp.rules.group_travel import complete_routed_travel_within_window, routed_travel_window_record
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.nightfolk import CIVIS_NOCTE, DOMINUS_NOCTE, become_civis_nocte, night_rank, nightfolk_state


CASINO = "floor_7_volupta_grand_casino"
KORLOY_STABLES = "floor_7_korloy_monster_stables"
BOSS_ROOM = "floor_7_boss_room"

NIRRNIR_STABILIZED_SURVIVAL_MS = 48 * 60 * 60 * 1000
HUMAN_BLOOD_BRIDGE_MS = 10 * 60 * 1000
HUMAN_BLOOD_DONOR_MAX_HP_RATIO = 0.65
HUMAN_BLOOD_BRIDGE_HP_RATIO = 0.30
GAZE_TELEGRAPH_MS = 1500
GAZE_STUN_MS = 5000  # Simulation duration; under-Level-20 immediate stun is canon.
FRESH_DRAGON_BLOOD_WINDOW_MS = 30 * 60 * 1000  # Simulation definition of 'fresh' for the runtime item.
AGHYELLR_BLOOD_JAR_COUNT = 17


class Floor7AghyellrScenario:
    """Argent Serpent poisoning, Aghyellr raid, Civis Nocte transformation and dragon-blood cure."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        apply_floor7_nirrnir_corpus(runtime.catalog)
        self._seed_world()
        runtime.register_world_advance_hook(self._on_world_advance)
        runtime.register_defeat_hook(self._on_defeat)

    def _seed_world(self) -> None:
        source = "Sword Art Online Progressive Volume 8: Rhapsody of Crimson Heat (Finish)"
        self.runtime.world_map.locations.setdefault(
            KORLOY_STABLES,
            LocationDefinition(
                KORLOY_STABLES,
                7,
                "Korloy Monster Stables",
                ZoneKind.SAFE_TOWN,
                safe_zone=True,
                provenance=Provenance(
                    ProvenanceKind.CANON_INFERRED,
                    sources=(source,),
                    notes="Casino monster-stable area where the Korloy inspection and Argent Serpent trap occur; exact internal casino geometry is abstracted.",
                ),
            ),
        )
        if not any(
            edge.from_location_id == CASINO and edge.to_location_id == KORLOY_STABLES
            for edge in self.runtime.world_map.connections
        ):
            p = Provenance(
                ProvenanceKind.SIMULATION,
                sources=(source,),
                notes="Short in-complex travel time is simulation.",
            )
            edge = TravelConnection(CASINO, KORLOY_STABLES, 3 * 60_000, provenance=p)
            self.runtime.world_map.connections = tuple(self.runtime.world_map.connections) + (edge,)
            self.runtime.world_map.adjacency.setdefault(CASINO, []).append(edge)
            self.runtime.world_map.adjacency.setdefault(KORLOY_STABLES, []).append(
                TravelConnection(KORLOY_STABLES, CASINO, edge.travel_ms, True, True, p)
            )

    @staticmethod
    def _initial_story_state() -> dict:
        return {
            "stage": "not_started",
            "nirrnir_actor_id": None,
            "poisoned_at_ms": None,
            "stabilized_at_ms": None,
            "deadline_ms": None,
            "human_blood_bridge_active": False,
            "human_blood_bridge_expires_at_ms": None,
            "human_blood_donor_actor_id": None,
            "human_blood_donor_cost_hp": None,
            "civis_actor_id": None,
            "cured_at_ms": None,
            "cure_blood_instance_id": None,
        }

    def _story(self) -> dict:
        return self.runtime.world.global_flags.setdefault(
            "floor7_nirrnir_poison_story",
            self._initial_story_state(),
        )

    def _story_view(self) -> dict:
        story = self.runtime.world.global_flags.get("floor7_nirrnir_poison_story")
        return story if story is not None else self._initial_story_state()

    def _raids(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor7_aghyellr_raids", {})

    def _create_nirrnir_actor(self) -> CombatantState:
        actor_id = f"questnpc_nirrnir_{uuid.uuid4().hex[:12]}"
        actor = CombatantState(
            actor_id=actor_id,
            name="Nirrnir Nachtoy",
            kind=EntityKind.NPC,
            level=30,
            max_hp=7200,
            hp=1800,
            strength=46,
            agility=62,
            armor=120,
            evasion=16,
            cursor=CursorColor.YELLOW,
            location_id=KORLOY_STABLES,
            metadata={
                "npc_definition_id": NIRRNIR_ID,
                "night_rank": DOMINUS_NOCTE,
                "dominus_nocte": True,
                "direct_sunlight_weakness": "lethal",
                "can_create_night_followers": True,
                "blood_feeding_restores_hp": True,
                "argent_serpent_silver_poison": True,
                "lobelia_stabilised_coma": True,
                "combat_stats_provenance": "simulation",
            },
        )
        actor.statuses.append(
            StatusEffectState(
                effect_id=f"argent_serpent_silver_poison:{actor_id}",
                status_type=StatusType.DEBUFF,
                source_id=None,
                remaining_ms=NIRRNIR_STABILIZED_SURVIVAL_MS,
                magnitude=1.0,
                tick_interval_ms=NIRRNIR_STABILIZED_SURVIVAL_MS,
                until_next_tick_ms=NIRRNIR_STABILIZED_SURVIVAL_MS,
                stack_key="argent_serpent_silver_poison",
                tags=("argent_serpent", "silver_poison", "dominus_nocte", "not_curable_by_ordinary_antidote"),
            )
        )
        self.runtime.actors[actor_id] = actor
        return actor

    def trigger_nirrnir_poisoning(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != KORLOY_STABLES:
            raise ValueError("Nirrnir's Argent Serpent poisoning occurs during the Korloy stable inspection")
        story = self._story()
        if story["stage"] != "not_started":
            raise ValueError("Nirrnir's Argent Serpent poisoning has already been triggered")
        nirrnir = self._create_nirrnir_actor()
        story.update(
            stage="stabilised_silver_poison",
            nirrnir_actor_id=nirrnir.actor_id,
            poisoned_at_ms=self.runtime.world.now_ms,
            stabilized_at_ms=self.runtime.world.now_ms,
            deadline_ms=self.runtime.world.now_ms + NIRRNIR_STABILIZED_SURVIVAL_MS,
        )
        return self.nirrnir_status()

    def _on_world_advance(self, before_ms: int, after_ms: int) -> None:
        story = self.runtime.world.global_flags.get("floor7_nirrnir_poison_story")
        if story is None or story["stage"] in {"not_started", "cured", "nirrnir_died_from_silver_poison"}:
            return
        actor_id = story["nirrnir_actor_id"]
        if actor_id not in self.runtime.actors:
            raise RuntimeError("Nirrnir poison story points to a missing actor")
        nirrnir = self.runtime.actors[actor_id]
        deadline = story["deadline_ms"]
        if deadline is None:
            raise RuntimeError("active Nirrnir poison story has no deadline")
        remaining = max(0, int(deadline) - after_ms)
        for status in nirrnir.statuses:
            if status.stack_key == "argent_serpent_silver_poison":
                status.remaining_ms = remaining
                status.until_next_tick_ms = min(status.until_next_tick_ms, max(1, remaining))

        if remaining <= 0:
            nirrnir.hp = 0
            nirrnir.alive = False
            nirrnir.metadata["human_blood_bridge_active"] = False
            story["stage"] = "nirrnir_died_from_silver_poison"
            story["human_blood_bridge_active"] = False
            story["died_at_ms"] = after_ms
            return

        if story["stage"] != "stabilised_silver_poison":
            return
        bridge_active = story["human_blood_bridge_active"]
        if bridge_active:
            expiry = story["human_blood_bridge_expires_at_ms"]
            if expiry is None:
                raise RuntimeError("active human-blood bridge has no expiry")
            if after_ms >= int(expiry):
                story["human_blood_bridge_active"] = False
                nirrnir.metadata["human_blood_bridge_active"] = False
                bridge_active = False

        if not bridge_active:
            remaining_ratio = remaining / NIRRNIR_STABILIZED_SURVIVAL_MS
            poison_cap = max(1, int(round(nirrnir.max_hp * 0.25 * remaining_ratio)))
            nirrnir.hp = min(nirrnir.hp, poison_cap)

    def _on_defeat(self, encounter, target, killer_id: str | None) -> None:
        raids = self.runtime.world.global_flags.get("floor7_aghyellr_raids", {})
        for state in raids.values():
            if state["stage"] == "battle" and state["boss_id"] == target.actor_id:
                state["stage"] = "aghyellr_defeated"

    def _validate_raid_world_time(self, state: dict) -> None:
        encounter_id = state["encounter_id"]
        encounter = self.runtime.encounters[encounter_id]
        expected_world_ms = self.runtime.encounter_world_time_ms(encounter_id)
        if self.runtime.world.now_ms < expected_world_ms:
            raise RuntimeError("Aghyellr encounter advanced beyond the authoritative world clock")
        if encounter.time_ms < 0:
            raise RuntimeError("Aghyellr encounter time moved before zero")

    def nirrnir_status(self) -> dict:
        story = self._story_view()
        if story["stage"] == "not_started":
            return {
                **story,
                "alive": None,
                "hp": None,
                "max_hp": None,
                "location_id": None,
                "remaining_ms": None,
                "ordinary_antidote_effective": None,
                "required_cure": None,
                "nightfolk": None,
            }
        actor = self.runtime.actors[story["nirrnir_actor_id"]]
        deadline = story["deadline_ms"]
        remaining = max(0, int(deadline) - self.runtime.world.now_ms)
        return {
            **story,
            "alive": actor.alive,
            "hp": actor.hp,
            "max_hp": actor.max_hp,
            "location_id": actor.location_id,
            "remaining_ms": remaining,
            "ordinary_antidote_effective": False,
            "required_cure": "fresh undiluted unpreserved dragon blood",
            "nightfolk": nightfolk_state(actor),
        }

    def start_aghyellr_raid(self, player_ids: list[str], *, bring_nirrnir: bool = True) -> dict:
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Aghyellr raid needs at least one player")
        story = self._story_view()
        nirrnir_id = story["nirrnir_actor_id"] if story["stage"] != "not_started" else None
        nirrnir_route = None
        if bring_nirrnir:
            if nirrnir_id is None:
                raise ValueError("Nirrnir poisoning must exist before she can be carried into the Aghyellr raid")
            nirrnir = self.runtime.actors[nirrnir_id]
            if not nirrnir.alive:
                raise ValueError("Nirrnir did not survive long enough to reach the Floor 7 Boss Room")
            stabilized_at_ms = story.get("stabilized_at_ms")
            if stabilized_at_ms is None:
                raise RuntimeError("Nirrnir poison story has no authoritative stabilization time")
            if nirrnir.location_id != BOSS_ROOM:
                nirrnir_route = complete_routed_travel_within_window(
                    self.runtime,
                    [nirrnir.actor_id],
                    BOSS_ROOM,
                    started_at_ms=int(stabilized_at_ms),
                    completed_at_ms=self.runtime.world.now_ms,
                )
            nirrnir.metadata["carried_to_aghyellr_raid"] = True

        encounter, boss = self.runtime.start_floor_boss_encounter(
            players,
            boss_definition_id=AGHYELLR_ID,
        )
        if bring_nirrnir:
            nirrnir = self.runtime.actors[nirrnir_id]
            if nirrnir.location_id != BOSS_ROOM:
                raise RuntimeError("Nirrnir movement authority did not reach the Aghyellr Boss Room")
            self.runtime.add_encounter_participant(
                encounter.encounter_id, nirrnir.actor_id, position=(-8.0, 0.0)
            )

        instance_id = f"aghyellr7_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "encounter_id": encounter.encounter_id,
            "boss_id": boss.actor_id,
            "player_ids": players,
            "stage": "battle",
            "pending_gaze": None,
            "nirrnir_actor_id": nirrnir_id if bring_nirrnir else None,
            "nirrnir_raid_route": routed_travel_window_record(nirrnir_route) if nirrnir_route else None,
            "civis_actor_ids": [],
            "doleful_nocturne_revealed_instance_ids": [],
            "blood_jar_instance_ids": [],
            "blood_jars_total": AGHYELLR_BLOOD_JAR_COUNT,
            "blood_jars_collected": 0,
            "started_at_ms": self.runtime.world.now_ms,
        }
        self._raids()[instance_id] = state
        return self.raid_status(instance_id)

    def sustain_nirrnir_with_human_blood(self, instance_id: str, donor_actor_id: str) -> dict:
        state = self._raids()[instance_id]
        self._validate_raid_world_time(state)
        if state["stage"] != "battle":
            raise ValueError("the human-blood bridge is a last-resort action during the Aghyellr battle")
        story = self._story()
        if story["stage"] != "stabilised_silver_poison":
            raise ValueError("Nirrnir is not in the treatable silver-poison state")
        if state["nirrnir_actor_id"] != story["nirrnir_actor_id"]:
            raise RuntimeError("Aghyellr raid is not carrying the poisoned Nirrnir from the active story")
        encounter = self.runtime.encounters[state["encounter_id"]]
        if donor_actor_id not in state["player_ids"] or donor_actor_id not in encounter.participants:
            raise ValueError("blood donor must be a player participant in this Aghyellr raid")
        donor = self.runtime.actors[donor_actor_id]
        nirrnir = self.runtime.actors[story["nirrnir_actor_id"]]
        if not donor.alive or not nirrnir.alive:
            raise ValueError("both donor and Nirrnir must be alive")
        if night_rank(donor) is not None:
            raise ValueError("the human-blood bridge expects a non-Night player donor")
        critical_hp = max(1, int(round(nirrnir.max_hp * 0.05)))
        if nirrnir.hp > critical_hp:
            raise ValueError("Nirrnir has not yet fallen to the critical last-resort HP range")

        donor_cost = int(math.ceil(donor.max_hp * HUMAN_BLOOD_DONOR_MAX_HP_RATIO))
        if donor.hp <= donor_cost:
            raise ValueError("the donor lacks enough current HP to survive the required blood loss")
        donor.hp -= donor_cost
        nirrnir.hp = max(nirrnir.hp, int(round(nirrnir.max_hp * HUMAN_BLOOD_BRIDGE_HP_RATIO)))
        story["human_blood_bridge_active"] = True
        story["human_blood_bridge_expires_at_ms"] = self.runtime.world.now_ms + HUMAN_BLOOD_BRIDGE_MS
        story["human_blood_donor_actor_id"] = donor_actor_id
        story["human_blood_donor_cost_hp"] = donor_cost
        story["civis_actor_id"] = donor_actor_id
        nirrnir.metadata["human_blood_bridge_active"] = True
        nirrnir.metadata["human_blood_donor_actor_id"] = donor_actor_id

        transformation = become_civis_nocte(
            donor,
            master_actor_id=nirrnir.actor_id,
            now_ms=self.runtime.world.now_ms,
        )
        state["civis_actor_ids"].append(donor_actor_id)
        self.runtime._append(
            encounter,
            "nirrnir_human_blood_bridge",
            donor_actor_id,
            nirrnir.actor_id,
            donor_hp_cost=donor_cost,
            donor_hp_after=donor.hp,
            nirrnir_hp_after=nirrnir.hp,
            bridge_expires_at_ms=story["human_blood_bridge_expires_at_ms"],
            night_rank=transformation.combat_bonus and CIVIS_NOCTE,
        )
        return {
            "instance_id": instance_id,
            "donor_actor_id": donor_actor_id,
            "donor_hp_cost": donor_cost,
            "donor_hp_after": donor.hp,
            "transformation": nightfolk_state(donor),
            "state": self.raid_status(instance_id),
        }

    def reveal_doleful_nocturne(self, instance_id: str, actor_id: str, sword_instance_id: str) -> dict:
        state = self._raids()[instance_id]
        self._validate_raid_world_time(state)
        if actor_id not in state["player_ids"]:
            raise ValueError("Doleful Nocturne revealer must be an Aghyellr raid player")
        actor = self.runtime.actors[actor_id]
        if night_rank(actor) != CIVIS_NOCTE:
            raise ValueError("the sealed Sword of Volupta identity is revealed here by a Civis Nocte wielder")
        sword = actor.inventory[sword_instance_id]
        if sword.template_id != SWORD_OF_VOLUPTA_ID:
            raise ValueError("item is not the Sword of Volupta")
        if actor.equipment.get("weapon") != sword_instance_id:
            raise ValueError("the Sword of Volupta must be equipped to reveal its combat identity")
        if sword_instance_id in state["doleful_nocturne_revealed_instance_ids"]:
            raise ValueError("this Sword of Volupta instance has already revealed its true identity")

        sword.metadata.update(
            {
                "true_identity_revealed": True,
                "true_name": "Doleful Nocturne",
                "revealed_by_civis_nocte_actor_id": actor_id,
                "revealed_at_ms": self.runtime.world.now_ms,
            }
        )
        state["doleful_nocturne_revealed_instance_ids"].append(sword_instance_id)
        self.runtime._append(
            self.runtime.encounters[state["encounter_id"]],
            "doleful_nocturne_revealed",
            actor_id,
            actor_id,
            sword_instance_id=sword_instance_id,
            true_name="Doleful Nocturne",
        )
        template = self.runtime.catalog.weapons[SWORD_OF_VOLUPTA_ID]
        return {
            "instance_id": instance_id,
            "actor_id": actor_id,
            "sword_instance_id": sword_instance_id,
            "true_name": sword.metadata["true_name"],
            "effects": sorted(template.tags),
            "nightfolk": nightfolk_state(actor),
        }

    def telegraph_intimidating_gaze(self, instance_id: str) -> dict:
        state = self._raids()[instance_id]
        self._validate_raid_world_time(state)
        boss = self.runtime.actors[state["boss_id"]]
        if not boss.alive or state["stage"] != "battle":
            raise ValueError("Aghyellr is not in an active battle state")
        encounter = self.runtime.encounters[state["encounter_id"]]
        if state["pending_gaze"] is not None:
            raise ValueError("Intimidating Gaze is already telegraphed")
        pending = {
            "telegraphed_at_ms": encounter.time_ms,
            "resolve_at_ms": encounter.time_ms + GAZE_TELEGRAPH_MS,
        }
        state["pending_gaze"] = pending
        self.runtime._append(
            encounter,
            "aghyellr_intimidating_gaze_telegraph",
            boss.actor_id,
            None,
            resolve_at_ms=pending["resolve_at_ms"],
            visual="wings spread; eyes turn red",
        )
        return self.raid_status(instance_id)

    def resolve_intimidating_gaze(self, instance_id: str, *, look_away_actor_ids: list[str] | None = None) -> dict:
        state = self._raids()[instance_id]
        self._validate_raid_world_time(state)
        pending = state["pending_gaze"]
        if pending is None:
            raise ValueError("Intimidating Gaze has not been telegraphed")
        encounter = self.runtime.encounters[state["encounter_id"]]
        remaining = max(0, int(pending["resolve_at_ms"]) - encounter.time_ms)
        if remaining:
            self.runtime.advance_encounter(encounter.encounter_id, remaining)
            self._validate_raid_world_time(state)
        looking_away = set(look_away_actor_ids or ())
        stunned: list[str] = []
        unaffected: list[str] = []
        for actor_id in state["player_ids"]:
            actor = encounter.participants[actor_id]
            if not actor.alive or actor_id in looking_away:
                continue
            if actor.level < 20:
                actor.statuses = [status for status in actor.statuses if status.stack_key != "aghyellr_intimidating_gaze"]
                actor.statuses.append(
                    StatusEffectState(
                        effect_id=f"aghyellr_gaze:{actor_id}:{encounter.time_ms}",
                        status_type=StatusType.STUN,
                        source_id=state["boss_id"],
                        remaining_ms=GAZE_STUN_MS,
                        magnitude=1.0,
                        tick_interval_ms=GAZE_STUN_MS,
                        until_next_tick_ms=GAZE_STUN_MS,
                        stack_key="aghyellr_intimidating_gaze",
                        tags=("aghyellr", "intimidating_gaze", "under_level_20"),
                    )
                )
                stunned.append(actor_id)
            else:
                unaffected.append(actor_id)
        state["pending_gaze"] = None
        self.runtime._append(
            encounter,
            "aghyellr_intimidating_gaze_resolved",
            state["boss_id"],
            None,
            look_away_actor_ids=sorted(looking_away),
            stunned_actor_ids=stunned,
            level_20_plus_unaffected_actor_ids=unaffected,
        )
        return {
            "instance_id": instance_id,
            "stunned_actor_ids": stunned,
            "look_away_actor_ids": sorted(looking_away),
            "level_20_plus_unaffected_actor_ids": unaffected,
            "state": self.raid_status(instance_id),
        }

    def collect_fresh_dragon_blood(self, instance_id: str, actor_id: str) -> dict:
        state = self._raids()[instance_id]
        self._validate_raid_world_time(state)
        boss = self.runtime.actors[state["boss_id"]]
        encounter = self.runtime.encounters[state["encounter_id"]]
        if boss.alive:
            raise ValueError("Aghyellr must be defeated before its dragon-blood drop can be collected")
        if actor_id not in encounter.participants or not encounter.participants[actor_id].alive:
            raise ValueError("blood collector must be a living raid participant")
        if state["blood_jars_collected"] != 0:
            raise ValueError("Aghyellr's dragon-blood drop has already been collected")
        actor = self.runtime.actors[actor_id]
        ids: list[str] = []
        for index in range(AGHYELLR_BLOOD_JAR_COUNT):
            item = ItemInstance(
                instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
                template_id=FRESH_AGHYELLR_BLOOD_ID,
                owner_id=actor_id,
                metadata={
                    "collected_from_boss_id": boss.actor_id,
                    "drop_jar_index": index + 1,
                    "drop_jar_count": AGHYELLR_BLOOD_JAR_COUNT,
                    "collected_at_ms": self.runtime.world.now_ms,
                    "fresh_until_ms": self.runtime.world.now_ms + FRESH_DRAGON_BLOOD_WINDOW_MS,
                    "freshness_window_provenance": "simulation",
                    "diluted": False,
                    "preserved": False,
                },
            )
            add_item(actor, item, self.runtime.catalog, allow_overweight=True)
            ids.append(item.instance_id)
        state["blood_jar_instance_ids"] = ids
        state["blood_jars_collected"] = len(ids)
        state["stage"] = "dragon_blood_collected"
        return {
            "instance_id": instance_id,
            "blood_instance_ids": list(ids),
            "blood_jars_collected": len(ids),
            "fresh_until_ms": self.runtime.actors[actor_id].inventory[ids[0]].metadata["fresh_until_ms"],
            "state": self.raid_status(instance_id),
        }

    def administer_dragon_blood(self, instance_id: str, actor_id: str, blood_instance_id: str) -> dict:
        state = self._raids()[instance_id]
        self._validate_raid_world_time(state)
        story = self._story()
        if story["stage"] != "stabilised_silver_poison":
            raise ValueError("Nirrnir is not in the treatable Argent Serpent poisoning state")
        if state["nirrnir_actor_id"] != story["nirrnir_actor_id"]:
            raise RuntimeError("Aghyellr raid and Nirrnir poison story point to different Nirrnir actors")
        if blood_instance_id not in state["blood_jar_instance_ids"]:
            raise ValueError("blood instance is not part of this Aghyellr raid's seventeen-jar drop")
        actor = self.runtime.actors[actor_id]
        item = actor.inventory[blood_instance_id]
        if item.template_id != FRESH_AGHYELLR_BLOOD_ID:
            raise RuntimeError("recorded Aghyellr blood instance has the wrong item template")
        if item.metadata["diluted"] or item.metadata["preserved"]:
            raise ValueError("Nirrnir requires fresh, undiluted, unpreserved dragon blood")
        if self.runtime.world.now_ms > int(item.metadata["fresh_until_ms"]):
            raise ValueError("the collected dragon blood is no longer fresh enough for this runtime cure")
        nirrnir = self.runtime.actors[story["nirrnir_actor_id"]]
        if actor.location_id != nirrnir.location_id:
            raise ValueError("the blood carrier must be with Nirrnir to administer the cure")

        actor.inventory.pop(item.instance_id)
        item.owner_id = None
        item.metadata["consumed_to_cure_nirrnir"] = True
        nirrnir.statuses = [status for status in nirrnir.statuses if status.stack_key != "argent_serpent_silver_poison"]
        nirrnir.metadata["argent_serpent_silver_poison"] = False
        nirrnir.metadata["lobelia_stabilised_coma"] = False
        nirrnir.metadata["human_blood_bridge_active"] = False
        nirrnir.metadata["cured_by_fresh_dragon_blood"] = True
        nirrnir.hp = nirrnir.max_hp
        nirrnir.alive = True
        story["stage"] = "cured"
        story["human_blood_bridge_active"] = False
        story["cured_at_ms"] = self.runtime.world.now_ms
        story["cure_blood_instance_id"] = blood_instance_id
        return self.nirrnir_status()

    def raid_status(self, instance_id: str) -> dict:
        state = self._raids()[instance_id]
        self._validate_raid_world_time(state)
        boss = self.runtime.actors[state["boss_id"]]
        return {
            **state,
            "boss": self.runtime.boss_bar_state(boss),
            "boss_alive": boss.alive,
            "nirrnir": self.nirrnir_status(),
            "civis_states": {
                actor_id: nightfolk_state(self.runtime.actors[actor_id])
                for actor_id in state["civis_actor_ids"]
            },
            "blood_jars_remaining_in_campaign": sum(
                1
                for blood_id in state["blood_jar_instance_ids"]
                if any(blood_id in actor.inventory for actor in self.runtime.actors.values())
            ),
        }


def install_floor7_aghyellr_scenario(runtime) -> Floor7AghyellrScenario:
    if AGHYELLR_ID not in __import__("sao_mcp.corpus.bosses", fromlist=["CORE_BOSSES"]).CORE_BOSSES:
        raise RuntimeError("Aghyellr boss corpus was not loaded")
    return Floor7AghyellrScenario(runtime)

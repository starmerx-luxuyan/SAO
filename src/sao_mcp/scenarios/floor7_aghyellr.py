from __future__ import annotations

import uuid

from sao_mcp.corpus.floor7 import AGHYELLR_ID, NIRRNIR_ID
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
from sao_mcp.rules.inventory import add_item


CASINO = "floor_7_volupta_grand_casino"
KORLOY_STABLES = "floor_7_korloy_monster_stables"
BOSS_ROOM = "floor_7_boss_room"

NIRRNIR_STABILIZED_SURVIVAL_MS = 48 * 60 * 60 * 1000
GAZE_TELEGRAPH_MS = 1500
GAZE_STUN_MS = 5000  # Simulation duration; under-Level-20 immediate stun is canon.
FRESH_DRAGON_BLOOD_WINDOW_MS = 30 * 60 * 1000  # Simulation definition of 'fresh' for the runtime item.


class Floor7AghyellrScenario:
    """Argent Serpent poisoning, time-critical Aghyellr raid, Intimidating Gaze and fresh dragon-blood cure."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        apply_floor7_nirrnir_corpus(runtime.catalog)
        self._seed_world()

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

    def _story(self) -> dict:
        return self.runtime.world.global_flags.setdefault(
            "floor7_nirrnir_poison_story",
            {
                "stage": "not_started",
                "nirrnir_actor_id": None,
                "poisoned_at_ms": None,
                "stabilized_at_ms": None,
                "deadline_ms": None,
                "cured_at_ms": None,
                "cure_blood_instance_id": None,
            },
        )

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
                "dominus_nocte": True,
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
            return self.nirrnir_status()
        nirrnir = self._create_nirrnir_actor()
        story.update(
            stage="stabilised_silver_poison",
            nirrnir_actor_id=nirrnir.actor_id,
            poisoned_at_ms=self.runtime.world.now_ms,
            stabilized_at_ms=self.runtime.world.now_ms,
            deadline_ms=self.runtime.world.now_ms + NIRRNIR_STABILIZED_SURVIVAL_MS,
        )
        return self.nirrnir_status()

    def _sync_nirrnir(self) -> None:
        story = self._story()
        actor_id = story.get("nirrnir_actor_id")
        if not actor_id or actor_id not in self.runtime.actors:
            return
        nirrnir = self.runtime.actors[actor_id]
        if story["stage"] == "cured":
            return
        deadline = story.get("deadline_ms")
        if deadline is None:
            return
        remaining = max(0, int(deadline) - self.runtime.world.now_ms)
        for status in nirrnir.statuses:
            if status.stack_key == "argent_serpent_silver_poison":
                status.remaining_ms = remaining
                status.until_next_tick_ms = min(status.until_next_tick_ms, max(1, remaining))
        if remaining <= 0:
            nirrnir.hp = 0
            nirrnir.alive = False
            story["stage"] = "nirrnir_died_from_silver_poison"
            story["died_at_ms"] = self.runtime.world.now_ms

    def nirrnir_status(self) -> dict:
        self._sync_nirrnir()
        story = self._story()
        actor_id = story.get("nirrnir_actor_id")
        actor = self.runtime.actors.get(actor_id) if actor_id else None
        deadline = story.get("deadline_ms")
        remaining = max(0, int(deadline) - self.runtime.world.now_ms) if deadline is not None else None
        return {
            **story,
            "alive": actor.alive if actor else None,
            "hp": actor.hp if actor else None,
            "max_hp": actor.max_hp if actor else None,
            "location_id": actor.location_id if actor else None,
            "remaining_ms": remaining,
            "ordinary_antidote_effective": False if actor else None,
            "required_cure": "fresh undiluted unpreserved dragon blood" if actor else None,
        }

    def start_aghyellr_raid(self, player_ids: list[str], *, bring_nirrnir: bool = True) -> dict:
        self._sync_nirrnir()
        players = list(dict.fromkeys(player_ids))
        if not players:
            raise ValueError("Aghyellr raid needs at least one player")
        encounter, boss = self.runtime.start_floor_boss_encounter(
            players,
            boss_definition_id=AGHYELLR_ID,
        )
        story = self._story()
        nirrnir_id = story.get("nirrnir_actor_id")
        if bring_nirrnir and nirrnir_id:
            nirrnir = self.runtime.actors[nirrnir_id]
            if not nirrnir.alive:
                raise ValueError("Nirrnir did not survive long enough to reach the Floor 7 Boss Room")
            nirrnir.location_id = BOSS_ROOM
            encounter.participants[nirrnir.actor_id] = nirrnir
            encounter.positions[nirrnir.actor_id] = (-8.0, 0.0)
            nirrnir.metadata["carried_to_aghyellr_raid"] = True

        instance_id = f"aghyellr7_{uuid.uuid4().hex[:12]}"
        state = {
            "instance_id": instance_id,
            "encounter_id": encounter.encounter_id,
            "boss_id": boss.actor_id,
            "player_ids": players,
            "stage": "battle",
            "pending_gaze": None,
            "nirrnir_actor_id": nirrnir_id if bring_nirrnir else None,
            "blood_instance_id": None,
            "started_at_ms": self.runtime.world.now_ms,
        }
        self._raids()[instance_id] = state
        return self.raid_status(instance_id)

    def telegraph_intimidating_gaze(self, instance_id: str) -> dict:
        state = self._raids()[instance_id]
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
        pending = state.get("pending_gaze")
        if pending is None:
            raise ValueError("Intimidating Gaze has not been telegraphed")
        encounter = self.runtime.encounters[state["encounter_id"]]
        remaining = max(0, int(pending["resolve_at_ms"]) - encounter.time_ms)
        if remaining:
            self.runtime.advance_encounter(encounter.encounter_id, remaining)
            self.runtime.advance_world(remaining)
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
        boss = self.runtime.actors[state["boss_id"]]
        encounter = self.runtime.encounters[state["encounter_id"]]
        if boss.alive:
            raise ValueError("Aghyellr must be defeated before fresh dragon blood can be collected")
        if actor_id not in encounter.participants or not encounter.participants[actor_id].alive:
            raise ValueError("blood collector must be a living raid participant")
        if state["blood_instance_id"] is not None:
            raise ValueError("fresh dragon blood has already been collected from this boss")
        actor = self.runtime.actors[actor_id]
        item = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=FRESH_AGHYELLR_BLOOD_ID,
            owner_id=actor_id,
            metadata={
                "collected_from_boss_id": boss.actor_id,
                "collected_at_ms": self.runtime.world.now_ms,
                "fresh_until_ms": self.runtime.world.now_ms + FRESH_DRAGON_BLOOD_WINDOW_MS,
                "freshness_window_provenance": "simulation",
                "diluted": False,
                "preserved": False,
            },
        )
        add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        state["blood_instance_id"] = item.instance_id
        state["stage"] = "dragon_blood_collected"
        return {
            "instance_id": instance_id,
            "blood_instance_id": item.instance_id,
            "fresh_until_ms": item.metadata["fresh_until_ms"],
            "state": self.raid_status(instance_id),
        }

    def administer_dragon_blood(self, actor_id: str, blood_instance_id: str) -> dict:
        self._sync_nirrnir()
        story = self._story()
        if story["stage"] != "stabilised_silver_poison":
            raise ValueError("Nirrnir is not in the treatable Argent Serpent poisoning state")
        actor = self.runtime.actors[actor_id]
        item = actor.inventory[blood_instance_id]
        if item.template_id != FRESH_AGHYELLR_BLOOD_ID:
            raise ValueError("item is not fresh Aghyellr dragon blood")
        if item.metadata.get("diluted") or item.metadata.get("preserved"):
            raise ValueError("Nirrnir requires fresh, undiluted, unpreserved dragon blood")
        if self.runtime.world.now_ms > int(item.metadata.get("fresh_until_ms", -1)):
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
        nirrnir.metadata["cured_by_fresh_dragon_blood"] = True
        nirrnir.hp = nirrnir.max_hp
        nirrnir.alive = True
        story["stage"] = "cured"
        story["cured_at_ms"] = self.runtime.world.now_ms
        story["cure_blood_instance_id"] = blood_instance_id
        return self.nirrnir_status()

    def raid_status(self, instance_id: str) -> dict:
        state = self._raids()[instance_id]
        boss = self.runtime.actors[state["boss_id"]]
        if not boss.alive and state["stage"] == "battle":
            state["stage"] = "aghyellr_defeated"
        return {
            **state,
            "boss": self.runtime.boss_bar_state(boss),
            "boss_alive": boss.alive,
            "nirrnir": self.nirrnir_status(),
        }


def install_floor7_aghyellr_scenario(runtime) -> Floor7AghyellrScenario:
    if AGHYELLR_ID not in __import__("sao_mcp.corpus.bosses", fromlist=["CORE_BOSSES"]).CORE_BOSSES:
        raise RuntimeError("Aghyellr boss corpus was not loaded")
    return Floor7AghyellrScenario(runtime)

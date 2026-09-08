from __future__ import annotations

import uuid

from sao_mcp.corpus.floor6 import apply_floor6_world_seed
from sao_mcp.corpus.floor6_stachion import (
    CYLON_ID,
    GOLDEN_KEY_ID,
    QUEST_ID,
    WITNESSES,
)
from sao_mcp.corpus.world import LocationDefinition, TravelConnection
from sao_mcp.domain.models import ItemInstance, Provenance, ProvenanceKind, ZoneKind
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.quests import QuestObjectiveKind


STACHION = "floor_6_stachion"
PUZZLE_QUARTER = "floor_6_stachion_puzzle_quarter"
CYLON_MANOR = "floor_6_cylon_lord_manor"
TRAVELLER_GRAVE = "floor_6_traveller_grave"
SURIBUS = "floor_6_suribus"
PITHAGRUS_HOUSE = "floor_6_pithagrus_suribus_house"
HOUSE_SEARCH_MS = 75 * 60_000  # Simulation abstraction for exploring the haunted/puzzle-filled second house.


class Floor6StachionScenario:
    """Release-side opening of Curse of Stachion, stopping at acquisition of Pithagrus's golden key."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        apply_floor6_world_seed(runtime.world_map)
        self._seed_world()

    def _seed_world(self) -> None:
        source = "Sword Art Online Progressive Volume 5: Canon of the Golden Rule (Start)"
        locations = {
            CYLON_MANOR: LocationDefinition(
                CYLON_MANOR,
                6,
                "Cylon's Lord Manor",
                ZoneKind.SAFE_TOWN,
                safe_zone=True,
                provenance=Provenance(
                    ProvenanceKind.CANON_INFERRED,
                    sources=(source,),
                    notes="Stachion lord's manor where Cylon gives Curse of Stachion; exact building geometry is abstracted.",
                ),
            ),
            TRAVELLER_GRAVE: LocationDefinition(
                TRAVELLER_GRAVE,
                6,
                "Traveller's Grave",
                ZoneKind.SAFE_TOWN,
                safe_zone=True,
                provenance=Provenance(
                    ProvenanceKind.CANON_INFERRED,
                    sources=(source,),
                    notes="Grave where Cylon asks the players to offer the missing golden cube. Exact city placement is abstracted.",
                ),
            ),
        }
        for location_id, location in locations.items():
            self.runtime.world_map.locations.setdefault(location_id, location)

        p = Provenance(
            ProvenanceKind.SIMULATION,
            sources=(source,),
            notes="In-city travel durations are simulation; endpoint identities/relationships are canon-backed.",
        )
        edges = (
            TravelConnection(STACHION, CYLON_MANOR, 4 * 60_000, provenance=p),
            TravelConnection(STACHION, TRAVELLER_GRAVE, 5 * 60_000, provenance=p),
            TravelConnection(PUZZLE_QUARTER, CYLON_MANOR, 3 * 60_000, provenance=p),
        )
        existing = {(edge.from_location_id, edge.to_location_id) for edge in self.runtime.world_map.connections}
        for edge in edges:
            if (edge.from_location_id, edge.to_location_id) in existing:
                continue
            self.runtime.world_map.connections = tuple(self.runtime.world_map.connections) + (edge,)
            self.runtime.world_map.adjacency.setdefault(edge.from_location_id, []).append(edge)
            if edge.bidirectional:
                self.runtime.world_map.adjacency.setdefault(edge.to_location_id, []).append(
                    TravelConnection(
                        edge.to_location_id,
                        edge.from_location_id,
                        edge.travel_ms,
                        True,
                        edge.requires_floor_unlocked,
                        edge.provenance,
                    )
                )

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor6_stachion_quest_states", {})

    def _state(self, actor_id: str) -> dict:
        try:
            return self._states()[actor_id]
        except KeyError as exc:
            raise ValueError("Curse of Stachion has not been started") from exc

    def _active_progress(self, actor_id: str):
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        if progress is None or progress.claimed:
            raise ValueError("Curse of Stachion must be active")
        return progress

    def start_quest(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != CYLON_MANOR:
            raise ValueError("Curse of Stachion begins with Cylon at the Stachion lord's manor")
        self.runtime.accept_quest(actor_id, QUEST_ID)
        self._states().setdefault(
            actor_id,
            {
                "actor_id": actor_id,
                "stage": "interview_old_associates",
                "started_at_ms": self.runtime.world.now_ms,
                "witnesses_interviewed": [],
                "suribus_house_revealed_at_ms": None,
                "golden_key_obtained_at_ms": None,
                "capture_event_started": False,
            },
        )
        return self.status(actor_id)

    def interview_witness(self, actor_id: str, witness_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        if actor.location_id != PUZZLE_QUARTER:
            raise ValueError("Pithagrus's former associates are interviewed in Stachion's puzzle-heavy town area")
        if witness_id not in WITNESSES:
            raise KeyError(witness_id)
        self.runtime.interact_npc(actor_id, witness_id)

        interviewed = state["witnesses_interviewed"]
        if witness_id not in interviewed:
            interviewed.append(witness_id)
            self.runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id="stachion_old_household_testimony",
            )

        if len(interviewed) == len(WITNESSES) and state["suribus_house_revealed_at_ms"] is None:
            state["stage"] = "travel_to_suribus_second_home"
            state["suribus_house_revealed_at_ms"] = self.runtime.world.now_ms
            self.runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.DISCOVER,
                target_id="pithagrus_suribus_house_discovered",
            )
        return self.status(actor_id)

    def search_pithagrus_house(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        if actor.location_id != PITHAGRUS_HOUSE:
            raise ValueError("the golden key is found at Pithagrus's second home in Suribus")
        if len(state["witnesses_interviewed"]) < len(WITNESSES):
            raise ValueError("the Stachion interviews have not yet revealed Pithagrus's Suribus house")

        existing = next(
            (item for item in actor.inventory.values() if item.template_id == GOLDEN_KEY_ID),
            None,
        )
        if existing is None:
            self.runtime.advance_world(HOUSE_SEARCH_MS)
            existing = ItemInstance(
                instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
                template_id=GOLDEN_KEY_ID,
                owner_id=actor_id,
                quantity=1,
            )
            add_item(actor, existing, self.runtime.catalog, allow_overweight=True)
            self.runtime.quests.record_event(
                actor_id,
                kind=QuestObjectiveKind.COLLECT,
                target_id=GOLDEN_KEY_ID,
            )
            state["golden_key_obtained_at_ms"] = self.runtime.world.now_ms
        state["stage"] = "golden_key_obtained_capture_pending"
        return self.status(actor_id)

    def status(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        actor = self.runtime.actors[actor_id]
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        has_key = any(item.template_id == GOLDEN_KEY_ID for item in actor.inventory.values())
        return {
            **state,
            "witness_count": len(state["witnesses_interviewed"]),
            "witness_total": len(WITNESSES),
            "has_golden_key": has_key,
            "quest_progress": dict(progress.counters) if progress else None,
            "ready_to_claim": self.runtime.quests.ready_to_claim(actor, QUEST_ID) if progress else False,
            "next_canon_stage": "compulsory Cylon capture event" if has_key else None,
        }


def install_floor6_stachion_scenario(runtime) -> Floor6StachionScenario:
    if QUEST_ID not in runtime.quests.definitions:
        raise RuntimeError("Curse of Stachion corpus was not loaded")
    if CYLON_ID not in runtime.npcs.definitions:
        raise RuntimeError("Cylon NPC corpus was not loaded")
    if GOLDEN_KEY_ID not in runtime.catalog.items:
        raise RuntimeError("Floor 6 golden key corpus was not loaded")
    return Floor6StachionScenario(runtime)

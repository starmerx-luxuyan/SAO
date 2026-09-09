from __future__ import annotations

from dataclasses import dataclass, field

from sao_mcp.domain.models import Provenance, ProvenanceKind
from sao_mcp.rules.quests import QuestRuntime


@dataclass(slots=True, frozen=True)
class NPCDefinition:
    npc_id: str
    name: str
    home_location_id: str
    roles: tuple[str, ...] = ()
    quest_ids: tuple[str, ...] = ()
    knowledge_tags: tuple[str, ...] = ()
    provenance: Provenance = Provenance(ProvenanceKind.SIMULATION)


@dataclass(slots=True)
class NPCState:
    npc_id: str
    location_id: str
    relationship_by_actor: dict[str, int] = field(default_factory=dict)
    flags: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class NPCInteraction:
    npc_id: str
    name: str
    location_id: str
    roles: tuple[str, ...]
    available_quests: tuple[str, ...]
    relationship: int
    knowledge_tags: tuple[str, ...]


CORE_NPCS: dict[str, NPCDefinition] = {
    "npc_horunka_mother": NPCDefinition(
        npc_id="npc_horunka_mother",
        name="Horunka Village Mother",
        home_location_id="floor_1_horunka",
        roles=("resident", "quest_giver"),
        quest_ids=("secret_medicine_of_the_forest",),
        knowledge_tags=("horunka", "forest_medicine", "little_nepenthes"),
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=("Sword Art Online Volume 8: First Day",),
            notes="NPC role and family circumstance are canon; generic English display name avoids inventing a personal name.",
        ),
    ),
    "npc_tutorial_instructor": NPCDefinition(
        npc_id="npc_tutorial_instructor",
        name="Field Instructor",
        home_location_id="floor_1_town_of_beginnings",
        roles=("tutorial", "quest_giver"),
        quest_ids=("field_combat_orientation",),
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            notes="Runtime tutorial NPC; not an SAO canon character.",
        ),
    ),
    "pc_lisbeth": NPCDefinition(
        npc_id="pc_lisbeth",
        name="Lisbeth",
        home_location_id="floor_48_lisbeth_smith_shop",
        roles=("named_player", "blacksmith", "armorer", "shop_owner", "repair_service"),
        knowledge_tags=("lindarth", "blacksmithing", "weapon_creation", "enhancement", "repair"),
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 2: Warmth of the Heart",),
            notes="Named player blacksmith and owner of a smith/armour shop in Lindarth on Floor 48.",
        ),
    ),
    "pc_agil": NPCDefinition(
        npc_id="pc_agil",
        name="Agil",
        home_location_id="floor_50_agil_shop",
        roles=("named_player", "merchant", "shop_owner", "item_trader"),
        knowledge_tags=("algade", "trade", "market_prices", "weapons", "materials", "food_ingredients"),
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Volume 1, Chapter 5",),
            notes="Named player merchant and owner of an item shop in Algade on Floor 50.",
        ),
    ),
}


class NPCRuntime:
    def __init__(self, definitions: dict[str, NPCDefinition] | None = None) -> None:
        self.definitions = definitions or CORE_NPCS
        self.states = {
            npc_id: NPCState(npc_id, definition.home_location_id)
            for npc_id, definition in self.definitions.items()
        }

    def interact(
        self,
        actor_id: str,
        npc_id: str,
        *,
        actor_location_id: str | None,
        now_ms: int,
        quests: QuestRuntime,
    ) -> NPCInteraction:
        return self.interact_at(
            actor_id,
            npc_id,
            actor_location_id=actor_location_id,
            npc_location_id=self.states[npc_id].location_id,
            now_ms=now_ms,
            quests=quests,
        )

    def interact_at(
        self,
        actor_id: str,
        npc_id: str,
        *,
        actor_location_id: str | None,
        npc_location_id: str,
        now_ms: int,
        quests: QuestRuntime,
    ) -> NPCInteraction:
        definition = self.definitions[npc_id]
        state = self.states[npc_id]
        if actor_location_id != npc_location_id:
            raise ValueError("actor and NPC are not at the same location")
        completed = quests.completed_by_actor.get(actor_id, set())
        active = quests.progress_by_actor.get(actor_id, {})
        available: list[str] = []
        for quest_id in definition.quest_ids:
            quest = quests.definitions[quest_id]
            if any(required not in completed for required in quest.prerequisites):
                continue
            if quest_id in active and not active[quest_id].claimed:
                available.append(quest_id)
                continue
            if quest_id in completed and not quest.repeatable:
                continue
            if now_ms < quests.global_accept_block_until_ms.get(quest_id, 0):
                continue
            available.append(quest_id)
        return NPCInteraction(
            npc_id=npc_id,
            name=definition.name,
            location_id=npc_location_id,
            roles=definition.roles,
            available_quests=tuple(available),
            relationship=state.relationship_by_actor.get(actor_id, 0),
            knowledge_tags=definition.knowledge_tags,
        )

    def adjust_relationship(self, actor_id: str, npc_id: str, delta: int) -> int:
        state = self.states[npc_id]
        updated = max(-1000, min(1000, state.relationship_by_actor.get(actor_id, 0) + delta))
        state.relationship_by_actor[actor_id] = updated
        return updated

    def dump_state(self) -> dict:
        return {
            npc_id: {
                "location_id": state.location_id,
                "relationship_by_actor": dict(state.relationship_by_actor),
                "flags": dict(state.flags),
            }
            for npc_id, state in self.states.items()
        }

    def load_state(self, payload: dict) -> None:
        for npc_id, value in payload.items():
            if npc_id not in self.states:
                continue
            state = self.states[npc_id]
            state.location_id = value.get("location_id", state.location_id)
            state.relationship_by_actor = {
                actor_id: int(score)
                for actor_id, score in value.get("relationship_by_actor", {}).items()
            }
            state.flags = dict(value.get("flags", {}))

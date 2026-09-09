from __future__ import annotations

import uuid
from dataclasses import asdict

from sao_mcp.corpus.floor4 import (
    GONDOLA_TARGET,
    OPTIONAL_RAM_MATERIAL,
    PREMIUM_MATERIALS,
    QUEST_ID,
    ROMOLO_ID,
    SECRET_TARGET,
    SHIPWRIGHT_GONDOLA_TRANSPORTS,
    STANDARD_MATERIALS,
    WATER_CARRIER_HIDDEN_TRANSPORT,
    YOFILIS_ID,
)
from sao_mcp.corpus.loot import CORE_LOOT_TABLES
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS, AINCRAD_MONSTER_LOOT_TABLES
from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.transport import authorized_transport, authorized_transport_record


ROVIA = "floor_4_rovia"
BEAR_FOREST = "floor_4_bear_forest"
FALLEN_ELF_HIDEOUT = "floor_4_fallen_elf_hideout"
YOFEL_CASTLE = "floor_4_yofel_castle"
CALDERA_LAKE = "floor_4_caldera_lake"
USCO = "floor_4_usco"
MAGNATHERIUM_ID = "magnatherium"
BICEPS_CLEAR_FLAG = "floor4_biceps_archelon_defeated"
BUILD_TIME_MS = 3 * 60 * 60 * 1000
NOBLEWOOD_HARVEST_TIME_MS = 10_000  # Simulation action time per felled tree/core.
HIDEOUT_NAVIGATION_MS = 6 * 60 * 60 * 1000  # Mirrors the documented Kirito/Asuna traversal duration.


class Floor4ShipwrightScenario:
    """Shipwright of Yore from material gathering through the Dark-Elf-route intelligence report."""

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        magnatherium = AINCRAD_MONSTERS[MAGNATHERIUM_ID]
        CORE_LOOT_TABLES[magnatherium.loot_table_id] = AINCRAD_MONSTER_LOOT_TABLES[
            magnatherium.loot_table_id
        ]

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor4_shipwright_states", {})

    def _state(self, actor_id: str) -> dict:
        try:
            return self._states()[actor_id]
        except KeyError as exc:
            raise ValueError("Shipwright of Yore has not been started") from exc

    def _active_progress(self, actor_id: str):
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        if progress is None or progress.claimed:
            raise ValueError("Shipwright of Yore must be active")
        return progress

    @staticmethod
    def _transport_spec(origin: str, destination: str):
        specs = (*SHIPWRIGHT_GONDOLA_TRANSPORTS, WATER_CARRIER_HIDDEN_TRANSPORT)
        matches = [
            spec
            for spec in specs
            if {spec.endpoint_a, spec.endpoint_b} == {origin, destination}
        ]
        if len(matches) != 1:
            raise ValueError("destination is not connected by an implemented Floor 4 gondola route")
        return matches[0]

    def _execute_gondola_transport(self, actor_id: str, origin: str, destination: str, spec) -> dict:
        actor = self.runtime.actors[actor_id]
        gondola = actor.metadata["floor4_gondola"]
        if gondola["moored_at"] != origin:
            raise ValueError("the personal gondola is not moored at the actor's current location")
        resolution = authorized_transport(
            self.runtime,
            transport_id=spec.transport_id,
            actor_ids=[actor_id],
            carrier_actor_id=None,
            from_location_id=origin,
            to_location_id=destination,
            elapsed_ms=spec.elapsed_ms,
            transport_tags=spec.transport_tags,
        )
        record = authorized_transport_record(resolution)
        record["gondola_id"] = gondola["gondola_id"]
        gondola["moored_at"] = destination
        self._state(actor_id)["gondola_transport_history"].append(record)
        return record

    def start_quest(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != ROVIA:
            raise ValueError("Shipwright of Yore begins at Romolo's workshop in Rovia")
        self.runtime.accept_quest(actor_id, QUEST_ID)
        self._states().setdefault(
            actor_id,
            {
                "actor_id": actor_id,
                "stage": "gather_materials",
                "started_at_ms": self.runtime.world.now_ms,
                "gondola_built_at_ms": None,
                "first_sail_at_ms": None,
                "gondola_transport_history": [],
                "water_carriers_suspicious": False,
                "romolo_followup_at_ms": None,
                "water_carrier_follow_transport": None,
                "transport_followed_at_ms": None,
                "secret_discovered_at_ms": None,
                "completed_at_ms": None,
            },
        )
        return self.status(actor_id)

    def harvest_noblewood_core(self, actor_id: str, encounter_id: str) -> ItemInstance:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        if actor.location_id != BEAR_FOREST:
            raise ValueError("Noblewood Cores are harvested from the Bear Forest")
        encounter = self.runtime.encounters[encounter_id]
        if encounter.zone_id != BEAR_FOREST or actor_id not in encounter.participants:
            raise ValueError("actor must be fighting in the Bear Forest encounter")
        magnatherium = next(
            (
                member
                for member in encounter.participants.values()
                if member.metadata.get("monster_id") == MAGNATHERIUM_ID and member.alive
            ),
            None,
        )
        if magnatherium is None:
            raise ValueError("a living Magnatherium is needed to ram down a Noblewood tree")

        self.runtime.advance_encounter(encounter_id, NOBLEWOOD_HARVEST_TIME_MS)
        item = ItemInstance(
            instance_id=f"item_{uuid.uuid4().hex[:12]}",
            template_id="noblewood_core",
            owner_id=actor_id,
            quantity=1,
        )
        add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        self.runtime._append(
            encounter,
            "noblewood_core_harvested",
            actor_id,
            magnatherium.actor_id,
            template_id="noblewood_core",
            source="Magnatherium charge into aged teak",
        )
        return item

    @staticmethod
    def _inventory_quantity(actor, template_id: str) -> int:
        return sum(item.quantity for item in actor.inventory.values() if item.template_id == template_id)

    @staticmethod
    def _consume_one(actor, template_id: str) -> None:
        for instance_id, item in list(actor.inventory.items()):
            if item.template_id != template_id:
                continue
            item.quantity -= 1
            if item.quantity <= 0:
                actor.inventory.pop(instance_id)
            return
        raise ValueError(f"missing gondola material: {template_id}")

    def _select_materials(self, actor) -> tuple[dict[str, str], int]:
        selected: dict[str, str] = {}
        premium_count = 0
        for category in ("sealant", "lumber", "fasteners", "upholstery"):
            premium = PREMIUM_MATERIALS[category]
            standard = STANDARD_MATERIALS[category]
            if self._inventory_quantity(actor, premium) > 0:
                selected[category] = premium
                premium_count += 1
            elif self._inventory_quantity(actor, standard) > 0:
                selected[category] = standard
            else:
                raise ValueError(f"missing {category} material for the gondola")
        return selected, premium_count

    def build_gondola(
        self,
        actor_id: str,
        *,
        name: str = "Gondola",
        passenger_seats: int = 2,
        install_ram: bool = True,
    ) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        if actor.location_id != ROVIA:
            raise ValueError("Romolo builds the gondola at his Rovia workshop")
        if actor.metadata.get("floor4_gondola"):
            raise ValueError("character already owns a Floor 4 personal gondola")
        if not 1 <= passenger_seats <= 10:
            raise ValueError("personal gondola supports 1 to 10 passenger seats, plus the player gondolier")
        clean_name = name.strip() or "Gondola"

        selected, premium_count = self._select_materials(actor)
        for template_id in selected.values():
            self._consume_one(actor, template_id)
        ram = bool(install_ram and self._inventory_quantity(actor, OPTIONAL_RAM_MATERIAL) > 0)
        if ram:
            self._consume_one(actor, OPTIONAL_RAM_MATERIAL)

        self.runtime.advance_world(BUILD_TIME_MS)
        gondola = {
            "gondola_id": f"gondola_{uuid.uuid4().hex[:12]}",
            "name": clean_name,
            "owner_id": actor_id,
            "passenger_seats": passenger_seats,
            "gondolier_seat": 1,
            "materials": selected,
            "premium_material_count": premium_count,
            "quality": "premium" if premium_count == 4 else "mixed" if premium_count else "standard",
            "ram_installed": ram,
            "built_at_ms": self.runtime.world.now_ms,
            "moored_at": ROVIA,
        }
        actor.metadata["floor4_gondola"] = gondola
        self.runtime.quests.record_event(
            actor_id,
            kind=QuestObjectiveKind.DISCOVER,
            target_id=GONDOLA_TARGET,
        )
        state = self._state(actor_id)
        state["stage"] = "gondola_built"
        state["gondola_built_at_ms"] = self.runtime.world.now_ms
        return self.status(actor_id)

    def sail(self, actor_id: str, destination_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        gondola = actor.metadata.get("floor4_gondola")
        if not gondola:
            raise ValueError("character does not own a personal gondola")
        origin = str(actor.location_id)
        if origin == ROVIA and destination_id == FALLEN_ELF_HIDEOUT:
            raise ValueError("the hidden Fallen Elf route is reached by following the Water Carriers transport")
        if origin == FALLEN_ELF_HIDEOUT and destination_id == ROVIA and state["stage"] != "report_to_yofel":
            raise ValueError("the transport secret must be discovered before leaving the hideout")
        spec = self._transport_spec(origin, destination_id)
        if {origin, destination_id} == {CALDERA_LAKE, USCO} and not self.runtime.world.global_flags.get(BICEPS_CLEAR_FLAG):
            raise ValueError("Biceps Archelon blocks passage from Caldera Lake to the southern half of Floor 4")

        record = self._execute_gondola_transport(actor_id, origin, destination_id, spec)
        if state["first_sail_at_ms"] is None:
            state["first_sail_at_ms"] = self.runtime.world.now_ms
            state["water_carriers_suspicious"] = True
            state["stage"] = "return_to_romolo"
        return {
            "actor_id": actor_id,
            "transport": record,
            "gondola": dict(gondola),
            "shipwright_state": self.status(actor_id),
        }

    def receive_romolo_followup(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        if actor.location_id != ROVIA:
            raise ValueError("Romolo's Water Carriers lead is given in Rovia")
        if state["stage"] != "return_to_romolo":
            raise ValueError("the Water Carriers' hostility must be observed before returning to Romolo")
        self.runtime.interact_npc(actor_id, ROMOLO_ID)
        state["stage"] = "follow_transport_at_nightfall"
        state["romolo_followup_at_ms"] = self.runtime.world.now_ms
        return self.status(actor_id)

    def follow_water_carrier_transport(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        gondola = actor.metadata.get("floor4_gondola")
        if actor.location_id != ROVIA or not gondola:
            raise ValueError("the transport must be followed from Rovia in the player's gondola")
        if gondola["moored_at"] != ROVIA:
            raise ValueError("the player's gondola is not moored in Rovia")
        if state["stage"] != "follow_transport_at_nightfall":
            raise ValueError("Romolo must first identify the evening transport to follow")

        record = self._execute_gondola_transport(
            actor_id,
            ROVIA,
            FALLEN_ELF_HIDEOUT,
            WATER_CARRIER_HIDDEN_TRANSPORT,
        )
        record["followed_water_carriers"] = True
        state["gondola_transport_history"][-1] = record
        state["water_carrier_follow_transport"] = record
        state["stage"] = "hideout_search"
        state["transport_followed_at_ms"] = self.runtime.world.now_ms
        return self.status(actor_id)

    def investigate_fallen_elf_hideout(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        self._active_progress(actor_id)
        state = self._state(actor_id)
        if actor.location_id != FALLEN_ELF_HIDEOUT or state["stage"] != "hideout_search":
            raise ValueError("the Water Carriers secret is investigated inside the submerged Fallen Elf hideout")

        self.runtime.advance_world(HIDEOUT_NAVIGATION_MS)
        self.runtime.quests.record_event(
            actor_id,
            kind=QuestObjectiveKind.DISCOVER,
            target_id=SECRET_TARGET,
        )
        state["stage"] = "report_to_yofel"
        state["secret_discovered_at_ms"] = self.runtime.world.now_ms
        state["discovered_facts"] = [
            "Water Carriers Guild transports wooden boxes to Fallen Elves",
            "the delivered boxes are empty because the timber itself is shipbuilding material",
            "the Fallen Elves are supporting a future ship-borne assault on Yofel Castle",
        ]
        return self.status(actor_id)

    def report_to_yofel(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if actor.location_id != YOFEL_CASTLE:
            raise ValueError("the Dark Elf route completes by reporting the intelligence at Yofel Castle")
        if state["stage"] != "report_to_yofel":
            raise ValueError("the Water Carriers secret has not yet been uncovered")
        self.runtime.interact_npc(actor_id, YOFILIS_ID)
        claim = self.runtime.claim_quest(actor_id, QUEST_ID)
        state["stage"] = "completed"
        state["completed_at_ms"] = self.runtime.world.now_ms
        actor.metadata["floor4_laketop_fortress_unlocked"] = True
        return {
            "claim": asdict(claim),
            "shipwright_state": self.status(actor_id),
            "next_quest_id": "laketop_fortress",
        }

    def status(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        actor = self.runtime.actors[actor_id]
        progress = self.runtime.quests.progress_by_actor.get(actor_id, {}).get(QUEST_ID)
        return {
            **state,
            "gondola": actor.metadata.get("floor4_gondola"),
            "quest_progress": dict(progress.counters) if progress else None,
        }


def install_floor4_shipwright_scenario(runtime) -> Floor4ShipwrightScenario:
    return Floor4ShipwrightScenario(runtime)

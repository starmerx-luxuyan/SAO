from __future__ import annotations

import uuid

from sao_mcp.corpus.floor7_intrigue import (
    ARENA_DYE_EVIDENCE_ID,
    DECOLORANT_SIMMER_MS,
    LYKAON_DECOLORANT_ID,
    NARSOS_FRUIT_ID,
    NARSOS_REQUIRED,
    RUBRABIUM_DYE_ID,
    WURTZ_REQUIRED,
    WURTZ_STONE_ID,
)
from sao_mcp.corpus.monsters import AINCRAD_MONSTERS
from sao_mcp.domain.models import CursorColor, ItemInstance
from sao_mcp.rules.inventory import add_item


CASINO = "floor_7_volupta_grand_casino"
MONSTER_ARENA = "floor_7_monster_arena"
LOOSEROCK_FOREST = "floor_7_looserock_forest"
WEST_RIVERBANK = "floor_7_west_riverbank"
KORLOY_STABLES = "floor_7_korloy_monster_stables"

NARSOS_GATHER_MS = 60 * 60 * 1000  # Simulation; the source locks quantity/location, not gathering duration.
WURTZ_GATHER_MS = 5 * 60 * 60 * 1000  # Source estimate for one person to collect the requested fifty stones.
STABLE_ESCAPE_MS = 12 * 60 * 1000  # Simulation abstraction for the escape from the casino rear yard to the riverbank.
EMPLOYMENT_FADE_MS = 60_000  # Simulation duration for the already-failing control state once the Lykaon is free.


class Floor7CasinoIntrigueScenario:
    """Investigate Korloy arena cheating, brew the canon decolorant and reveal the disguised Storm Lykaon."""

    def __init__(self, runtime, volupta) -> None:
        self.runtime = runtime
        self.volupta = volupta

    def _states(self) -> dict:
        return self.runtime.world.global_flags.setdefault("floor7_casino_intrigue_states", {})

    def _state(self, actor_id: str) -> dict:
        try:
            return self._states()[actor_id]
        except KeyError as exc:
            raise ValueError("the Volupta cheating investigation has not been started") from exc

    @staticmethod
    def _quantity(actor, template_id: str) -> int:
        return sum(item.quantity for item in actor.inventory.values() if item.template_id == template_id)

    @staticmethod
    def _consume(actor, template_id: str, quantity: int) -> None:
        remaining = quantity
        for instance_id, item in list(actor.inventory.items()):
            if item.template_id != template_id:
                continue
            used = min(item.quantity, remaining)
            item.quantity -= used
            remaining -= used
            if item.quantity <= 0:
                actor.inventory.pop(instance_id)
            if remaining <= 0:
                return
        raise ValueError(f"missing required material: {template_id}")

    def inspect_first_match_cage(self, actor_id: str, match_instance_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        if actor.location_id != MONSTER_ARENA:
            raise ValueError("the suspicious red residue is inspected in the Monster Arena cage")
        match = self.volupta.match_state(match_instance_id)
        if match["definition_id"] != "rusty_lykaon_vs_bouncy_slater" or match["status"] != "resolved":
            raise ValueError("the relevant Rusty Lykaon/Bouncy Slater match must have finished")

        state = self._states().setdefault(
            actor_id,
            {
                "actor_id": actor_id,
                "stage": "arena_dye_evidence_found",
                "match_instance_id": match_instance_id,
                "evidence_instance_id": None,
                "reported_to_nirrnir": False,
                "narsos_collected": 0,
                "wurtz_collected": 0,
                "decolorant_instance_id": None,
                "disguised_lykaon_actor_id": None,
                "true_species_revealed": False,
                "storm_lykaon_freed": False,
                "field_encounter_id": None,
            },
        )
        if state["evidence_instance_id"] is None:
            evidence = ItemInstance(
                instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
                template_id=ARENA_DYE_EVIDENCE_ID,
                owner_id=actor_id,
                metadata={
                    "match_instance_id": match_instance_id,
                    "identified_as_blood": False,
                    "plant_dye_suspected": True,
                },
            )
            add_item(actor, evidence, self.runtime.catalog, allow_overweight=True)
            state["evidence_instance_id"] = evidence.instance_id
        return self.status(actor_id)

    def report_evidence_to_nirrnir(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if actor.location_id != CASINO:
            raise ValueError("Nirrnir receives the arena-cheating evidence at the Grand Casino")
        if state["stage"] != "arena_dye_evidence_found":
            raise ValueError("the suspicious arena residue has not been documented")
        state["reported_to_nirrnir"] = True
        state["stage"] = "gather_decolorant_materials"
        state["material_request"] = {
            NARSOS_FRUIT_ID: NARSOS_REQUIRED,
            WURTZ_STONE_ID: WURTZ_REQUIRED,
        }
        state["recipe"] = {
            "narsos_fruit": NARSOS_REQUIRED,
            "wurtz_stone": WURTZ_REQUIRED,
            "preparation": "squeeze fruit, combine with stones in the specified batch, simmer over low heat",
            "simmer_ms": DECOLORANT_SIMMER_MS,
        }
        return self.status(actor_id)

    def gather_narsos_fruit(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "gather_decolorant_materials":
            raise ValueError("Nirrnir has not requested the decolorant materials")
        if actor.location_id != LOOSEROCK_FOREST:
            raise ValueError("ripe Narsos fruit is gathered in Looserock Forest")
        missing = max(0, NARSOS_REQUIRED - self._quantity(actor, NARSOS_FRUIT_ID))
        if missing:
            self.runtime.advance_world(NARSOS_GATHER_MS)
            item = ItemInstance(
                instance_id=f"material_{uuid.uuid4().hex[:12]}",
                template_id=NARSOS_FRUIT_ID,
                owner_id=actor_id,
                quantity=missing,
            )
            add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        state["narsos_collected"] = min(NARSOS_REQUIRED, self._quantity(actor, NARSOS_FRUIT_ID))
        return self.status(actor_id)

    def gather_wurtz_stones(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if state["stage"] != "gather_decolorant_materials":
            raise ValueError("Nirrnir has not requested the decolorant materials")
        if actor.location_id != WEST_RIVERBANK:
            raise ValueError("Wurtz stones are gathered from the riverbed west of Volupta")
        missing = max(0, WURTZ_REQUIRED - self._quantity(actor, WURTZ_STONE_ID))
        if missing:
            self.runtime.advance_world(WURTZ_GATHER_MS)
            item = ItemInstance(
                instance_id=f"material_{uuid.uuid4().hex[:12]}",
                template_id=WURTZ_STONE_ID,
                owner_id=actor_id,
                quantity=missing,
            )
            add_item(actor, item, self.runtime.catalog, allow_overweight=True)
        state["wurtz_collected"] = min(WURTZ_REQUIRED, self._quantity(actor, WURTZ_STONE_ID))
        return self.status(actor_id)

    def brew_decolorant(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if actor.location_id != CASINO:
            raise ValueError("the decolorant batch is prepared with Nirrnir/Kio at the Grand Casino")
        if self._quantity(actor, NARSOS_FRUIT_ID) < NARSOS_REQUIRED:
            raise ValueError("twenty ripe Narsos fruits are required")
        if self._quantity(actor, WURTZ_STONE_ID) < WURTZ_REQUIRED:
            raise ValueError("fifty Wurtz stones are required")
        if state["decolorant_instance_id"] is not None:
            return self.status(actor_id)

        self._consume(actor, NARSOS_FRUIT_ID, NARSOS_REQUIRED)
        self._consume(actor, WURTZ_STONE_ID, WURTZ_REQUIRED)
        self.runtime.advance_world(DECOLORANT_SIMMER_MS)
        bottle = ItemInstance(
            instance_id=f"questitem_{uuid.uuid4().hex[:12]}",
            template_id=LYKAON_DECOLORANT_ID,
            owner_id=actor_id,
            metadata={
                "narsos_fruits_used": NARSOS_REQUIRED,
                "wurtz_stones_used": WURTZ_REQUIRED,
                "simmer_ms": DECOLORANT_SIMMER_MS,
                "batch_size": "one observed quest bottle",
            },
        )
        add_item(actor, bottle, self.runtime.catalog, allow_overweight=True)
        state["decolorant_instance_id"] = bottle.instance_id
        state["stage"] = "decolorant_ready_infiltrate_stables"
        return self.status(actor_id)

    def discover_dyed_lykaon(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if actor.location_id != KORLOY_STABLES:
            raise ValueError("the disguised Lykaon is found in the Korloy monster stables")
        if state["stage"] != "decolorant_ready_infiltrate_stables":
            raise ValueError("the decolorant has not been prepared")
        if state["disguised_lykaon_actor_id"] is not None:
            return self.status(actor_id)

        definition = AINCRAD_MONSTERS["storm_lykaon"]
        lykaon = self.runtime._create_monster(
            name="Rusty Lykaon",
            level=definition.level,
            location_id=KORLOY_STABLES,
            hp_factor=definition.hp_factor,
            loot_table_id=definition.loot_table_id,
            quest_kill_id=definition.quest_kill_id,
        )
        lykaon.location_id = KORLOY_STABLES
        lykaon.hp = max(1, int(round(lykaon.max_hp * 0.33)))
        lykaon.alive = True
        lykaon.cursor = CursorColor.YELLOW
        lykaon.metadata.update(
            {
                "monster_id": "rusty_lykaon",
                "arena_registered_rank": 6,
                "rubrabium_dyed": True,
                "restrained_by_chain": True,
                "korloy_employment_active": True,
                "hidden_dye_damage": True,
                "true_species_not_yet_visible": True,
            }
        )
        state["disguised_lykaon_actor_id"] = lykaon.actor_id
        state["stage"] = "dyed_lykaon_found"
        return self.status(actor_id)

    def apply_decolorant(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if actor.location_id != KORLOY_STABLES or state["stage"] != "dyed_lykaon_found":
            raise ValueError("the decolorant is applied to the restrained Lykaon in the Korloy stable")
        bottle_id = state["decolorant_instance_id"]
        bottle = actor.inventory.get(bottle_id)
        if bottle is None or bottle.template_id != LYKAON_DECOLORANT_ID:
            raise ValueError("the prepared Lykaon decolorant is missing")
        lykaon = self.runtime.actors[state["disguised_lykaon_actor_id"]]

        actor.inventory.pop(bottle.instance_id)
        bottle.owner_id = None
        bottle.metadata["consumed_on_lykaon"] = lykaon.actor_id
        lykaon.name = "Storm Lykaon"
        lykaon.metadata.update(
            {
                "monster_id": "storm_lykaon",
                "rubrabium_dyed": False,
                "rubrabium_dye_removed": True,
                "hidden_dye_damage": False,
                "true_species_not_yet_visible": False,
                "revealed_pelt": "silver-gray with black mottling",
                "revealed_at_ms": self.runtime.world.now_ms,
            }
        )
        state["true_species_revealed"] = True
        state["stage"] = "storm_lykaon_revealed"
        return self.status(actor_id)

    def free_storm_lykaon(self, actor_id: str) -> dict:
        actor = self.runtime.actors[actor_id]
        state = self._state(actor_id)
        if actor.location_id != KORLOY_STABLES or state["stage"] != "storm_lykaon_revealed":
            raise ValueError("the revealed Storm Lykaon is still chained in the Korloy stable")
        lykaon = self.runtime.actors[state["disguised_lykaon_actor_id"]]
        lykaon.metadata["restrained_by_chain"] = False
        lykaon.metadata["freed_from_korloy"] = True
        self.runtime.advance_world(STABLE_ESCAPE_MS)
        actor.location_id = WEST_RIVERBANK
        lykaon.location_id = WEST_RIVERBANK
        encounter = self.runtime.start_encounter([actor_id, lykaon.actor_id], zone_id=WEST_RIVERBANK, safe_zone=False)
        lykaon.cursor = CursorColor.YELLOW
        lykaon.metadata["employment_fades_at_encounter_ms"] = encounter.time_ms + EMPLOYMENT_FADE_MS
        state["storm_lykaon_freed"] = True
        state["field_encounter_id"] = encounter.encounter_id
        state["stage"] = "freed_lykaon_control_fading"
        return self.status(actor_id)

    def expire_storm_lykaon_control(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        if state["stage"] != "freed_lykaon_control_fading":
            raise ValueError("the freed Storm Lykaon's Korloy control is not currently fading")
        encounter = self.runtime.encounters[state["field_encounter_id"]]
        lykaon = self.runtime.actors[state["disguised_lykaon_actor_id"]]
        deadline = int(lykaon.metadata["employment_fades_at_encounter_ms"])
        remaining = max(0, deadline - encounter.time_ms)
        if remaining:
            self.runtime.advance_world(remaining)
            self.runtime.advance_encounter(encounter.encounter_id, remaining)
        lykaon.cursor = CursorColor.RED
        lykaon.metadata["korloy_employment_active"] = False
        lykaon.metadata["ordinary_monster_behavior_resumed"] = True
        state["stage"] = "storm_lykaon_free_and_hostile"
        return self.status(actor_id)

    def status(self, actor_id: str) -> dict:
        state = self._state(actor_id)
        actor = self.runtime.actors[actor_id]
        lykaon_id = state.get("disguised_lykaon_actor_id")
        lykaon = self.runtime.actors.get(lykaon_id) if lykaon_id else None
        visible_species = None
        if lykaon is not None:
            visible_species = lykaon.name
        return {
            **state,
            "narsos_in_inventory": self._quantity(actor, NARSOS_FRUIT_ID),
            "wurtz_in_inventory": self._quantity(actor, WURTZ_STONE_ID),
            "visible_lykaon_species": visible_species,
            "lykaon_hp": lykaon.hp if lykaon else None,
            "lykaon_max_hp": lykaon.max_hp if lykaon else None,
            "lykaon_cursor": lykaon.cursor.value if lykaon else None,
            "next_stage": (
                "report the dye evidence to Nirrnir" if state["stage"] == "arena_dye_evidence_found"
                else "gather 20 Narsos fruits and 50 Wurtz stones" if state["stage"] == "gather_decolorant_materials"
                else "brew the three-hour decolorant batch" if state["stage"] == "gather_decolorant_materials" and self._quantity(actor, NARSOS_FRUIT_ID) >= NARSOS_REQUIRED and self._quantity(actor, WURTZ_STONE_ID) >= WURTZ_REQUIRED
                else "infiltrate the Korloy monster stables" if state["stage"] == "decolorant_ready_infiltrate_stables"
                else "apply the decolorant" if state["stage"] == "dyed_lykaon_found"
                else "expose the cheating or free the Storm Lykaon" if state["stage"] == "storm_lykaon_revealed"
                else "wait for Korloy control to expire; then ordinary encounter rules apply" if state["stage"] == "freed_lykaon_control_fading"
                else None
            ),
        }


def install_floor7_casino_intrigue_scenario(runtime, volupta) -> Floor7CasinoIntrigueScenario:
    required = {ARENA_DYE_EVIDENCE_ID, NARSOS_FRUIT_ID, WURTZ_STONE_ID, LYKAON_DECOLORANT_ID, RUBRABIUM_DYE_ID}
    if any(template_id not in runtime.catalog.items for template_id in required):
        raise RuntimeError("Floor 7 casino-intrigue material corpus was not loaded")
    if "storm_lykaon" not in AINCRAD_MONSTERS:
        raise RuntimeError("Storm Lykaon monster corpus was not loaded")
    return Floor7CasinoIntrigueScenario(runtime, volupta)

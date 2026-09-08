from __future__ import annotations

import json
from enum import Enum
from typing import Any


def _default(value: Any):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=_default)


def register_floor6_tools(mcp, cube, stachion, trials) -> None:
    @mcp.tool()
    def start_floor6_stachion_curse(actor_id: str) -> str:
        """Accept Cylon's Curse of Stachion quest at the Stachion lord's manor."""
        return _json(stachion.start_quest(actor_id))

    @mcp.tool()
    def interview_floor6_stachion_witness(actor_id: str, witness_id: str) -> str:
        """Interview one of Pithagrus's seven former associates in Stachion."""
        return _json(stachion.interview_witness(actor_id, witness_id))

    @mcp.tool()
    def search_floor6_pithagrus_suribus_house(actor_id: str) -> str:
        """Search Pithagrus's second home in Suribus and obtain the golden key after the Stachion investigation."""
        return _json(stachion.search_pithagrus_house(actor_id))

    @mcp.tool()
    def trigger_floor6_cylon_capture(actor_id: str) -> str:
        """Trigger Cylon's scripted paralysis-gas capture after the golden key is obtained; the actual key instance is confiscated."""
        return _json(stachion.trigger_cylon_capture(actor_id))

    @mcp.tool()
    def advance_floor6_cylon_transport_to_ambush(actor_id: str) -> str:
        """Advance Cylon's carriage from Suribus to the point immediately before the Morte/Joe ambush."""
        return _json(stachion.advance_transport_to_ambush_site(actor_id))

    @mcp.tool()
    def trigger_floor6_morte_joe_ambush(actor_id: str) -> str:
        """Start the carriage ambush: Morte kills Cylon and his key/jar/mask valuables become real ground-loot instances."""
        return _json(stachion.trigger_morte_joe_ambush(actor_id))

    @mcp.tool()
    def topple_floor6_paralysis_jar(actor_id: str) -> str:
        """While still paralysed, blow Cylon's dropped Namnepenth poison jar over to create the paralysis-cloud diversion."""
        return _json(stachion.topple_poison_jar(actor_id))

    @mcp.tool()
    def advance_floor6_to_paralysis_release(actor_id: str) -> str:
        """Advance the remaining scripted paralysis after the poison-cloud diversion, returning the scene to ordinary PvP rules."""
        return _json(stachion.advance_to_paralysis_release(actor_id))

    @mcp.tool()
    def resolve_floor6_ambusher_retreat(actor_id: str) -> str:
        """After ordinary PvP begins, let living ambushers retreat once one is defeated or the simulation low-HP retreat condition is reached."""
        return _json(stachion.resolve_ambusher_retreat(actor_id))

    @mcp.tool()
    def recover_floor6_cylon_ground_loot(actor_id: str) -> str:
        """After Morte/Joe are dead or gone, recover Cylon's exact dropped item instances and reopen the road to Suribus/Stachion."""
        return _json(stachion.recover_cylon_ground_loot(actor_id))

    @mcp.tool()
    def get_floor6_stachion_curse_state(actor_id: str) -> str:
        """Inspect Curse of Stachion witness/key/capture/ambush progress. The quest remains active after the key is recovered."""
        return _json(stachion.status(actor_id))

    @mcp.tool()
    def meet_floor6_myia(actor_id: str) -> str:
        """Meet Myia on the release route after Cylon's ambush and bring the two paired iron keys into the story."""
        return _json(trials.meet_myia(actor_id))

    @mcp.tool()
    def inspect_floor6_paired_iron_key_signal(actor_id: str) -> str:
        """Use Cylon's and Theano's paired iron keys: vibration gives direction and resonance gives a playable distance hint."""
        return _json(trials.paired_iron_key_signal(actor_id))

    @mcp.tool()
    def hear_floor6_theano_note(actor_id: str) -> str:
        """Hear Myia's account of Theano's disappearance note and its instruction to visit Barro."""
        return _json(trials.hear_theano_note(actor_id))

    @mcp.tool()
    def consult_floor6_barro(actor_id: str) -> str:
        """Consult Barro, the former mansion gardener named in Theano's disappearance note."""
        return _json(trials.consult_barro(actor_id))

    @mcp.tool()
    def open_floor6_dungeon_of_trials(actor_id: str) -> str:
        """Use the Suribus golden key at the Stachion manor basement entrance and unlock the Dungeon of Trials world edge."""
        return _json(trials.open_dungeon_of_trials(actor_id))

    @mcp.tool()
    def inspect_floor6_dungeon_release_route(actor_id: str) -> str:
        """Enter the Dungeon of Trials and establish the changed release-route state after Theano has already passed through."""
        return _json(trials.inspect_release_dungeon(actor_id))

    @mcp.tool()
    def get_floor6_trials_state(actor_id: str) -> str:
        """Inspect Myia, paired-key and Dungeon of Trials release-route progress."""
        return _json(trials.status(actor_id))

    @mcp.tool()
    def start_floor6_irrational_cube_puzzle(player_ids: list[str]) -> str:
        """Begin The Irrational Cube's invulnerable 3x3 number-face puzzle in the Floor 6 Boss Room."""
        return _json(cube.start_puzzle(player_ids))

    @mcp.tool()
    def rotate_floor6_cube_row(instance_id: str, row: int, direction: str) -> str:
        """Rotate one numbered row left/right during The Irrational Cube's invulnerability puzzle."""
        return _json(cube.rotate_row(instance_id, row, direction))

    @mcp.tool()
    def rotate_floor6_cube_column(instance_id: str, column: int, direction: str) -> str:
        """Rotate one numbered column up/down during The Irrational Cube's invulnerability puzzle."""
        return _json(cube.rotate_column(instance_id, column, direction))

    @mcp.tool()
    def engage_floor6_irrational_cube(instance_id: str) -> str:
        """After the number face matches the nine-digit door code, start the normal Floor 6 boss combat phase."""
        return _json(cube.engage_boss(instance_id))

    @mcp.tool()
    def get_floor6_irrational_cube_state(instance_id: str) -> str:
        """Inspect the current number face, target code, puzzle stage and combat state."""
        return _json(cube.status(instance_id))

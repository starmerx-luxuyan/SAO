from __future__ import annotations

import json
from dataclasses import asdict
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


def register_floor22_tools(mcp, runtime) -> None:
    @mcp.tool()
    def start_floor22_witch_quest(player_ids: list[str]) -> str:
        """Trigger Toto's Forest House K4 quest transition into the isolated Floor 22 quest area."""
        return _json(runtime.start_witch_quest(player_ids))

    @mcp.tool()
    def collect_floor22_witch_treasure(actor_id: str, template_id: str) -> str:
        """Recover one optional Scarecrow/Tin/Lion treasure before entering the Witch Castle."""
        return _json(asdict(runtime.collect_witch_optional_treasure(actor_id, template_id)))

    @mcp.tool()
    def enter_floor22_witch_castle(instance_id: str) -> str:
        """Enter the Witch Castle and spawn the four Werepanther key encounter."""
        encounter = runtime.enter_witch_castle(instance_id)
        return _json(
            {
                "instanceId": instance_id,
                "encounterId": encounter.encounter_id,
                "zoneId": encounter.zone_id,
                "participantIds": list(encounter.participants),
            }
        )

    @mcp.tool()
    def start_floor22_witch_confrontation(instance_id: str, accept_soup: bool = False) -> str:
        """Use the Werepanther key to enter the inner room and start the Witch confrontation/paralysis event."""
        encounter, witch = runtime.start_witch_confrontation(instance_id, accept_soup=accept_soup)
        return _json(
            {
                "instanceId": instance_id,
                "encounterId": encounter.encounter_id,
                "witchId": witch.actor_id,
                "witchHp": witch.hp,
                "witchMaxHp": witch.max_hp,
                "participantIds": list(encounter.participants),
            }
        )

    @mcp.tool()
    def finish_floor22_witch_quest_return(instance_id: str) -> str:
        """Return the Log House to its Floor 22 site after the Witch is defeated and unlock property eligibility."""
        return _json(runtime.return_from_witch_quest(instance_id))

    @mcp.tool()
    def get_floor22_witch_instance(instance_id: str) -> str:
        """Inspect the persistent stage and actors of one Floor 22 Witch quest instance."""
        return _json(runtime._instance(instance_id))

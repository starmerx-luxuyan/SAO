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


def register_floor5_tools(mcp, karluin, fuscus, shortcut) -> None:
    @mcp.tool()
    def order_floor5_blue_blueberry_tart(actor_id: str) -> str:
        """Eat BLINK & BRINK's limited Blue-Blueberry Tart and gain the one-hour Karluin Relic Finding Bonus."""
        return _json(karluin.order_blue_blueberry_tart(actor_id))

    @mcp.tool()
    def get_floor5_relic_bonus(actor_id: str) -> str:
        """Inspect the actor's Karluin Relic Finding Bonus and remaining duration."""
        return _json(karluin.relic_bonus_state(actor_id))

    @mcp.tool()
    def search_floor5_karluin_relic(actor_id: str) -> str:
        """Search the current Karluin ruin/catacomb location for a glowing relic while the Tart buff is active."""
        return _json(asdict(karluin.search_relic(actor_id)))

    @mcp.tool()
    def breathe_on_floor5_luminescence_ring(actor_id: str, instance_id: str) -> str:
        """Breathe on the Ring of Luminescence to activate its Candlelight glow."""
        return _json(karluin.breathe_on_luminescence_ring(actor_id, instance_id))

    @mcp.tool()
    def create_floor5_mournful_wraith_encounter(actor_id: str) -> str:
        """Create a Mournful Wraith encounter in Karluin's dangerous lower catacombs."""
        encounter, monster = karluin.create_mournful_wraith_encounter(actor_id)
        return _json(
            {
                "encounterId": encounter.encounter_id,
                "monsterId": monster.actor_id,
                "monsterTemplateId": monster.metadata.get("monster_id"),
                "name": monster.name,
                "level": monster.level,
                "maxHp": monster.max_hp,
            }
        )

    @mcp.tool()
    def trigger_floor5_shrewman_robbing(actor_id: str, instance_id: str) -> str:
        """Drop an item in the lower catacombs and let a Sly Shrewman overwrite its ownership with Robbing."""
        encounter, thief, stolen = karluin.trigger_shrewman_robbery(actor_id, instance_id)
        return _json(
            {
                "encounterId": encounter.encounter_id,
                "thiefId": thief.actor_id,
                "stolenInstanceId": stolen.instance_id,
                "templateId": stolen.template_id,
                "newOwnerId": stolen.owner_id,
            }
        )

    @mcp.tool()
    def recover_floor5_shrewman_items(actor_id: str, thief_id: str) -> str:
        """Recover the exact item instances stolen by a defeated Sly Shrewman."""
        return _json({"recoveredInstanceIds": karluin.recover_shrewman_stolen_items(actor_id, thief_id)})

    @mcp.tool()
    def get_floor5_shortcut_puzzle() -> str:
        """Inspect the Karluin catacomb shortcut boss weakening puzzle progress."""
        return _json(shortcut.puzzle_state())

    @mcp.tool()
    def investigate_floor5_shortcut_puzzle(actor_id: str, hours: float = 1.0) -> str:
        """Spend world time investigating the puzzle that weakens the Karluin shortcut area boss."""
        return _json(shortcut.investigate_puzzle(actor_id, hours=hours))

    @mcp.tool()
    def start_floor5_shortcut_area_boss(player_ids: list[str]) -> str:
        """Fight the unnamed Karluin catacomb area boss guarding the Mananarena shortcut."""
        return _json(shortcut.start_area_boss_raid(player_ids))

    @mcp.tool()
    def get_floor5_shortcut_boss_state(instance_id: str) -> str:
        """Inspect the shortcut guardian's state, puzzle weakening and shortcut-clear flag."""
        return _json(shortcut.status(instance_id))

    @mcp.tool()
    def traverse_floor5_karluin_mananarena_shortcut(actor_id: str) -> str:
        """Use the cleared Karluin-Mananarena shortcut tunnel from either side."""
        return _json(shortcut.traverse_shortcut(actor_id))

    @mcp.tool()
    def start_floor5_fuscus_raid(player_ids: list[str]) -> str:
        """Start Fuscus the Vacant Colossus using the implemented six-bar Floor 5 boss definition."""
        return _json(fuscus.start_raid(player_ids))

    @mcp.tool()
    def resolve_floor5_hidden_flag_drop(instance_id: str) -> str:
        """After Fuscus dies, resolve the hidden personal Flag of Valor drop without revealing its recipient."""
        return _json(fuscus.resolve_hidden_flag_drop(instance_id))

    @mcp.tool()
    def check_floor5_personal_flag_drop(actor_id: str, instance_id: str) -> str:
        """Check only this raid participant's personal Fuscus drop result."""
        return _json(fuscus.check_personal_flag_drop(actor_id, instance_id))

    @mcp.tool()
    def refresh_floor5_flag_of_valor_aura(actor_id: str, encounter_id: str) -> str:
        """Deploy or refresh the Flag of Valor aura from current authoritative positions."""
        return _json(fuscus.refresh_flag_aura(actor_id, encounter_id))

    @mcp.tool()
    def withdraw_floor5_flag_of_valor(actor_id: str, encounter_id: str) -> str:
        """Withdraw the Flag of Valor and remove its guildmate stat aura from this encounter."""
        return _json(fuscus.withdraw_flag(actor_id, encounter_id))

    @mcp.tool()
    def get_floor5_fuscus_state(instance_id: str) -> str:
        """Inspect Fuscus boss state and whether its hidden Flag drop has been resolved, without exposing the recipient."""
        return _json(fuscus.status(instance_id))

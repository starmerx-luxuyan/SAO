from __future__ import annotations

from sao_mcp.domain.models import Provenance, ProvenanceKind
from sao_mcp.rules.quests import (
    QuestDefinition,
    QuestObjectiveDefinition,
    QuestObjectiveKind,
    QuestReward,
    QuestRewardItem,
)


DAY_MS = 24 * 60 * 60 * 1000


CORE_QUESTS: dict[str, QuestDefinition] = {
    "secret_medicine_of_the_forest": QuestDefinition(
        quest_id="secret_medicine_of_the_forest",
        name="Secret Medicine of the Forest",
        floor_number=1,
        giver_id="npc_horunka_mother",
        turn_in_id="npc_horunka_mother",
        objectives=(
            QuestObjectiveDefinition(
                "obtain_ovule",
                QuestObjectiveKind.COLLECT,
                "little_nepenthes_ovule",
                required=1,
                consume_on_turn_in=True,
            ),
        ),
        reward=QuestReward(
            items=(QuestRewardItem("anneal_blade", 1, max_enhancement_attempts=8),),
        ),
        repeatable=True,
        global_accept_cooldown_ms=DAY_MS,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=(
                "Sword Art Online Volume 8: First Day",
                "Sword Art Online Progressive Volume 1",
            ),
            notes=(
                "Floor 1 Horunka collection quest; objective is a flowerhead Little Nepenthes ovule; "
                "reward is Anneal Blade; official-service acceptance cooldown is 24 hours."
            ),
        ),
    ),
    "field_combat_orientation": QuestDefinition(
        quest_id="field_combat_orientation",
        name="Field Combat Orientation",
        floor_number=1,
        giver_id="npc_tutorial_instructor",
        turn_in_id="npc_tutorial_instructor",
        objectives=(
            QuestObjectiveDefinition("defeat_boars", QuestObjectiveKind.KILL, "frenzy_boar", required=3),
        ),
        reward=QuestReward(col=40, xp=55),
        repeatable=False,
        provenance=Provenance(
            ProvenanceKind.SIMULATION,
            notes="Runtime tutorial quest; not an SAO canon quest.",
        ),
    ),
}

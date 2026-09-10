from __future__ import annotations

import math

from sao_mcp.domain.models import EntityKind
from sao_mcp.runtime.spatial_runtime import SpatialAincradRuntime


class RaidSpatialAincradRuntime(SpatialAincradRuntime):
    """Spatial runtime with deterministic formations that remain valid up to a 48-player raid."""

    def start_encounter(self, actor_ids, *, zone_id=None, safe_zone=None, anti_crystal=None):
        # Encounter time is intentionally local and begins at zero. Action/recovery/reaction deadlines
        # are expressed in that local clock, so they must not leak from an earlier finished encounter.
        for actor_id in dict.fromkeys(actor_ids):
            actor = self.actors[actor_id]
            actor.committed_until_ms = 0
            actor.recovery_until_ms = 0
            actor.ai_reaction_until_ms = 0
        return super().start_encounter(
            actor_ids,
            zone_id=zone_id,
            safe_zone=safe_zone,
            anti_crystal=anti_crystal,
        )

    def _boss_minion_slot_position(self, boss, ordinal: int) -> tuple[float, float]:
        # Six minions per half-ring keeps 0.9m monster bodies from overlapping and leaves the
        # player-facing side open for the boss to approach the raid. Geometry is simulation tuning.
        boss_position = self._boss_position_for_formation(boss)
        ring = ordinal // 6
        slot = ordinal % 6
        radius = 2.2 + ring * 1.2
        angle = -math.pi / 2.0 + (slot + 0.5) * (math.pi / 6.0)
        return (
            round(boss_position[0] + math.cos(angle) * radius, 4),
            round(boss_position[1] + math.sin(angle) * radius, 4),
        )

    @staticmethod
    def _boss_position_for_formation(boss) -> tuple[float, float]:
        return (0.0, 0.0)

    def _spawn_boss_minions(self, encounter, boss, count, *, reason, bar_depletion=None):
        before = int(boss.metadata.get("boss_minions_spawned", 0))
        spawned = super()._spawn_boss_minions(
            encounter,
            boss,
            count,
            reason=reason,
            bar_depletion=bar_depletion,
        )
        for index, actor_id in enumerate(spawned):
            ordinal = before + index
            encounter.participants[actor_id].metadata["boss_spawn_ordinal"] = ordinal
            encounter.positions[actor_id] = self._boss_minion_slot_position(boss, ordinal)
        return spawned

    def _arrange_raid_formation(self, encounter, boss) -> None:
        encounter.positions[boss.actor_id] = self._boss_position_for_formation(boss)
        players = [
            actor
            for actor in encounter.participants.values()
            if actor.kind is EntityKind.PLAYER
        ]
        # 16 players per half-ring: inner radius 4.2m has ~0.82m arc spacing, safely above
        # the 0.7m combined player collision diameter. Three rings cover the canonical 48 cap.
        for index, actor in enumerate(players):
            ring = index // 16
            slot = index % 16
            remaining = len(players) - ring * 16
            count_in_ring = min(16, max(1, remaining))
            radius = 4.2 + ring * 2.0
            angle = math.pi / 2.0 + (slot + 0.5) * (math.pi / count_in_ring)
            encounter.positions[actor.actor_id] = (
                round(math.cos(angle) * radius, 4),
                round(math.sin(angle) * radius, 4),
            )
            actor.metadata["raid_formation_ring"] = ring
            actor.metadata["raid_formation_slot"] = slot

        for actor in encounter.participants.values():
            if actor.metadata.get("boss_parent_id") != boss.actor_id:
                continue
            ordinal = int(actor.metadata.get("boss_spawn_ordinal", 0))
            encounter.positions[actor.actor_id] = self._boss_minion_slot_position(boss, ordinal)

    def start_floor_boss_encounter(
        self,
        player_ids,
        *,
        boss_definition_id: str = "illfang_the_kobold_lord",
        enforce_location: bool = True,
    ):
        encounter, boss = super().start_floor_boss_encounter(
            player_ids,
            boss_definition_id=boss_definition_id,
            enforce_location=enforce_location,
        )
        self._arrange_raid_formation(encounter, boss)
        return encounter, boss

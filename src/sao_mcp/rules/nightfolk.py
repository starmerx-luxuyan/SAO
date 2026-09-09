from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind


CIVIS_NOCTE = "civis_nocte"
DOMINUS_NOCTE = "dominus_nocte"
CIVIS_NOCTE_COMBAT_BONUS = 0.12
DOMINUS_NOCTE_COMBAT_BONUS = 0.24
CIVIS_BLOOD_RECOVERY_RATIO = 0.70


@dataclass(slots=True, frozen=True)
class CivisNocteTransformation:
    actor_id: str
    master_actor_id: str
    transformed_at_ms: int
    combat_bonus: float
    sunlight_weakness: str
    can_create_followers: bool


@dataclass(slots=True, frozen=True)
class BloodFeedingResolution:
    civis_actor_id: str
    donor_actor_id: str
    donor_hp_spent: int
    hp_restored: int
    civis_hp_after: int
    donor_hp_after: int
    donor_transformed: bool


@dataclass(slots=True, frozen=True)
class NightMonsterTamingResolution:
    tamer_actor_id: str
    monster_actor_id: str
    tamer_level: int
    monster_level: int
    night_rank: str
    tamed_at_ms: int


def night_rank(actor: CombatantState) -> str | None:
    rank = actor.metadata.get("night_rank")
    if rank is None:
        return None
    if rank not in {CIVIS_NOCTE, DOMINUS_NOCTE}:
        raise RuntimeError(f"unknown Night rank on actor {actor.actor_id}: {rank}")
    return str(rank)


def is_night_kind(actor: CombatantState) -> bool:
    return night_rank(actor) is not None


def night_combat_bonus(actor: CombatantState) -> float:
    rank = night_rank(actor)
    if rank is None:
        return 0.0
    if rank == CIVIS_NOCTE:
        return CIVIS_NOCTE_COMBAT_BONUS
    return DOMINUS_NOCTE_COMBAT_BONUS


def become_civis_nocte(
    actor: CombatantState,
    *,
    master_actor_id: str,
    now_ms: int,
) -> CivisNocteTransformation:
    if not actor.alive:
        raise ValueError("a defeated actor cannot become Civis Nocte")
    if night_rank(actor) is not None:
        raise ValueError("actor already has a Night rank")
    actor.metadata.update(
        {
            "night_rank": CIVIS_NOCTE,
            "night_master_actor_id": master_actor_id,
            "night_transformed_at_ms": now_ms,
            "civis_nocte": True,
            "civis_nocte_combat_bonus": CIVIS_NOCTE_COMBAT_BONUS,
            "direct_sunlight_weakness": "lethal",
            "can_create_night_followers": False,
            "blood_feeding_restores_hp": True,
        }
    )
    return CivisNocteTransformation(
        actor.actor_id,
        master_actor_id,
        now_ms,
        CIVIS_NOCTE_COMBAT_BONUS,
        "lethal",
        False,
    )


def feed_civis_nocte(
    civis: CombatantState,
    donor: CombatantState,
    *,
    donor_hp_cost: int,
) -> BloodFeedingResolution:
    if night_rank(civis) != CIVIS_NOCTE:
        raise ValueError("only a Civis Nocte can use this feeding rule")
    if not civis.alive or not donor.alive:
        raise ValueError("both feeder and donor must be alive")
    if civis.actor_id == donor.actor_id:
        raise ValueError("Civis Nocte feeding requires another actor")
    if civis.location_id is None or civis.location_id != donor.location_id:
        raise ValueError("Civis Nocte and donor must be colocated")
    if donor_hp_cost < 1:
        raise ValueError("donor_hp_cost must be positive")
    if donor_hp_cost >= donor.hp:
        raise ValueError("feeding cannot spend the donor's final HP through this non-combat action")

    before = civis.hp
    donor.hp -= donor_hp_cost
    restored = min(
        civis.max_hp - civis.hp,
        max(1, int(round(donor_hp_cost * CIVIS_BLOOD_RECOVERY_RATIO))),
    )
    civis.hp += restored
    return BloodFeedingResolution(
        civis.actor_id,
        donor.actor_id,
        donor_hp_cost,
        civis.hp - before,
        civis.hp,
        donor.hp,
        False,
    )


def tame_lower_level_monster(
    tamer: CombatantState,
    monster: CombatantState,
    *,
    now_ms: int,
) -> NightMonsterTamingResolution:
    rank = night_rank(tamer)
    if rank is None:
        raise ValueError("monster control requires a Night-kind actor")
    if not tamer.alive or not monster.alive:
        raise ValueError("both Night tamer and monster must be alive")
    if tamer.location_id is None or tamer.location_id != monster.location_id:
        raise ValueError("Night tamer and monster must be colocated")
    if monster.kind not in {EntityKind.MONSTER, EntityKind.BOSS}:
        raise ValueError("Night monster control can only target monsters or bosses")
    if monster.metadata.get("night_tameable") is not True:
        raise ValueError("this monster is not exposed as Night-tameable")
    if monster.level >= tamer.level:
        raise ValueError("Night monster control requires the monster to be lower level than the tamer")
    if monster.metadata.get("night_tamed_by_actor_id") is not None:
        raise ValueError("monster is already controlled by a Night-kind actor")

    monster.metadata.update(
        {
            "night_tamed_by_actor_id": tamer.actor_id,
            "night_tamed_by_rank": rank,
            "night_tamed_at_ms": now_ms,
            "night_tamed": True,
        }
    )
    monster.cursor = CursorColor.YELLOW
    return NightMonsterTamingResolution(
        tamer.actor_id,
        monster.actor_id,
        tamer.level,
        monster.level,
        rank,
        now_ms,
    )


def nightfolk_state(actor: CombatantState) -> dict:
    rank = night_rank(actor)
    return {
        "actor_id": actor.actor_id,
        "night_rank": rank,
        "night_master_actor_id": actor.metadata.get("night_master_actor_id"),
        "combat_bonus": night_combat_bonus(actor),
        "direct_sunlight_weakness": actor.metadata.get("direct_sunlight_weakness"),
        "can_create_night_followers": actor.metadata.get("can_create_night_followers"),
        "blood_feeding_restores_hp": actor.metadata.get("blood_feeding_restores_hp"),
    }
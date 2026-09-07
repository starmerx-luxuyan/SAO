from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ProvenanceKind(StrEnum):
    CANON = "canon"
    CANON_INFERRED = "canon_inferred"
    SIMULATION = "simulation"
    OPTIONAL_VARIANT = "optional_variant"


@dataclass(slots=True, frozen=True)
class Provenance:
    kind: ProvenanceKind
    sources: tuple[str, ...] = ()
    notes: str = ""


CANON = Provenance(ProvenanceKind.CANON)
SIMULATION = Provenance(ProvenanceKind.SIMULATION)


class EntityKind(StrEnum):
    PLAYER = "player"
    NPC = "npc"
    MONSTER = "monster"
    BOSS = "boss"


class CursorColor(StrEnum):
    GREEN = "green"
    ORANGE = "orange"
    YELLOW = "yellow"
    RED = "red"


class DamageType(StrEnum):
    SLASH = "slash"
    THRUST = "thrust"
    BLUNT = "blunt"
    MIXED = "mixed"


class WeaponClass(StrEnum):
    ONE_HAND_SWORD = "one_hand_sword"
    RAPIER = "rapier"
    DAGGER = "dagger"
    ONE_HAND_CURVED_SWORD = "one_hand_curved_sword"
    KATANA = "katana"
    MACE = "mace"
    TWO_HAND_SWORD = "two_hand_sword"
    TWO_HAND_AXE = "two_hand_axe"
    SPEAR = "spear"
    THROWING_BLADE = "throwing_blade"
    MARTIAL_ARTS = "martial_arts"
    OTHER = "other"


class ItemKind(StrEnum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SHIELD = "shield"
    CONSUMABLE = "consumable"
    MATERIAL = "material"
    FOOD = "food"
    QUEST = "quest"
    TOOL = "tool"
    MISC = "misc"


class EnhancementTrack(StrEnum):
    SHARPNESS = "sharpness"
    QUICKNESS = "quickness"
    ACCURACY = "accuracy"
    HEAVINESS = "heaviness"
    DURABILITY = "durability"


class SkillKind(StrEnum):
    WEAPON = "weapon"
    ARMOR = "armor"
    SUPPORT = "support"
    LIFE = "life"
    EXTRA = "extra"
    UNIQUE = "unique"


class StatusType(StrEnum):
    REGEN = "regen"
    POISON = "poison"
    BLEED = "bleed"
    PARALYSIS = "paralysis"
    SILENCE = "silence"
    STUN = "stun"
    STAGGER = "stagger"
    SLOW = "slow"
    BUFF = "buff"
    DEBUFF = "debuff"


class ConsumableEffect(StrEnum):
    HEAL_OVER_TIME = "heal_over_time"
    HEAL_FULL = "heal_full"
    CURE = "cure"
    TELEPORT = "teleport"
    CORRIDOR = "corridor"


class DefenseMode(StrEnum):
    NONE = "none"
    EVADE = "evade"
    GUARD = "guard"
    PARRY = "parry"
    AUTO = "auto"


class SwordSkillPhase(StrEnum):
    READY = "ready"
    WINDUP = "windup"
    COMMITTED = "committed"
    ACTIVE = "active"
    POST_MOTION = "post_motion"


class ZoneKind(StrEnum):
    SAFE_TOWN = "safe_town"
    FIELD = "field"
    DUNGEON = "dungeon"
    LABYRINTH = "labyrinth"
    BOSS_ROOM = "boss_room"


@dataclass(slots=True, frozen=True)
class SkillDefinition:
    skill_id: str
    name: str
    kind: SkillKind
    description: str = ""
    prerequisites: tuple[str, ...] = ()
    provenance: Provenance = CANON


@dataclass(slots=True, frozen=True)
class SwordSkillDefinition:
    skill_id: str
    name: str
    weapon_class: WeaponClass
    prerequisite_proficiency: float
    hits: tuple[float, ...]
    windup_ms: int
    active_ms: int
    post_motion_ms: int
    accuracy_modifier: float = 0.0
    lunge_m: float = 0.0
    stagger: float = 0.0
    provenance: Provenance = SIMULATION

    @property
    def total_multiplier(self) -> float:
        return sum(self.hits)


@dataclass(slots=True, frozen=True)
class ItemTemplate:
    template_id: str
    name: str
    kind: ItemKind
    weight: float = 0.0
    stack_limit: int = 1
    base_value_col: int | None = None
    tags: tuple[str, ...] = ()
    provenance: Provenance = SIMULATION


@dataclass(slots=True, frozen=True)
class WeaponTemplate(ItemTemplate):
    weapon_class: WeaponClass = WeaponClass.OTHER
    damage_type: DamageType = DamageType.MIXED
    attack_min: int = 1
    attack_max: int = 2
    required_level: int = 1
    required_strength: int = 1
    base_durability: int = 100
    base_speed_ms: int = 700
    reach_m: float = 1.5
    bonus_strength: int = 0
    bonus_agility: int = 0


@dataclass(slots=True, frozen=True)
class ArmorTemplate(ItemTemplate):
    armor: int = 0
    base_durability: int = 100
    slot: str = "body"


@dataclass(slots=True, frozen=True)
class ConsumableTemplate(ItemTemplate):
    effect: ConsumableEffect = ConsumableEffect.HEAL_OVER_TIME
    magnitude: int = 0
    duration_ms: int = 0
    cooldown_ms: int = 0
    requires_voice: bool = False
    status_tags: tuple[StatusType, ...] = ()


@dataclass(slots=True)
class ItemInstance:
    instance_id: str
    template_id: str
    owner_id: str | None = None
    quantity: int = 1
    durability: int | None = None
    max_durability: int | None = None
    enhancement_attempts_used: int = 0
    max_enhancement_attempts: int = 0
    enhancements: dict[EnhancementTrack, int] = field(default_factory=dict)
    maker_id: str | None = None
    quality: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def broken(self) -> bool:
        return self.durability is not None and self.durability <= 0

    @property
    def enhancement_end_product(self) -> bool:
        return self.max_enhancement_attempts > 0 and self.enhancement_attempts_used >= self.max_enhancement_attempts


@dataclass(slots=True)
class StatusEffectState:
    effect_id: str
    status_type: StatusType
    source_id: str | None
    remaining_ms: int
    magnitude: float = 0.0
    tick_interval_ms: int = 1000
    until_next_tick_ms: int = 1000
    stack_key: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class CombatantState:
    actor_id: str
    name: str
    kind: EntityKind
    level: int
    max_hp: int
    hp: int
    strength: int
    agility: int
    armor: int = 0
    evasion: int = 0
    cursor: CursorColor = CursorColor.GREEN
    col: int = 0
    skill_proficiencies: dict[str, float] = field(default_factory=dict)
    equipped_skills: list[str] = field(default_factory=list)
    inventory: dict[str, ItemInstance] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)
    statuses: list[StatusEffectState] = field(default_factory=list)
    cooldowns_until_ms: dict[str, int] = field(default_factory=dict)
    party_id: str | None = None
    guild_id: str | None = None
    location_id: str | None = None
    recovery_until_ms: int = 0
    committed_until_ms: int = 0
    ai_reaction_until_ms: int = 0
    alive: bool = True
    infamy: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def clamp_hp(self) -> None:
        self.hp = max(0, min(self.max_hp, self.hp))
        self.alive = self.hp > 0


@dataclass(slots=True)
class CombatEvent:
    time_ms: int
    event_type: str
    actor_id: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EncounterState:
    encounter_id: str
    participants: dict[str, CombatantState]
    zone_id: str
    time_ms: int = 0
    safe_zone: bool = False
    anti_crystal: bool = False
    threat: dict[str, dict[str, float]] = field(default_factory=dict)
    last_attacker_by_target: dict[str, str] = field(default_factory=dict)
    last_attack_time_by_target: dict[str, int] = field(default_factory=dict)
    events: list[CombatEvent] = field(default_factory=list)


@dataclass(slots=True)
class PartyState:
    party_id: str
    leader_id: str
    member_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RaidState:
    raid_id: str
    leader_id: str
    party_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FloorState:
    number: int
    unlocked: bool = False
    main_town_gate_active: bool = False
    floor_boss_defeated: bool = False
    floor_boss_defeated_at_ms: int | None = None
    scheduled_gate_activation_at_ms: int | None = None
    discovered_locations: set[str] = field(default_factory=set)


@dataclass(slots=True)
class WorldState:
    now_ms: int = 0
    floors: dict[int, FloorState] = field(default_factory=dict)
    parties: dict[str, PartyState] = field(default_factory=dict)
    raids: dict[str, RaidState] = field(default_factory=dict)
    global_flags: dict[str, Any] = field(default_factory=dict)

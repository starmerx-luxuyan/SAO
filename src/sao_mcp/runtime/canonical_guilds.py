from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.domain.models import CombatantState, CursorColor, EntityKind
from sao_mcp.rules.progression import default_max_hp, experience_to_reach_level
from sao_mcp.rules.relationships import GuildState, SharedStorage


PROGRESSIVE_2 = "Sword Art Online Progressive Volume 2: Concerto of Black and White"
DKB_GUILD_ID = "dragon_knights_brigade"
ALS_GUILD_ID = "aincrad_liberation_squad"
LIND_ACTOR_ID = "pc_lind"
KIBAOU_ACTOR_ID = "pc_kibaou"


@dataclass(slots=True, frozen=True)
class CanonGuildSpec:
    guild_id: str
    name: str
    leader_actor_id: str
    leader_name: str
    leader_role: str
    emblem: str


PROGRESSIVE_CLEARING_GUILDS = (
    CanonGuildSpec(
        DKB_GUILD_ID,
        "Dragon Knights Brigade",
        LIND_ACTOR_ID,
        "Lind",
        "founder_and_guild_leader",
        "DKB",
    ),
    CanonGuildSpec(
        ALS_GUILD_ID,
        "Aincrad Liberation Squad",
        KIBAOU_ACTOR_ID,
        "Kibaou",
        "founder_and_guild_leader",
        "ALS",
    ),
)


def _materialize_named_leader(runtime, spec: CanonGuildSpec) -> CombatantState:
    existing = runtime.actors.get(spec.leader_actor_id)
    if existing is not None:
        if existing.kind is not EntityKind.PLAYER or existing.name != spec.leader_name:
            raise RuntimeError(
                f"canonical guild leader actor {spec.leader_actor_id} conflicts with {spec.leader_name}"
            )
        return existing

    # Exact Floor 8 combat levels/stats are not published in the source used here. Keep the
    # actor mechanically valid but location-unresolved and label the numeric profile as simulation.
    level = 28
    strength = 10 + (level - 1) * 2
    agility = 10 + (level - 1) * 2
    hp = default_max_hp(level, strength, agility)
    actor = CombatantState(
        actor_id=spec.leader_actor_id,
        name=spec.leader_name,
        kind=EntityKind.PLAYER,
        level=level,
        max_hp=hp,
        hp=hp,
        strength=strength,
        agility=agility,
        cursor=CursorColor.GREEN,
        location_id=None,
        skill_proficiencies={},
        equipped_skills=[],
        metadata={
            "named_player": True,
            "progressive_clearing_guild_leader": True,
            "guild_leadership_role": spec.leader_role,
            "identity_provenance": "canon",
            "guild_leadership_provenance": "canon",
            "guild_source": PROGRESSIVE_2,
            "combat_profile_provenance": "simulation_floor8_clearer_calibration",
            "world_location_unresolved": True,
            "experience": experience_to_reach_level(level),
        },
    )
    runtime.actors[actor.actor_id] = actor
    return actor


def _register_stable_guild(runtime, spec: CanonGuildSpec, leader: CombatantState) -> GuildState:
    relationships = runtime.relationships
    if spec.guild_id in relationships.guilds:
        raise RuntimeError(f"canonical guild {spec.guild_id} was registered twice")
    if any(guild.name.casefold() == spec.name.casefold() for guild in relationships.guilds.values()):
        raise RuntimeError(f"canonical guild name {spec.name!r} collides with another GuildState")
    if leader.guild_id is not None:
        raise RuntimeError(f"canonical guild leader {leader.actor_id} already belongs to {leader.guild_id}")

    storage_id = f"guildstore_{spec.guild_id}"
    if storage_id in relationships.storages:
        raise RuntimeError(f"canonical guild storage {storage_id} already exists")
    storage = SharedStorage(storage_id=storage_id, storage_kind="guild", member_ids=[leader.actor_id])
    guild = GuildState(
        guild_id=spec.guild_id,
        name=spec.name,
        leader_id=leader.actor_id,
        member_ids=[leader.actor_id],
        emblem=spec.emblem,
        # No canon guild-tax percentage is established here. Zero avoids inventing an economy effect.
        tax_rate=0.0,
        storage_id=storage_id,
    )
    relationships.storages[storage_id] = storage
    relationships.guilds[spec.guild_id] = guild
    leader.guild_id = spec.guild_id
    leader.metadata["guild_emblem"] = spec.emblem
    return guild


def _validate_registered_guild(runtime, spec: CanonGuildSpec, leader: CombatantState) -> GuildState:
    relationships = runtime.relationships
    guild = relationships.guilds[spec.guild_id]
    if guild.name != spec.name or guild.leader_id != leader.actor_id:
        raise RuntimeError(f"canonical GuildState {spec.guild_id} no longer matches its source identity")
    if leader.guild_id != spec.guild_id or leader.actor_id not in guild.member_ids:
        raise RuntimeError(f"canonical leader {leader.actor_id} is not a real member of {spec.guild_id}")
    if guild.storage_id not in relationships.storages:
        raise RuntimeError(f"canonical guild {spec.guild_id} has no authoritative shared storage")
    storage = relationships.storages[guild.storage_id]
    if storage.storage_kind != "guild" or leader.actor_id not in storage.member_ids:
        raise RuntimeError(f"canonical guild {spec.guild_id} storage membership is inconsistent")
    return guild


def install_progressive_clearing_guilds(runtime) -> dict[str, GuildState]:
    """Install/verify the canon early-clearing guild identities in the real relationship runtime."""
    if not hasattr(runtime, "relationships"):
        raise RuntimeError("progressive clearing guilds require the relationship runtime")

    present = {spec.guild_id for spec in PROGRESSIVE_CLEARING_GUILDS if spec.guild_id in runtime.relationships.guilds}
    expected = {spec.guild_id for spec in PROGRESSIVE_CLEARING_GUILDS}
    if present and present != expected:
        raise RuntimeError("Progressive clearing guild state is partially installed")

    result: dict[str, GuildState] = {}
    for spec in PROGRESSIVE_CLEARING_GUILDS:
        leader = _materialize_named_leader(runtime, spec)
        if spec.guild_id in runtime.relationships.guilds:
            guild = _validate_registered_guild(runtime, spec, leader)
        else:
            guild = _register_stable_guild(runtime, spec, leader)
        result[spec.guild_id] = guild
    return result

from __future__ import annotations

from sao_mcp.domain.models import CombatantState, CursorColor, PartyState, RaidState


MAX_PARTY_MEMBERS = 6
MAX_RAID_PARTIES = 8


def add_party_member(party: PartyState, actor_id: str) -> None:
    if actor_id in party.member_ids:
        return
    if len(party.member_ids) >= MAX_PARTY_MEMBERS:
        raise ValueError("a party may contain at most six members")
    party.member_ids.append(actor_id)


def add_raid_party(raid: RaidState, party_id: str) -> None:
    if party_id in raid.party_ids:
        return
    if len(raid.party_ids) >= MAX_RAID_PARTIES:
        raise ValueError("a raid may contain at most eight parties")
    raid.party_ids.append(party_id)


def authorized_duel_between(attacker: CombatantState, target: CombatantState) -> bool:
    opponents = attacker.metadata.get("authorized_duel_opponents", ())
    return target.actor_id in opponents


def hostile_action_is_criminal(attacker: CombatantState, target: CombatantState, *, safe_zone: bool) -> bool:
    if attacker.actor_id == target.actor_id:
        return False
    if authorized_duel_between(attacker, target):
        return False
    if safe_zone:
        return False
    if target.cursor is CursorColor.ORANGE:
        return False
    return attacker.cursor is CursorColor.GREEN and target.cursor is CursorColor.GREEN


def apply_unlawful_hostile_action(
    attacker: CombatantState,
    target: CombatantState,
    *,
    safe_zone: bool,
    severity: int = 1,
) -> bool:
    if not hostile_action_is_criminal(attacker, target, safe_zone=safe_zone):
        return False
    attacker.cursor = CursorColor.ORANGE
    attacker.infamy += max(1, severity)
    return True

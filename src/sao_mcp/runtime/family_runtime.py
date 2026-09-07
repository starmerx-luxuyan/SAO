from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

from sao_mcp.rules.family import DivorceMode, DivorceProposal, DivorceStatus
from sao_mcp.rules.inventory import personal_carry_capacity, recompute_equipment_stats
from sao_mcp.runtime.community_runtime import CommunityAincradRuntime


class FamilyCommunityAincradRuntime(CommunityAincradRuntime):
    """Community runtime plus canonical marriage dissolution/allocation semantics."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.divorce_proposals: dict[str, DivorceProposal] = {}

    def _marriage_partners(self, marriage_id: str):
        marriage = self.relationships.marriages[marriage_id]
        if not marriage.active:
            raise ValueError("marriage is no longer active")
        a_id, b_id = marriage.partner_ids
        return marriage, self.actors[a_id], self.actors[b_id]

    def propose_divorce(
        self,
        actor_id: str,
        *,
        mode: DivorceMode | str = DivorceMode.AUTO_PERCENTAGE,
        proposer_percent: int = 50,
        selected_item_ids: list[str] | None = None,
    ) -> DivorceProposal:
        marriage = self.relationships.marriage_for(actor_id)
        if marriage is None:
            raise ValueError("actor is not married")
        target_id = marriage.partner_ids[1] if marriage.partner_ids[0] == actor_id else marriage.partner_ids[0]
        proposal = DivorceProposal.create(
            marriage.marriage_id,
            actor_id,
            target_id,
            mode,
            proposer_percent=proposer_percent,
            selected_item_ids=selected_item_ids,
            now_ms=self.world.now_ms,
        )
        self.divorce_proposals[proposal.proposal_id] = proposal
        if proposal.mode is DivorceMode.SURRENDER_ALL:
            self._finalize_divorce(proposal, reason="unconditional 0/100 surrender")
        return proposal

    def accept_divorce(self, proposal_id: str, target_id: str) -> DivorceProposal:
        proposal = self.divorce_proposals[proposal_id]
        if proposal.status is not DivorceStatus.PENDING or proposal.target_id != target_id:
            raise ValueError("divorce proposal cannot be accepted by this player")
        self._finalize_divorce(proposal, reason="mutual allocation agreement")
        return proposal

    def decline_divorce(self, proposal_id: str, target_id: str) -> DivorceProposal:
        proposal = self.divorce_proposals[proposal_id]
        if proposal.status is not DivorceStatus.PENDING or proposal.target_id != target_id:
            raise ValueError("divorce proposal cannot be declined by this player")
        proposal.status = DivorceStatus.DECLINED
        return proposal

    def _item_value(self, item) -> float:
        template = self.catalog.item(item.template_id)
        base = template.base_value_col
        if base is None:
            if item.template_id in self.catalog.weapons:
                weapon = self.catalog.weapons[item.template_id]
                base = max(10, int(round((weapon.attack_min + weapon.attack_max) * 1.8)))
            elif item.template_id in self.catalog.armors:
                base = max(8, self.catalog.armors[item.template_id].armor * 2)
            else:
                base = 5
        condition = 1.0
        if item.durability is not None and item.max_durability:
            condition = max(0.15, item.durability / item.max_durability)
        enhancement = 1.0 + sum(item.enhancements.values()) * 0.12
        return float(base) * max(1, item.quantity) * max(0.5, item.quality) * condition * enhancement

    def _auto_percentage_items(self, pool: dict, proposer_percent: int) -> set[str]:
        if proposer_percent <= 0:
            return set()
        if proposer_percent >= 100:
            return set(pool)
        values = {item_id: self._item_value(item) for item_id, item in pool.items()}
        target_value = sum(values.values()) * proposer_percent / 100.0
        chosen: set[str] = set()
        current = 0.0
        for item_id in sorted(values, key=lambda key: (-values[key], key)):
            value = values[item_id]
            if abs((current + value) - target_value) <= abs(current - target_value):
                chosen.add(item_id)
                current += value
        return chosen

    def _ground_drop(self, actor, item, reason: str) -> None:
        location_id = actor.location_id or "unknown"
        ground = self.world.global_flags.setdefault("ground_drops", {})
        rows = ground.setdefault(location_id, [])
        row = asdict(item)
        row["owner_id"] = None
        row["drop_reason"] = reason
        row["former_actor_id"] = actor.actor_id
        rows.append(row)

    def _fit_personal_capacity(self, actor, inventory: dict, *, reason: str) -> dict:
        actor.metadata.pop("shared_carry_capacity_override", None)
        capacity = personal_carry_capacity(actor)
        equipped_ids = set(actor.equipment.values())
        ordered = sorted(
            inventory.items(),
            key=lambda pair: (
                0 if pair[0] in equipped_ids else 1,
                -self._item_value(pair[1]),
                pair[0],
            ),
        )
        kept: dict = {}
        used = 0.0
        for item_id, item in ordered:
            template = self.catalog.item(item.template_id)
            weight = template.weight * max(1, item.quantity)
            if used + weight <= capacity + 1e-9:
                kept[item_id] = item
                used += weight
            else:
                self._ground_drop(actor, item, reason)
        actor.equipment = {
            slot: item_id for slot, item_id in actor.equipment.items() if item_id in kept
        }
        return kept

    def _close_marriage(self, marriage, a, b, *, reason: str) -> None:
        marriage.active = False
        marriage.ended_at_ms = self.world.now_ms
        marriage.end_reason = reason
        for actor, spouse in ((a, b), (b, a)):
            self.relationships.marriage_by_actor.pop(actor.actor_id, None)
            actor.metadata.pop("marriage_id", None)
            actor.metadata.pop("spouse_id", None)
            actor.metadata.pop("shared_carry_capacity_override", None)
        recompute_equipment_stats(a, self.catalog)
        recompute_equipment_stats(b, self.catalog)

    def _finalize_divorce(self, proposal: DivorceProposal, *, reason: str) -> None:
        marriage, a, b = self._marriage_partners(proposal.marriage_id)
        proposer = a if a.actor_id == proposal.proposer_id else b
        target = b if proposer is a else a
        pool = proposer.inventory

        if proposal.mode is DivorceMode.SURRENDER_ALL:
            proposer_ids: set[str] = set()
        elif proposal.mode is DivorceMode.ITEM_SELECTION:
            unknown = [item_id for item_id in proposal.selected_item_ids if item_id not in pool]
            if unknown:
                raise ValueError(f"selected divorce items are missing: {unknown}")
            proposer_ids = set(proposal.selected_item_ids)
        else:
            proposer_ids = self._auto_percentage_items(pool, proposal.proposer_percent)

        proposer_inventory = {
            item_id: deepcopy(item) for item_id, item in pool.items() if item_id in proposer_ids
        }
        target_inventory = {
            item_id: deepcopy(item) for item_id, item in pool.items() if item_id not in proposer_ids
        }
        for item in proposer_inventory.values():
            item.owner_id = proposer.actor_id
        for item in target_inventory.values():
            item.owner_id = target.actor_id

        wallet = marriage.shared_wallet_col
        proposer_col = wallet * proposal.proposer_percent // 100
        target_col = wallet - proposer_col
        proposer.col = proposer_col
        target.col = target_col
        proposer.inventory = self._fit_personal_capacity(
            proposer, proposer_inventory, reason="divorce capacity overflow"
        )
        target.inventory = self._fit_personal_capacity(
            target, target_inventory, reason="divorce capacity overflow"
        )
        proposal.status = DivorceStatus.COMPLETED
        proposal.completed_at_ms = self.world.now_ms
        self._close_marriage(marriage, a, b, reason=reason)

    def _inherit_marriage_on_death(self, dead_actor_id: str) -> dict | None:
        marriage = self.relationships.marriage_for(dead_actor_id)
        if marriage is None:
            return None
        dead = self.actors[dead_actor_id]
        survivor_id = marriage.partner_ids[1] if marriage.partner_ids[0] == dead_actor_id else marriage.partner_ids[0]
        survivor = self.actors[survivor_id]
        shared_pool = survivor.inventory
        survivor_inventory = {item_id: deepcopy(item) for item_id, item in shared_pool.items()}
        for item in survivor_inventory.values():
            item.owner_id = survivor.actor_id
        survivor.col = marriage.shared_wallet_col
        dead.col = 0
        dead.inventory = {}
        dead.equipment = {}
        survivor.inventory = self._fit_personal_capacity(
            survivor, survivor_inventory, reason="spouse death inheritance capacity overflow"
        )
        self._close_marriage(marriage, dead, survivor, reason="partner permanent death")
        return {
            "marriageId": marriage.marriage_id,
            "deadActorId": dead_actor_id,
            "survivorId": survivor_id,
            "survivorCol": survivor.col,
            "survivorItemCount": len(survivor.inventory),
        }

    def _finalize_expired_deaths(self, encounter) -> None:
        candidates = [
            actor.actor_id
            for actor in encounter.participants.values()
            if actor.metadata.get("death_state") == "end_phase"
        ]
        super()._finalize_expired_deaths(encounter)
        for actor_id in candidates:
            actor = self.actors.get(actor_id)
            if actor and actor.metadata.get("death_state") == "permanent":
                result = self._inherit_marriage_on_death(actor_id)
                if result:
                    self._append(
                        encounter,
                        "marriage_ended_by_death",
                        None,
                        actor_id,
                        **result,
                    )

    def dump_family_state(self) -> dict:
        return {
            "divorce_proposals": {
                proposal_id: proposal.dump()
                for proposal_id, proposal in self.divorce_proposals.items()
            }
        }

    def load_family_state(self, payload: dict) -> None:
        self.divorce_proposals = {}
        for proposal_id, row in payload.get("divorce_proposals", {}).items():
            self.divorce_proposals[proposal_id] = DivorceProposal(
                proposal_id=row["proposal_id"],
                marriage_id=row["marriage_id"],
                proposer_id=row["proposer_id"],
                target_id=row["target_id"],
                mode=DivorceMode(row["mode"]),
                proposer_percent=int(row["proposer_percent"]),
                selected_item_ids=list(row.get("selected_item_ids", [])),
                status=DivorceStatus(row.get("status", "pending")),
                created_at_ms=int(row.get("created_at_ms", 0)),
                completed_at_ms=row.get("completed_at_ms"),
            )

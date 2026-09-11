from __future__ import annotations

from dataclasses import asdict
from typing import Any

from sao_mcp.corpus.monsters import AINCRAD_MONSTERS
from sao_mcp.domain.models import EntityKind
from sao_mcp.rules.economy_loop import MarketItemClass, market_item_class
from sao_mcp.rules.quest_ecology import (
    MARKET_CONTRACT_DURATION_MS,
    MONSTER_CONTRACT_DURATION_MS,
    QUEST_ECOLOGY_TICK_MS,
    QUEST_ECOLOGY_WORLD_EVENT_RULE_ID,
    QuestContractSource,
    QuestContractState,
)
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.world_events import WorldEventStatus
from sao_mcp.runtime.monster_ecology_runtime import MonsterEcologyAincradRuntime


QUEST_ECOLOGY_SCHEMA = "quest-ecology.v1"


class QuestEcologyAincradRuntime(MonsterEcologyAincradRuntime):
    """Living quest contracts whose lifecycle is authoritative WorldEvent state."""

    def __init__(self, *, seed: int | None = None, catalog=None) -> None:
        super().__init__(seed=seed, catalog=catalog)
        self.quest_contracts: dict[str, QuestContractState] = {}
        self.quest_ecology_history: list[dict[str, Any]] = []
        self.quest_contract_sequence = 0
        self.quest_ecology_ecology_cursor = len(self.monster_ecology_history)
        self.quest_ecology_market_cursor = len(self.economy.market_history)
        self.next_quest_ecology_tick_at_ms = self.world.now_ms + QUEST_ECOLOGY_TICK_MS
        self.register_world_event_rule(
            QUEST_ECOLOGY_WORLD_EVENT_RULE_ID,
            self._discover_no_automatic_contract_occurrences,
            self._resolve_no_automatic_contract_occurrences,
        )
        self.register_defeat_hook(self._on_quest_contract_named_defeat)
        self.register_world_advance_hook(self._resolve_due_quest_ecology)

    @staticmethod
    def _discover_no_automatic_contract_occurrences() -> tuple[str, ...]:
        # Contract generation is driven by ecology/economy state below. WorldEvent owns only lifecycle.
        return ()

    @staticmethod
    def _resolve_no_automatic_contract_occurrences(occurrence_id: str):
        raise RuntimeError(f"quest ecology occurrence must be transitioned by contract authority: {occurrence_id}")

    def _record_quest_ecology(self, event: str, *, at_ms: int | None = None, **fields: Any) -> None:
        self.quest_ecology_history.append(
            {"event": event, **fields, "at_ms": self.world.now_ms if at_ms is None else int(at_ms)}
        )

    def _occurrence(self, contract: QuestContractState):
        return self.world_events.occurrences[contract.occurrence_id]

    def _active_contract(self, contract: QuestContractState) -> bool:
        return self._occurrence(contract).status is WorldEventStatus.ACTIVE

    def _install_contract_definition(self, contract: QuestContractState) -> None:
        floor_number = self.world_map.locations[contract.posting_location_id].floor_number
        definition = contract.quest_definition(floor_number=floor_number)
        existing = self.quests.definitions.get(contract.quest_id)
        if existing is not None and existing != definition:
            raise RuntimeError(f"quest contract definition collision: {contract.quest_id}")
        self.quests.definitions[contract.quest_id] = definition

    def _publish_contract(
        self,
        *,
        source_kind: QuestContractSource,
        source_ref_id: str,
        source_location_id: str,
        posting_location_id: str,
        objective_kind: QuestObjectiveKind,
        target_id: str,
        required: int,
        duration_ms: int,
        reward_col: int,
        reward_xp: int,
    ) -> QuestContractState:
        if source_location_id not in self.world_map.locations or posting_location_id not in self.world_map.locations:
            raise KeyError("quest contract references unknown world location")
        if not self.world_map.locations[posting_location_id].safe_zone:
            raise ValueError("quest ecology contracts must be posted at a safe location")
        self.quest_contract_sequence += 1
        suffix = f"{self.quest_contract_sequence:06d}"
        contract_id = f"quest_ecology_{suffix}"
        occurrence_id = f"quest_ecology_event_{suffix}"
        contract = QuestContractState(
            contract_id=contract_id,
            occurrence_id=occurrence_id,
            source_kind=source_kind,
            source_ref_id=source_ref_id,
            source_location_id=source_location_id,
            posting_location_id=posting_location_id,
            quest_id=contract_id,
            objective_kind=objective_kind,
            target_id=target_id,
            required=required,
            created_at_ms=self.world.now_ms,
            expires_at_ms=self.world.now_ms + duration_ms,
            reward_col=reward_col,
            reward_xp=reward_xp,
        )
        self.quest_contracts[contract_id] = contract
        self._install_contract_definition(contract)
        self.plan_world_event(
            occurrence_id,
            QUEST_ECOLOGY_WORLD_EVENT_RULE_ID,
            payload={
                "contract_id": contract_id,
                "source_kind": source_kind.value,
                "source_ref_id": source_ref_id,
                "source_location_id": source_location_id,
                "posting_location_id": posting_location_id,
                "expires_at_ms": contract.expires_at_ms,
            },
        )
        self.transition_world_event(
            occurrence_id,
            WorldEventStatus.ACTIVE,
            payload={"contract_id": contract_id},
        )
        self._record_quest_ecology(
            "contract_published",
            contract_id=contract_id,
            occurrence_id=occurrence_id,
            source_kind=source_kind.value,
            source_ref_id=source_ref_id,
            source_location_id=source_location_id,
            posting_location_id=posting_location_id,
            target_id=target_id,
            required=required,
            expires_at_ms=contract.expires_at_ms,
        )
        return contract

    def _claimant_rows(self, contract: QuestContractState) -> dict[str, dict[str, Any]]:
        rows = {}
        for actor_id, quests in self.quests.progress_by_actor.items():
            progress = quests.get(contract.quest_id)
            if progress is not None:
                rows[actor_id] = asdict(progress)
        return rows

    def _terminate_other_claimants(
        self,
        contract: QuestContractState,
        *,
        status: str,
        reason: str,
        keep_actor_ids: tuple[str, ...] = (),
    ) -> None:
        keep = set(keep_actor_ids)
        for actor_id, quests in self.quests.progress_by_actor.items():
            progress = quests.get(contract.quest_id)
            if (
                progress is None
                or actor_id in keep
                or progress.claimed
                or progress.terminated
            ):
                continue
            self.quests.terminate(
                actor_id,
                contract.quest_id,
                status=status,
                at_ms=self.world.now_ms,
                reason=reason,
            )
            self._record_quest_ecology(
                "claimant_terminated",
                contract_id=contract.contract_id,
                actor_id=actor_id,
                status=status,
                reason=reason,
            )

    def _resolve_contract(
        self,
        contract: QuestContractState,
        *,
        winner_kind: str,
        winner_ids: tuple[str, ...] = (),
        winner_ref_id: str | None = None,
    ) -> None:
        if not self._active_contract(contract):
            return
        contract.mark_winner(
            winner_kind=winner_kind,
            winner_ids=winner_ids,
            winner_ref_id=winner_ref_id,
        )
        self.transition_world_event(
            contract.occurrence_id,
            WorldEventStatus.RESOLVED,
            payload={
                "winner_kind": winner_kind,
                "winner_ids": list(winner_ids),
                "winner_ref_id": winner_ref_id,
                "world_progress": contract.world_progress,
            },
        )
        self._terminate_other_claimants(
            contract,
            status="failed",
            reason=f"resolved_by:{winner_kind}",
            keep_actor_ids=winner_ids,
        )
        self._record_quest_ecology(
            "contract_resolved",
            contract_id=contract.contract_id,
            winner_kind=winner_kind,
            winner_ids=list(winner_ids),
            winner_ref_id=winner_ref_id,
            world_progress=contract.world_progress,
        )

    def _interrupt_contract(self, contract: QuestContractState, *, reason: str) -> None:
        if not self._active_contract(contract):
            return
        self.transition_world_event(
            contract.occurrence_id,
            WorldEventStatus.INTERRUPTED,
            payload={"reason": reason, "world_progress": contract.world_progress},
        )
        self._terminate_other_claimants(
            contract,
            status="interrupted",
            reason=reason,
        )
        self._record_quest_ecology(
            "contract_interrupted", contract_id=contract.contract_id, reason=reason
        )

    def _expire_contracts(self, at_ms: int) -> None:
        for contract in sorted(self.quest_contracts.values(), key=lambda row: row.contract_id):
            if not self._active_contract(contract) or contract.expires_at_ms > at_ms:
                continue
            self.transition_world_event(
                contract.occurrence_id,
                WorldEventStatus.FAILED,
                payload={"reason": "expired", "world_progress": contract.world_progress},
            )
            self._terminate_other_claimants(
                contract,
                status="expired",
                reason="contract_expired",
            )
            self._record_quest_ecology(
                "contract_expired",
                at_ms=at_ms,
                contract_id=contract.contract_id,
                world_progress=contract.world_progress,
            )

    def _advance_contract_progress(
        self,
        contract: QuestContractState,
        quantity: int,
        *,
        source_kind: str,
        source_ref_id: str,
    ) -> int:
        if not self._active_contract(contract):
            return 0
        added = contract.advance_world_progress(quantity)
        if added:
            self._record_quest_ecology(
                "contract_world_progress",
                contract_id=contract.contract_id,
                source_kind=source_kind,
                source_ref_id=source_ref_id,
                quantity=added,
                world_progress=contract.world_progress,
                required=contract.required,
            )
        return added

    def _on_quest_contract_named_defeat(self, encounter, target, killer_id: str | None) -> None:
        monster_id = target.metadata.get("ecology_monster_id")
        if target.kind is not EntityKind.MONSTER or not monster_id:
            return
        for contract in sorted(self.quest_contracts.values(), key=lambda row: row.contract_id):
            if (
                not self._active_contract(contract)
                or contract.objective_kind is not QuestObjectiveKind.KILL
                or contract.target_id != monster_id
                or contract.source_location_id != target.location_id
            ):
                continue
            self._advance_contract_progress(
                contract,
                1,
                source_kind="named_monster_defeat",
                source_ref_id=killer_id or "unknown",
            )
            if contract.world_progress < contract.required:
                continue
            eligible: list[str] = []
            killer = encounter.participants.get(killer_id) if killer_id else None
            if killer is not None and killer.kind is EntityKind.PLAYER:
                for recipient in self._reward_recipients(encounter, killer):
                    progress = self.quests.progress_by_actor.get(recipient.actor_id, {}).get(contract.quest_id)
                    if (
                        progress is not None
                        and not progress.claimed
                        and not progress.terminated
                        and self.quests.ready_to_claim(recipient, contract.quest_id)
                    ):
                        eligible.append(recipient.actor_id)
            winners = tuple(sorted(set(eligible)))
            self._resolve_contract(
                contract,
                winner_kind=("named_player" if winners else "named_outsider"),
                winner_ids=winners,
                winner_ref_id=killer_id,
            )

    def _process_background_hunt_progress(self) -> None:
        rows = self.monster_ecology_history[self.quest_ecology_ecology_cursor :]
        for row in rows:
            if row.get("event") != "background_hunt":
                continue
            location_id = str(row["location_id"])
            cohort_id = str(row["cohort_id"])
            kills = dict(row.get("kills", {}))
            for contract in sorted(self.quest_contracts.values(), key=lambda value: value.contract_id):
                if (
                    not self._active_contract(contract)
                    or contract.objective_kind is not QuestObjectiveKind.KILL
                    or contract.source_location_id != location_id
                ):
                    continue
                quantity = int(kills.get(contract.target_id, 0))
                if quantity <= 0:
                    continue
                self._advance_contract_progress(
                    contract,
                    quantity,
                    source_kind="background_population",
                    source_ref_id=cohort_id,
                )
                if contract.world_progress >= contract.required:
                    self._resolve_contract(
                        contract,
                        winner_kind="background_population",
                        winner_ref_id=cohort_id,
                    )
        self.quest_ecology_ecology_cursor = len(self.monster_ecology_history)

    def _process_background_supply_progress(self) -> None:
        rows = self.economy.market_history[self.quest_ecology_market_cursor :]
        for row in rows:
            if row.get("event") != "external_background_supply":
                continue
            location_id = str(row["location_id"])
            template_id = str(row["template_id"])
            quantity = int(row["units"])
            source = str(row["source"])
            for contract in sorted(self.quest_contracts.values(), key=lambda value: value.contract_id):
                if (
                    not self._active_contract(contract)
                    or contract.objective_kind is not QuestObjectiveKind.COLLECT
                    or contract.source_location_id != location_id
                    or contract.target_id != template_id
                    or int(row["at_ms"]) < contract.created_at_ms
                ):
                    continue
                self._advance_contract_progress(
                    contract,
                    quantity,
                    source_kind="background_supply",
                    source_ref_id=source,
                )
                if contract.world_progress >= contract.required:
                    self._resolve_contract(
                        contract,
                        winner_kind="background_supply",
                        winner_ref_id=source,
                    )
        self.quest_ecology_market_cursor = len(self.economy.market_history)

    def _has_active_source_contract(
        self,
        source_kind: QuestContractSource,
        source_location_id: str,
        target_id: str,
    ) -> bool:
        return any(
            self._active_contract(contract)
            and contract.source_kind is source_kind
            and contract.source_location_id == source_location_id
            and contract.target_id == target_id
            for contract in self.quest_contracts.values()
        )

    def _generate_monster_pressure_contracts(self) -> None:
        locations = sorted(
            {
                state.location_id
                for monster_id, state in self.monster_ecology.items()
                if self.world.floors[AINCRAD_MONSTERS[monster_id].floor_number].unlocked
            }
        )
        for location_id in locations:
            location = self.world_map.locations[location_id]
            if location.safe_zone:
                continue
            danger = self._location_danger(location_id)
            if float(danger["density_ratio"]) < 0.70:
                continue
            candidates = []
            for monster_id, state in self.monster_ecology.items():
                if state.location_id != location_id:
                    continue
                definition = AINCRAD_MONSTERS[monster_id]
                tags = set(definition.tags)
                if "field_boss" in tags or "rare_named_monster" in tags or "rare" in tags:
                    continue
                live = self._live_units(monster_id)
                if live <= 0:
                    continue
                candidates.append((-live, definition.level, monster_id))
            if not candidates:
                continue
            _, _, monster_id = min(candidates)
            if self._has_active_source_contract(
                QuestContractSource.MONSTER_PRESSURE, location_id, monster_id
            ):
                continue
            posting = self._nearest_safe_location(location_id)
            if posting is None:
                continue
            state = self.monster_ecology[monster_id]
            live = self._live_units(monster_id)
            target_floor = max(1, int(state.carrying_capacity * 0.55))
            excess = max(1, live - target_floor)
            required = max(2, min(6, (excess + 1) // 2))
            level = AINCRAD_MONSTERS[monster_id].level
            self._publish_contract(
                source_kind=QuestContractSource.MONSTER_PRESSURE,
                source_ref_id=monster_id,
                source_location_id=location_id,
                posting_location_id=posting,
                objective_kind=QuestObjectiveKind.KILL,
                target_id=monster_id,
                required=required,
                duration_ms=MONSTER_CONTRACT_DURATION_MS,
                reward_col=max(50, required * max(1, level) * 10),
                reward_xp=max(80, required * max(1, level) * 25),
            )

    def _economy_ticks_at(self, tick_ms: int) -> list[dict[str, Any]]:
        return [
            row
            for row in self.economy.market_history
            if row.get("event") == "economy_tick" and int(row["at_ms"]) == tick_ms
        ]

    def _generate_market_shortage_contracts(self, tick_ms: int) -> None:
        for row in sorted(self._economy_ticks_at(tick_ms), key=lambda value: str(value["location_id"])):
            location_id = str(row["location_id"])
            location = self.world_map.locations[location_id]
            if not location.safe_zone:
                continue
            unmet = {str(key): int(value) for key, value in row.get("background_unmet_demand_units_by_template", {}).items()}
            candidates = []
            for template_id, units in unmet.items():
                if units < 2:
                    continue
                if market_item_class(self.catalog, template_id) is not MarketItemClass.MATERIAL:
                    continue
                if self._has_active_source_contract(
                    QuestContractSource.MARKET_SHORTAGE, location_id, template_id
                ):
                    continue
                candidates.append((-units, template_id))
            if not candidates:
                continue
            neg_units, template_id = min(candidates)
            units = -neg_units
            required = max(2, min(6, units))
            reference = self.economy.reference_unit_price(location_id, template_id)
            self._publish_contract(
                source_kind=QuestContractSource.MARKET_SHORTAGE,
                source_ref_id=f"{location_id}:{template_id}",
                source_location_id=location_id,
                posting_location_id=location_id,
                objective_kind=QuestObjectiveKind.COLLECT,
                target_id=template_id,
                required=required,
                duration_ms=MARKET_CONTRACT_DURATION_MS,
                reward_col=max(30, int(round(reference * required * 1.35))),
                reward_xp=required * 25,
            )

    def _interrupt_cleared_sources(self, tick_ms: int) -> None:
        current_market = {str(row["location_id"]): row for row in self._economy_ticks_at(tick_ms)}
        for contract in sorted(self.quest_contracts.values(), key=lambda value: value.contract_id):
            if not self._active_contract(contract):
                continue
            if contract.source_kind is QuestContractSource.MONSTER_PRESSURE:
                state = self.monster_ecology[contract.target_id]
                density = self._live_units(contract.target_id) / state.carrying_capacity
                if density <= 0.35 and contract.world_progress < contract.required:
                    self._interrupt_contract(contract, reason="monster_pressure_cleared")
            elif contract.source_kind is QuestContractSource.MARKET_SHORTAGE:
                row = current_market.get(contract.source_location_id)
                if row is None:
                    continue
                unmet = row.get("background_unmet_demand_units_by_template", {})
                if int(unmet.get(contract.target_id, 0)) <= 0:
                    self._interrupt_contract(contract, reason="market_shortage_cleared")

    def advance_quest_ecology_tick(self, tick_ms: int) -> None:
        if tick_ms != self.next_quest_ecology_tick_at_ms:
            raise RuntimeError(
                f"quest ecology tick must resolve at its scheduled boundary: {tick_ms} != {self.next_quest_ecology_tick_at_ms}"
            )
        if self.world.now_ms != tick_ms:
            raise RuntimeError("quest ecology tick must resolve at authoritative current world time")
        self._process_background_hunt_progress()
        self._process_background_supply_progress()
        self._interrupt_cleared_sources(tick_ms)
        self._generate_monster_pressure_contracts()
        self._generate_market_shortage_contracts(tick_ms)
        self._expire_contracts(tick_ms)
        self.next_quest_ecology_tick_at_ms += QUEST_ECOLOGY_TICK_MS
        self.assert_quest_ecology_authority()

    def _resolve_due_quest_ecology(self, before_ms: int, after_ms: int) -> None:
        if self.next_quest_ecology_tick_at_ms == after_ms:
            self.advance_quest_ecology_tick(after_ms)
        elif self.next_quest_ecology_tick_at_ms < after_ms:
            raise RuntimeError("quest ecology tick boundary was skipped by world scheduler")
        self._expire_contracts(after_ms)

    def _next_scheduler_boundary(self, target_ms: int) -> int:
        boundary = super()._next_scheduler_boundary(target_ms)
        now = self.world.now_ms
        if now < self.next_quest_ecology_tick_at_ms <= target_ms:
            boundary = min(boundary, self.next_quest_ecology_tick_at_ms)
        expiries = [
            contract.expires_at_ms
            for contract in self.quest_contracts.values()
            if self._active_contract(contract) and now < contract.expires_at_ms <= target_ms
        ]
        if expiries:
            boundary = min(boundary, min(expiries))
        return boundary

    def accept_quest_contract(self, actor_id: str, contract_id: str):
        actor = self.actors[actor_id]
        contract = self.quest_contracts[contract_id]
        if not actor.alive or actor.metadata.get("permanent_death"):
            raise ValueError("quest contract acceptance requires a living player")
        if actor.kind is not EntityKind.PLAYER:
            raise ValueError("quest contract acceptance requires a player actor")
        if not self._active_contract(contract):
            raise ValueError("quest contract is no longer active")
        if actor.location_id != contract.posting_location_id:
            raise ValueError("quest contract must be accepted at its posting location")
        progress = self.quests.accept(actor_id, contract.quest_id, now_ms=self.world.now_ms)
        self._record_quest_ecology(
            "contract_accepted", contract_id=contract_id, actor_id=actor_id
        )
        return progress

    def claim_quest(self, actor_id: str, quest_id: str):
        contract = self.quest_contracts.get(quest_id)
        if contract is None:
            return super().claim_quest(actor_id, quest_id)
        actor = self.actors[actor_id]
        occurrence = self._occurrence(contract)
        if actor.location_id != contract.posting_location_id:
            raise ValueError("quest contract must be turned in at its posting location")
        if occurrence.status is WorldEventStatus.ACTIVE:
            if contract.objective_kind is not QuestObjectiveKind.COLLECT:
                raise ValueError("competitive kill contract has not resolved")
        elif occurrence.status is WorldEventStatus.RESOLVED:
            if actor_id not in contract.winner_ids:
                raise ValueError("quest contract was resolved by another competitor")
        else:
            raise ValueError(f"quest contract is {occurrence.status.value}")
        if not self.quests.ready_to_claim(actor, quest_id):
            raise ValueError("quest contract objectives are incomplete")
        result = self.quests.claim(actor, quest_id, self.catalog, now_ms=self.world.now_ms)
        if result.col:
            self._settle_income_after_existing_credit(
                actor_id, result.col, source=f"quest_contract:{contract.contract_id}"
            )
            self.economy.record_system_reward(
                contract.posting_location_id,
                result.col,
                source=f"quest_contract:{contract.contract_id}",
                at_ms=self.world.now_ms,
            )
        self._refresh_marriage_capacity(actor_id)
        if occurrence.status is WorldEventStatus.ACTIVE:
            self.economy.record_external_supply(
                contract.source_location_id,
                contract.target_id,
                contract.required,
                source=f"quest_contract_delivery:{actor_id}",
                at_ms=self.world.now_ms,
            )
            contract.advance_world_progress(contract.required)
            self._resolve_contract(
                contract,
                winner_kind="named_player",
                winner_ids=(actor_id,),
                winner_ref_id=actor_id,
            )
        self._record_quest_ecology(
            "contract_claimed",
            contract_id=contract.contract_id,
            actor_id=actor_id,
            reward_col=result.col,
            reward_xp=result.experience.amount,
        )
        return result

    def quest_contract_state(self, contract_id: str) -> dict[str, Any]:
        contract = self.quest_contracts[contract_id]
        row = asdict(contract)
        row["world_event"] = asdict(self._occurrence(contract))
        row["claimants"] = self._claimant_rows(contract)
        return row

    def quest_ecology_state(self, contract_id: str | None = None) -> dict[str, Any]:
        self.assert_quest_ecology_authority()
        if contract_id is not None:
            return {
                "world_now_ms": self.world.now_ms,
                "next_tick_at_ms": self.next_quest_ecology_tick_at_ms,
                "contract": self.quest_contract_state(contract_id),
            }
        return {
            "world_now_ms": self.world.now_ms,
            "next_tick_at_ms": self.next_quest_ecology_tick_at_ms,
            "contracts": {
                contract_id: self.quest_contract_state(contract_id)
                for contract_id in sorted(self.quest_contracts)
            },
        }

    def assert_quest_ecology_authority(self) -> None:
        if self.next_quest_ecology_tick_at_ms <= self.world.now_ms:
            raise RuntimeError("quest ecology next tick must be in the future")
        if not 0 <= self.quest_ecology_ecology_cursor <= len(self.monster_ecology_history):
            raise RuntimeError("quest ecology monster-history cursor is invalid")
        if not 0 <= self.quest_ecology_market_cursor <= len(self.economy.market_history):
            raise RuntimeError("quest ecology market-history cursor is invalid")
        active_keys = set()
        for contract_id, contract in self.quest_contracts.items():
            if contract.contract_id != contract_id or contract.quest_id != contract_id:
                raise RuntimeError("quest contract registry key/id mismatch")
            if contract.source_location_id not in self.world_map.locations:
                raise RuntimeError("quest contract source location is invalid")
            if contract.posting_location_id not in self.world_map.locations:
                raise RuntimeError("quest contract posting location is invalid")
            if not self.world_map.locations[contract.posting_location_id].safe_zone:
                raise RuntimeError("quest contract posting location must remain safe")
            occurrence = self.world_events.occurrences.get(contract.occurrence_id)
            if occurrence is None or occurrence.rule_id != QUEST_ECOLOGY_WORLD_EVENT_RULE_ID:
                raise RuntimeError("quest contract lifecycle is missing from WorldEvent authority")
            definition = contract.quest_definition(
                floor_number=self.world_map.locations[contract.posting_location_id].floor_number
            )
            if self.quests.definitions.get(contract.quest_id) != definition:
                raise RuntimeError("quest contract definition projection disagrees with contract state")
            if occurrence.status is WorldEventStatus.ACTIVE:
                if contract.expires_at_ms <= self.world.now_ms:
                    raise RuntimeError("active quest contract has crossed its expiry boundary")
                key = (contract.source_kind.value, contract.source_location_id, contract.target_id)
                if key in active_keys:
                    raise RuntimeError("duplicate active quest contract for one world source")
                active_keys.add(key)
            if contract.winner_kind is not None and occurrence.status is not WorldEventStatus.RESOLVED:
                raise RuntimeError("quest contract winner exists without resolved WorldEvent lifecycle")
        for row in self.quest_ecology_history:
            if int(row["at_ms"]) > self.world.now_ms:
                raise RuntimeError("quest ecology history cannot be in the future")

    def dump_quest_ecology_state(self) -> dict[str, Any]:
        self.assert_quest_ecology_authority()
        return {
            "schema": QUEST_ECOLOGY_SCHEMA,
            "sequence": self.quest_contract_sequence,
            "next_tick_at_ms": self.next_quest_ecology_tick_at_ms,
            "ecology_cursor": self.quest_ecology_ecology_cursor,
            "market_cursor": self.quest_ecology_market_cursor,
            "contracts": {
                contract_id: asdict(contract)
                for contract_id, contract in self.quest_contracts.items()
            },
            "history": list(self.quest_ecology_history),
        }

    def load_quest_ecology_state(self, payload: dict[str, Any]) -> None:
        old_contract_ids = set(self.quest_contracts)
        for quest_id in old_contract_ids:
            self.quests.definitions.pop(quest_id, None)
        self.quest_contracts = {}
        if not payload:
            self.quest_ecology_history = []
            self.quest_contract_sequence = 0
            self.quest_ecology_ecology_cursor = len(self.monster_ecology_history)
            self.quest_ecology_market_cursor = len(self.economy.market_history)
            self.next_quest_ecology_tick_at_ms = self.world.now_ms + QUEST_ECOLOGY_TICK_MS
            return
        if payload.get("schema") != QUEST_ECOLOGY_SCHEMA:
            raise ValueError("unsupported non-empty quest ecology schema")
        restored = {}
        for contract_id, row in payload.get("contracts", {}).items():
            contract = QuestContractState(
                contract_id=row["contract_id"],
                occurrence_id=row["occurrence_id"],
                source_kind=QuestContractSource(row["source_kind"]),
                source_ref_id=row["source_ref_id"],
                source_location_id=row["source_location_id"],
                posting_location_id=row["posting_location_id"],
                quest_id=row["quest_id"],
                objective_kind=QuestObjectiveKind(row["objective_kind"]),
                target_id=row["target_id"],
                required=int(row["required"]),
                created_at_ms=int(row["created_at_ms"]),
                expires_at_ms=int(row["expires_at_ms"]),
                reward_col=int(row["reward_col"]),
                reward_xp=int(row["reward_xp"]),
                world_progress=int(row.get("world_progress", 0)),
                winner_kind=row.get("winner_kind"),
                winner_ids=tuple(row.get("winner_ids", ())),
                winner_ref_id=row.get("winner_ref_id"),
                revision=int(row.get("revision", 0)),
            )
            if contract.contract_id != contract_id:
                raise ValueError("quest ecology save contract key/id mismatch")
            restored[contract_id] = contract
        self.quest_contracts = restored
        for contract in self.quest_contracts.values():
            self._install_contract_definition(contract)
        self.quest_ecology_history = list(payload.get("history", []))
        self.quest_contract_sequence = int(payload.get("sequence", 0))
        self.quest_ecology_ecology_cursor = int(payload.get("ecology_cursor", 0))
        self.quest_ecology_market_cursor = int(payload.get("market_cursor", 0))
        self.next_quest_ecology_tick_at_ms = int(payload["next_tick_at_ms"])
        if self.next_quest_ecology_tick_at_ms <= self.world.now_ms:
            raise ValueError("quest ecology save next tick must be after current world time")
        self.assert_quest_ecology_authority()

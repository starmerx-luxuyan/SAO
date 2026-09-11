import pytest

from sao_mcp.domain.models import ItemInstance
from sao_mcp.rules.inventory import add_item
from sao_mcp.rules.quest_ecology import QUEST_ECOLOGY_TICK_MS, QuestContractSource
from sao_mcp.rules.quests import QuestObjectiveKind
from sao_mcp.rules.world_events import WorldEventStatus
from sao_mcp.runtime.persistence import export_runtime, import_runtime
from sao_mcp.runtime.quest_ecology_runtime import QuestEcologyAincradRuntime


TOWN = "floor_1_town_of_beginnings"
WEST = "floor_1_west_field"


def _monster_contract(runtime: QuestEcologyAincradRuntime):
    rows = [
        contract
        for contract in runtime.quest_contracts.values()
        if contract.source_kind is QuestContractSource.MONSTER_PRESSURE
        and contract.source_location_id == WEST
    ]
    assert rows
    return sorted(rows, key=lambda row: row.contract_id)[0]


def test_monster_pressure_publishes_active_world_event_contract_without_manual_quest_seed():
    runtime = QuestEcologyAincradRuntime(seed=801)
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    contract = _monster_contract(runtime)
    occurrence = runtime.world_events.occurrences[contract.occurrence_id]
    assert occurrence.status is WorldEventStatus.ACTIVE
    assert contract.objective_kind is QuestObjectiveKind.KILL
    assert contract.target_id == "frenzy_boar"
    assert runtime.world_map.locations[contract.posting_location_id].safe_zone
    assert contract.quest_id in runtime.quests.definitions
    assert contract.quest_id not in __import__("sao_mcp.corpus.quests", fromlist=["CORE_QUESTS"]).CORE_QUESTS


def test_named_player_can_win_competitive_cull_and_other_claimant_fails_then_winner_claims():
    runtime = QuestEcologyAincradRuntime(seed=802)
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    contract = _monster_contract(runtime)
    winner = runtime.create_character("Winner")
    loser = runtime.create_character("Loser")
    assert contract.posting_location_id == TOWN
    runtime.accept_quest_contract(winner.actor_id, contract.contract_id)
    runtime.accept_quest_contract(loser.actor_id, contract.contract_id)
    runtime.travel_actor(winner.actor_id, WEST)
    monsters = [runtime.materialize_ecological_monster(contract.target_id) for _ in range(contract.required)]
    for monster in monsters:
        monster.hp = 1
        monster.evasion = 0
    winner.skill_proficiencies["one_hand_sword"] = 1000
    encounter = runtime.start_encounter([winner.actor_id, *[monster.actor_id for monster in monsters]])
    for monster in monsters:
        result = runtime.attack(
            encounter.encounter_id,
            winner.actor_id,
            monster.actor_id,
            defense="none",
            seed=1,
        )
        assert result.hit
        if monster is not monsters[-1] and winner.recovery_until_ms > encounter.time_ms:
            runtime.advance_encounter(
                encounter.encounter_id, winner.recovery_until_ms - encounter.time_ms
            )
    assert runtime.world_events.occurrences[contract.occurrence_id].status is WorldEventStatus.RESOLVED
    assert contract.winner_kind == "named_player"
    assert winner.actor_id in contract.winner_ids
    loser_progress = runtime.quests.progress_by_actor[loser.actor_id][contract.quest_id]
    assert loser_progress.terminated_status == "failed"
    runtime.travel_actor(winner.actor_id, TOWN)
    before_col = winner.col
    result = runtime.claim_quest(winner.actor_id, contract.quest_id)
    assert result.col > 0
    assert winner.col > before_col
    market = runtime.aincrad_economy_state(TOWN)["location"]["market"]
    assert market["system_col_injected"] >= result.col


def test_background_hunters_can_finish_contract_before_named_claimant():
    runtime = QuestEcologyAincradRuntime(seed=803)
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    contract = _monster_contract(runtime)
    player = runtime.create_character("LateHunter")
    runtime.accept_quest_contract(player.actor_id, contract.contract_id)
    runtime.add_population_cohort(
        "f1_frontliners", "frontline", 240, WEST, 1.0, "boar_culling"
    )
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    occurrence = runtime.world_events.occurrences[contract.occurrence_id]
    assert occurrence.status is WorldEventStatus.RESOLVED
    assert contract.winner_kind == "background_population"
    assert contract.winner_ref_id == "f1_frontliners"
    progress = runtime.quests.progress_by_actor[player.actor_id][contract.quest_id]
    assert progress.terminated_status == "failed"


def test_contract_expires_at_exact_scheduler_boundary_and_marks_claimants_expired():
    runtime = QuestEcologyAincradRuntime(seed=804)
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    contract = _monster_contract(runtime)
    player = runtime.create_character("SlowHunter")
    runtime.accept_quest_contract(player.actor_id, contract.contract_id)
    runtime.advance_world(contract.expires_at_ms - runtime.world.now_ms)
    assert runtime.world.now_ms == contract.expires_at_ms
    assert runtime.world_events.occurrences[contract.occurrence_id].status is WorldEventStatus.FAILED
    progress = runtime.quests.progress_by_actor[player.actor_id][contract.quest_id]
    assert progress.terminated_status == "expired"
    assert progress.terminated_at_ms == contract.expires_at_ms


def test_real_market_unmet_material_demand_publishes_supply_contract_and_background_supply_can_win():
    runtime = QuestEcologyAincradRuntime(seed=805)
    runtime.add_population_cohort("town_buyers", "casual", 5_000, TOWN, 2.0, "materials_market")
    runtime.economy.record_external_supply(
        TOWN, "boar_hide", 1, source="initial_hunter_stock", at_ms=runtime.world.now_ms
    )
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    contracts = [
        contract
        for contract in runtime.quest_contracts.values()
        if contract.source_kind is QuestContractSource.MARKET_SHORTAGE
        and contract.target_id == "boar_hide"
    ]
    assert contracts
    contract = contracts[0]
    player = runtime.create_character("Supplier")
    runtime.accept_quest_contract(player.actor_id, contract.contract_id)
    runtime.economy.record_external_supply(
        TOWN,
        "boar_hide",
        contract.required,
        source="background_traders",
        at_ms=runtime.world.now_ms,
    )
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    assert runtime.world_events.occurrences[contract.occurrence_id].status is WorldEventStatus.RESOLVED
    assert contract.winner_kind == "background_supply"
    assert runtime.quests.progress_by_actor[player.actor_id][contract.quest_id].terminated_status == "failed"


def test_named_collect_contract_turnin_consumes_real_items_and_adds_local_supply():
    runtime = QuestEcologyAincradRuntime(seed=806)
    runtime.add_population_cohort("town_buyers", "casual", 5_000, TOWN, 2.0, "materials_market")
    runtime.economy.record_external_supply(TOWN, "boar_hide", 1, source="seed", at_ms=0)
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    contract = next(
        contract
        for contract in runtime.quest_contracts.values()
        if contract.source_kind is QuestContractSource.MARKET_SHORTAGE
        and contract.target_id == "boar_hide"
    )
    player = runtime.create_character("Deliverer")
    runtime.accept_quest_contract(player.actor_id, contract.contract_id)
    template = runtime.catalog.item("boar_hide")
    item = ItemInstance(
        instance_id="item_contract_boar_hide",
        template_id="boar_hide",
        owner_id=player.actor_id,
        quantity=contract.required,
    )
    add_item(player, item, runtime.catalog, allow_overweight=True)
    before_stock = runtime.economy.background_commodity_stock.get(TOWN, {}).get("boar_hide", 0)
    result = runtime.claim_quest(player.actor_id, contract.quest_id)
    assert result.col > 0
    assert item.instance_id not in player.inventory
    assert runtime.world_events.occurrences[contract.occurrence_id].status is WorldEventStatus.RESOLVED
    assert contract.winner_ids == (player.actor_id,)
    assert runtime.economy.background_commodity_stock[TOWN]["boar_hide"] == before_stock + contract.required


def test_quest_ecology_round_trip_restores_contracts_world_event_progress_and_cursors_exactly():
    runtime = QuestEcologyAincradRuntime(seed=807)
    runtime.advance_world(QUEST_ECOLOGY_TICK_MS)
    contract = _monster_contract(runtime)
    player = runtime.create_character("Saver")
    runtime.accept_quest_contract(player.actor_id, contract.contract_id)
    before = runtime.quest_ecology_state(contract.contract_id)
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, QuestEcologyAincradRuntime)
    assert restored.quest_ecology_state(contract.contract_id) == before
    assert restored.quests.definitions[contract.quest_id] == runtime.quests.definitions[contract.quest_id]
    assert restored.quest_ecology_ecology_cursor == runtime.quest_ecology_ecology_cursor
    assert restored.quest_ecology_market_cursor == runtime.quest_ecology_market_cursor


def test_generic_adventure_monster_materialization_consumes_ecology_capacity_contract_truth():
    runtime = QuestEcologyAincradRuntime(seed=808)
    player = runtime.create_character("EcologyToolUser")
    runtime.travel_actor(player.actor_id, WEST)
    before = runtime.monster_ecology["frenzy_boar"].available_units
    monster = runtime.materialize_ecological_monster("frenzy_boar")
    assert monster.metadata["ecology_monster_id"] == "frenzy_boar"
    assert runtime.monster_ecology["frenzy_boar"].available_units == before - 1

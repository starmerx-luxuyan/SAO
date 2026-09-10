import pytest

from sao_mcp.rules.family import DivorceMode, DivorceStatus
from sao_mcp.runtime.family_runtime import FamilyCommunityAincradRuntime
from sao_mcp.runtime.persistence import export_runtime, import_runtime


def _married(runtime: FamilyCommunityAincradRuntime, *, strong=False):
    a = runtime.create_character("A")
    b = runtime.create_character("B")
    if strong:
        a.strength = 100
        b.strength = 100
    a.col = 60
    b.col = 40
    request = runtime.request_marriage(a.actor_id, b.actor_id)
    marriage = runtime.accept_marriage(request.request_id, b.actor_id)
    return a, b, marriage


def test_mutual_percentage_divorce_splits_wallet_and_inventory_without_duplication():
    runtime = FamilyCommunityAincradRuntime(seed=1)
    a, b, marriage = _married(runtime, strong=True)
    original_ids = set(a.inventory)
    proposal = runtime.propose_divorce(
        a.actor_id,
        mode=DivorceMode.AUTO_PERCENTAGE,
        proposer_percent=40,
    )
    assert proposal.status is DivorceStatus.PENDING
    runtime.accept_divorce(proposal.proposal_id, b.actor_id)
    assert proposal.status is DivorceStatus.COMPLETED
    assert not marriage.active
    assert a.col == 40
    assert b.col == 60
    assert a.inventory is not b.inventory
    assert set(a.inventory).isdisjoint(b.inventory)
    assert set(a.inventory) | set(b.inventory) == original_ids
    assert runtime.relationships.marriage_for(a.actor_id) is None


def test_item_selection_divorce_honors_mutually_accepted_selected_instance():
    runtime = FamilyCommunityAincradRuntime(seed=1)
    a = runtime.create_character("A")
    selected = a.equipment["weapon"]
    b = runtime.create_character("B")
    a.strength = b.strength = 100
    request = runtime.request_marriage(a.actor_id, b.actor_id)
    runtime.accept_marriage(request.request_id, b.actor_id)
    proposal = runtime.propose_divorce(
        a.actor_id,
        mode=DivorceMode.ITEM_SELECTION,
        proposer_percent=50,
        selected_item_ids=[selected],
    )
    runtime.accept_divorce(proposal.proposal_id, b.actor_id)
    assert selected in a.inventory
    assert selected not in b.inventory


def test_surrender_all_divorce_is_unilateral_and_gives_other_partner_everything_when_capacity_allows():
    runtime = FamilyCommunityAincradRuntime(seed=1)
    a, b, marriage = _married(runtime, strong=True)
    original_ids = set(a.inventory)
    proposal = runtime.propose_divorce(
        a.actor_id,
        mode=DivorceMode.SURRENDER_ALL,
        proposer_percent=0,
    )
    assert proposal.status is DivorceStatus.COMPLETED
    assert not marriage.active
    assert a.col == 0
    assert b.col == 100
    assert not a.inventory
    assert set(b.inventory) == original_ids


def test_divorce_capacity_overflow_becomes_persistent_ground_drop():
    runtime = FamilyCommunityAincradRuntime(seed=1)
    a, b, _ = _married(runtime, strong=False)
    runtime.propose_divorce(
        a.actor_id,
        mode=DivorceMode.SURRENDER_ALL,
        proposer_percent=0,
    )
    drops = runtime.world.global_flags.get("ground_drops", {}).get(b.location_id, [])
    assert drops
    assert any(row.get("drop_reason") == "divorce capacity overflow" for row in drops)


def test_declined_divorce_keeps_marriage_and_shared_pool_active():
    runtime = FamilyCommunityAincradRuntime(seed=1)
    a, b, marriage = _married(runtime, strong=True)
    proposal = runtime.propose_divorce(a.actor_id, proposer_percent=50)
    runtime.decline_divorce(proposal.proposal_id, b.actor_id)
    assert proposal.status is DivorceStatus.DECLINED
    assert marriage.active
    assert a.inventory is b.inventory
    assert runtime.relationships.marriage_for(a.actor_id) is marriage


def test_permanent_spouse_death_ends_marriage_and_transfers_shared_estate():
    runtime = FamilyCommunityAincradRuntime(seed=1)
    a, b, marriage = _married(runtime, strong=True)
    original_ids = set(a.inventory)
    a.location_id = "floor_1_west_field"
    b.location_id = "floor_1_west_field"
    encounter = runtime.start_encounter([a.actor_id, b.actor_id], zone_id="floor_1_west_field")
    b.hp = 0
    b.alive = False
    runtime._resolve_defeat(encounter, b, a.actor_id)
    assert b.metadata["death_state"] == "end_phase"
    assert marriage.active
    runtime.advance_encounter(encounter.encounter_id, 10_000)
    assert b.metadata["death_state"] == "permanent"
    assert not marriage.active
    assert a.col == 100
    assert b.col == 0
    assert not b.inventory
    assert set(a.inventory) == original_ids
    assert runtime.relationships.marriage_for(a.actor_id) is None


def test_pending_divorce_proposal_round_trips_with_shared_marriage_state():
    runtime = FamilyCommunityAincradRuntime(seed=1)
    a, b, marriage = _married(runtime, strong=True)
    proposal = runtime.propose_divorce(
        a.actor_id,
        mode=DivorceMode.AUTO_PERCENTAGE,
        proposer_percent=55,
    )
    restored = import_runtime(export_runtime(runtime))
    assert isinstance(restored, FamilyCommunityAincradRuntime)
    loaded = restored.divorce_proposals[proposal.proposal_id]
    assert loaded.status is DivorceStatus.PENDING
    assert loaded.proposer_percent == 55
    assert restored.relationships.marriages[marriage.marriage_id].active
    assert restored.actors[a.actor_id].inventory is restored.actors[b.actor_id].inventory

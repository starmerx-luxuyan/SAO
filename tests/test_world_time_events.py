from sao_mcp.runtime.housing_runtime import HousingAincradRuntime, PROPERTY_ENTRY_TIME_MS


def test_world_time_hooks_cover_explicit_time_property_doors_and_solo_travel():
    runtime = HousingAincradRuntime(seed=89)
    actor = runtime.create_character("ClockWalker", level=5)
    actor.col = 2_000
    observed: list[tuple[int, int]] = []
    runtime.register_world_advance_hook(lambda before_ms, after_ms: observed.append((before_ms, after_ms)))

    runtime.advance_world(1_000)
    assert observed == [(0, 1_000)]

    residence = runtime.purchase_residence(actor.actor_id, "town_beginner_room", joint_marriage=False)
    before_enter = runtime.world.now_ms
    runtime.enter_property(actor.actor_id, residence.property_id)
    assert observed[-1] == (before_enter, before_enter + PROPERTY_ENTRY_TIME_MS)

    before_exit = runtime.world.now_ms
    runtime.exit_property(actor.actor_id)
    assert observed[-1] == (before_exit, before_exit + PROPERTY_ENTRY_TIME_MS)

    before_walk = runtime.world.now_ms
    resolution = runtime.travel_actor(actor.actor_id, "floor_1_west_field")
    assert observed[-1] == (before_walk, before_walk + resolution.elapsed_ms)
    assert runtime.world.now_ms == before_walk + resolution.elapsed_ms

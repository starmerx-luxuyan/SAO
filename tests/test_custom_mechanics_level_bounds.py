from sao_mcp.rules.custom_mechanics import configure_custom_mechanics
from sao_mcp.rules.progression import apply_level
from sao_mcp.runtime.social_communication_runtime import SocialCommunicationAincradRuntime


def test_level_growth_conditions_count_only_matching_target_levels():
    runtime = SocialCommunicationAincradRuntime(seed=0xA1C0)
    actor = runtime.create_character("BoundedGrowth", level=4)
    base_strength = actor.strength
    base_agility = actor.agility

    configure_custom_mechanics(
        actor,
        runtime.catalog,
        [
            {
                "mechanic_id": "bounded_growth",
                "effects": [
                    {
                        "type": "level_attribute_growth",
                        "strength_per_level": 2,
                        "agility_per_level": 1,
                        "from_level": 1,
                        "conditions": {"min_level": 5, "max_level": 6},
                    }
                ],
            }
        ],
        apply_retroactive=True,
    )

    assert (actor.strength, actor.agility) == (base_strength, base_agility)

    apply_level(actor, 7)
    # Normal Lv4 -> Lv7 growth contributes +6/+6. The custom rule counts only
    # the transitions whose target levels are 5 and 6, contributing +4/+2.
    assert actor.strength == base_strength + 10
    assert actor.agility == base_agility + 8

    apply_level(actor, 9)
    # Lv8 and Lv9 are outside max_level=6, so only ordinary +4/+4 applies.
    assert actor.strength == base_strength + 14
    assert actor.agility == base_agility + 12

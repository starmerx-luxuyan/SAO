# Campaign Setup API — v1.1.0

v1.1 separates **campaign setup authority** from ordinary in-world GM actions.
Setup tools write the same authoritative runtime state used by combat, UI, save/load and the GM Decision Gate, but they are not legal shortcuts for ordinary play.

Public setup has a real lifecycle: `begin_campaign_setup` opens the one-time configuration phase, setup mutations are accepted only while it is open, and `finalize_campaign_setup` permanently locks the public setup surface for that campaign. `get_campaign_setup_status` is always readable. Only the full internal/development surface exposes `reopen_campaign_setup` for explicit maintenance.

## Setup lifecycle

- `get_campaign_setup_status` — read `not_started`, `open`, or `finalized`.
- `begin_campaign_setup` — open setup once for a new campaign.
- `finalize_campaign_setup` — lock public setup after at least one player exists.
- `reopen_campaign_setup` — full/internal surface only; explicit maintenance, never ordinary hosted play.

## New setup tools

- `create_configured_character` — create a character with level, Col, profile, skills, proficiencies and progression rules in one operation.
- `configure_character_setup` — patch an existing player during explicit setup; supports level/XP/location/stat/profile/skill/progression configuration.
- `get_character_setup_state` — inspect raw authoritative setup state, including metadata, inventory and progression rules.
- `grant_character_item` — grant a real catalog item with quantity, durability, reinforcement-attempt cap, used attempts, enhancement tracks, quality, maker and optional immediate equip.
- `remove_character_item_setup` — remove a setup item, safely unequipping it first.
- `register_custom_skill_definition` — register a persistent campaign-local Skill definition.
- `register_custom_sword_skill_definition` — register a persistent campaign-local Sword Skill and optionally bind it to a specific proficiency with `proficiency_skill_id`.
- `register_custom_weapon_definition` / `register_custom_armor_definition` — define real campaign-local equipment templates.
- `register_custom_consumable_definition` / `register_custom_item_definition` — define real consumables and ordinary items that use the normal inventory/item runtime.
- `get_custom_catalog_state` / `remove_custom_item_definition` — inspect custom definitions and remove uninstantiated setup templates.
- `set_character_custom_mechanics` — install a validated declarative mechanic bundle on a character.

The original `create_character` remains available for ordinary legal starter creation.

## Public catalog expansion

`list_catalog` and `inspect_catalog_entry` now cover:

- `weapons`
- `armors`
- `consumables`
- `items`
- `skills`
- `sword_skills`

## Custom proficiency ownership

A custom Sword Skill can specify:

```json
{
  "proficiency_skill_id": "star_sword"
}
```

When present, prerequisite checks, attack proficiency scaling and successful-use proficiency growth use that Skill instead of silently falling back to the equipped weapon class.

A character can also route all attacks of one weapon class through a custom Skill:

```json
{
  "weapon_proficiency_skill_by_class": {
    "one_hand_sword": "star_sword"
  }
}
```

This lets a Unique Skill genuinely replace a normal weapon Skill while still using compatible one-handed swords.

## Progression rules

`progression_rules` currently supports four generic rule families.

### Per-level attribute growth

```json
{
  "level_growth_bonus": {
    "strength_per_level": 1,
    "agility_per_level": 1,
    "from_level": 1
  }
}
```

When configured retroactively on a Lv.7 character, the tracked bonus is applied for six completed level gains. Future `apply_level` / XP level-ups continue to add the bonus and update the tracked contribution without double-applying it.

### Weapon reinforcement-attempt cap by proficiency

```json
{
  "weapon_enhancement_cap_by_class": {
    "one_hand_sword": {
      "skill_id": "star_sword",
      "thresholds": [[50,1],[150,2],[250,3],[350,4],[450,5],[550,6],[650,7],[750,8],[850,9],[950,10]]
    }
  }
}
```

Each weapon instance records its original reinforcement-attempt cap in metadata. The runtime derives the current cap from that baseline plus the highest reached bonus, preventing cumulative drift when the rule is re-evaluated or replaced.

### Normal attack progression

```json
{
  "normal_attack_by_class": {
    "one_hand_sword": {
      "skill_id": "star_sword",
      "min_proficiency": 501,
      "reference_proficiency": 500,
      "damage_multiplier_start": 1.15,
      "damage_multiplier_per_proficiency": 0.0003,
      "damage_multiplier_max": 1.30,
      "recovery_multiplier_start": 0.90,
      "recovery_multiplier_end": 0.80,
      "recovery_end_proficiency": 1000
    }
  }
}
```

The modifier is part of physical attack resolution and timeline recovery calculation, not a display-only character-sheet bonus.

## Grounded field encounter entry

The public observation packet now projects `capabilities.encounter_options` from the local living monster ecology. The new ordinary player action:

```json
{
  "op": "engage_monster",
  "actor_id": "...",
  "monster_id": "frenzy_boar"
}
```

is accepted only when that monster ID appears in the player's fresh observation. It reuses an already materialized ecology actor when possible and starts a real `EncounterState`; it does not spawn a narrative-only target.

## Persistence

Save schema is now `sao.aincrad.save.v4`.

v4 persists campaign-local custom weapons, armor/shields, consumables, ordinary items, Skills and Sword Skills in `custom_catalog_state`. Custom item catalog payloads use `custom-catalog.v2`; actor-local custom mechanics persist through normal actor metadata. Importing a v3 save is exact: the state migrates to v4 with an empty custom-catalog registry. Existing v1/v2 exact-migration restrictions remain unchanged.


## Declarative custom mechanics

`custom_mechanics` is the preferred v1.1 mechanism layer for new custom starts. A character receives a list of named mechanic bundles, each containing one or more validated effects. Supported effect types are:

- `level_attribute_growth`
- `weapon_proficiency_route`
- `weapon_enhancement_cap_curve`
- `normal_attack_curve`
- `proficiency_gain_modifier`
- `skill_unlock`

Effects may use shared conditions such as minimum/maximum level, HP-ratio windows, required equipped/unlocked skills, and minimum proficiencies. Multiple compatible mechanics compose; conflicting weapon-proficiency routes are rejected. Legacy `progression_rules` remains supported for exact v1.1 compatibility, while new campaign blueprints should prefer `custom_mechanics`.

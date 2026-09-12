# Campaign Setup API — v1.2.0

Campaign setup is a separate authority from ordinary in-world GM actions. Setup writes the same authoritative runtime state used by combat, progression, persistence and UI, but only while the campaign setup lifecycle is open.

## Setup lifecycle

- `get_campaign_setup_status` — read `not_started`, `open`, or `finalized`.
- `begin_campaign_setup` — open setup for a new campaign.
- `finalize_campaign_setup` — lock hosted setup after at least one player exists.
- `reopen_campaign_setup` — full/internal surface only; explicit maintenance, never ordinary hosted play.

## Preferred v1.2 workflow

```text
get_campaign_setup_status
→ begin_campaign_setup
→ validate_campaign_blueprint
→ preview_campaign_blueprint
→ apply_campaign_blueprint
→ finalize_campaign_setup
```

Individual v1.1 setup tools remain available when a caller wants to build or edit a campaign incrementally.

## Campaign Blueprint

Schema:

```text
sao.aincrad.campaign-blueprint.v1
```

Top-level shape:

```json
{
  "schema": "sao.aincrad.campaign-blueprint.v1",
  "blueprint_id": "my_custom_start",
  "title": "My Custom Start",
  "catalog": {
    "skills": [],
    "sword_skills": [],
    "weapons": [],
    "armors": [],
    "consumables": [],
    "items": []
  },
  "characters": []
}
```

`catalog` definitions are registered through the same custom-catalog authority used by the individual setup tools. Character rows are then created against that resulting catalog, so a character can equip or reference definitions declared earlier in the same blueprint.

### Character row

A character has a blueprint-local `key` plus ordinary setup fields:

```json
{
  "key": "player",
  "name": "Example",
  "level": 7,
  "keep_starter_loadout": false,
  "location_id": "floor_1_town_of_beginnings",
  "strength": 22,
  "agility": 22,
  "col": 3000,
  "profile": {},
  "skill_proficiencies": {},
  "replace_skill_proficiencies": true,
  "equipped_skills": [],
  "unlocked_special_skills": [],
  "progression_rules": {},
  "custom_mechanics": [],
  "inventory": []
}
```

`keep_starter_loadout` defaults to false, so an arbitrary custom start can declare an exact inventory rather than inheriting the ordinary starter sword/coat/potions. Starter removal uses the normal setup inventory authority and unequips items before removal.

Inventory rows use real item instances and may specify quantity, durability/max durability, reinforcement-attempt limits/usage, enhancement tracks, quality, maker, metadata, immediate equip and overweight allowance.

### Validation and preview

`validate_campaign_blueprint` and `preview_campaign_blueprint` clone the complete persisted runtime and execute the actual blueprint implementation on the clone. They do not mutate the authoritative campaign. Validation returns a compact semantic summary; preview returns the resulting catalog/character state.

Preview does not expose provisional actor/item IDs as committed IDs.

### Apply

`apply_campaign_blueprint` requires setup to be open. It first executes the complete blueprint against cloned state; only after every definition, character, mechanic and item succeeds is the resulting authoritative state committed back. A failure in a late Sword Skill or inventory entry therefore does not leave a partially configured live campaign.

Apply deliberately leaves setup open. Finalization remains an explicit separate action so the caller can inspect the committed setup before locking it.

## Custom catalog

Individual setup tools still support:

- custom weapons;
- armor and shields;
- consumables;
- ordinary items;
- Skills;
- Sword Skills with optional `proficiency_skill_id`.

`list_catalog` and `inspect_catalog_entry` cover `weapons`, `armors`, `consumables`, `items`, `skills`, and `sword_skills`.

## Declarative custom mechanics

`custom_mechanics` is the preferred generic mechanism layer. Supported effect types are:

- `level_attribute_growth`
- `weapon_proficiency_route`
- `weapon_enhancement_cap_curve`
- `normal_attack_curve`
- `proficiency_gain_modifier`
- `skill_unlock`

Effects may use minimum/maximum level, HP-ratio windows, required equipped/unlocked skills and minimum proficiencies. Compatible mechanics compose; conflicting weapon-proficiency routes are rejected.

Legacy `progression_rules` remains supported for exact v1.1 compatibility.

## Persistence

The save schema remains `sao.aincrad.save.v4`. Campaign Blueprint introduces no parallel save format: custom definitions persist in `custom_catalog_state`, character mechanics persist in actor metadata, and granted equipment/items persist as ordinary item instances. The blueprint format itself is versioned independently as `sao.aincrad.campaign-blueprint.v1`.

from __future__ import annotations

from pydantic import TypeAdapter

from sao_mcp.domain.models import (
    ArmorTemplate,
    ConsumableTemplate,
    ItemTemplate,
    SkillDefinition,
    SwordSkillDefinition,
    WeaponTemplate,
)


WEAPONS_ADAPTER = TypeAdapter(dict[str, WeaponTemplate])
ARMORS_ADAPTER = TypeAdapter(dict[str, ArmorTemplate])
CONSUMABLES_ADAPTER = TypeAdapter(dict[str, ConsumableTemplate])
ITEMS_ADAPTER = TypeAdapter(dict[str, ItemTemplate])
SKILLS_ADAPTER = TypeAdapter(dict[str, SkillDefinition])
SWORD_SKILLS_ADAPTER = TypeAdapter(dict[str, SwordSkillDefinition])


def _ids(runtime, attr: str) -> set[str]:
    ids = getattr(runtime, attr, None)
    if ids is None:
        ids = set()
        setattr(runtime, attr, ids)
    return ids


def _weapon_ids(runtime) -> set[str]:
    return _ids(runtime, "_custom_catalog_weapon_ids")


def _armor_ids(runtime) -> set[str]:
    return _ids(runtime, "_custom_catalog_armor_ids")


def _consumable_ids(runtime) -> set[str]:
    return _ids(runtime, "_custom_catalog_consumable_ids")


def _item_ids(runtime) -> set[str]:
    return _ids(runtime, "_custom_catalog_item_ids")


def _skill_ids(runtime) -> set[str]:
    return _ids(runtime, "_custom_catalog_skill_ids")


def _sword_skill_ids(runtime) -> set[str]:
    return _ids(runtime, "_custom_catalog_sword_skill_ids")


def _all_item_mappings(runtime):
    return (
        (runtime.catalog.weapons, _weapon_ids(runtime), "weapon"),
        (runtime.catalog.armors, _armor_ids(runtime), "armor"),
        (runtime.catalog.consumables, _consumable_ids(runtime), "consumable"),
        (runtime.catalog.items, _item_ids(runtime), "item"),
    )


def _register_item_template(runtime, definition, mapping, custom_ids: set[str], kind: str, *, replace: bool):
    template_id = definition.template_id
    for other_mapping, other_custom_ids, other_kind in _all_item_mappings(runtime):
        if template_id not in other_mapping:
            continue
        if other_mapping is not mapping:
            raise ValueError(f"template id already belongs to {other_kind}: {template_id}")
        if template_id not in other_custom_ids:
            raise ValueError(f"cannot replace built-in {kind}: {template_id}")
        if not replace:
            raise ValueError(f"custom {kind} already exists: {template_id}")
        if any(template_id == item.template_id for actor in runtime.actors.values() for item in actor.inventory.values()):
            raise ValueError(f"cannot replace instantiated custom {kind}: {template_id}")
    mapping[template_id] = definition
    custom_ids.add(template_id)
    return definition


def register_custom_weapon(runtime, definition: WeaponTemplate, *, replace: bool = False) -> WeaponTemplate:
    return _register_item_template(runtime, definition, runtime.catalog.weapons, _weapon_ids(runtime), "weapon", replace=replace)


def register_custom_armor(runtime, definition: ArmorTemplate, *, replace: bool = False) -> ArmorTemplate:
    return _register_item_template(runtime, definition, runtime.catalog.armors, _armor_ids(runtime), "armor", replace=replace)


def register_custom_consumable(runtime, definition: ConsumableTemplate, *, replace: bool = False) -> ConsumableTemplate:
    return _register_item_template(runtime, definition, runtime.catalog.consumables, _consumable_ids(runtime), "consumable", replace=replace)


def register_custom_item(runtime, definition: ItemTemplate, *, replace: bool = False) -> ItemTemplate:
    return _register_item_template(runtime, definition, runtime.catalog.items, _item_ids(runtime), "item", replace=replace)


def remove_custom_item_template(runtime, template_id: str) -> ItemTemplate:
    for mapping, custom_ids, kind in _all_item_mappings(runtime):
        if template_id not in mapping:
            continue
        if template_id not in custom_ids:
            raise ValueError(f"cannot remove built-in {kind}: {template_id}")
        if any(template_id == item.template_id for actor in runtime.actors.values() for item in actor.inventory.values()):
            raise ValueError(f"cannot remove custom {kind} while an instance exists: {template_id}")
        custom_ids.remove(template_id)
        return mapping.pop(template_id)
    raise KeyError(template_id)


def register_custom_skill(runtime, definition: SkillDefinition, *, replace: bool = False) -> SkillDefinition:
    custom_ids = _skill_ids(runtime)
    existing = runtime.catalog.skills.get(definition.skill_id)
    if existing is not None and definition.skill_id not in custom_ids:
        raise ValueError(f"cannot replace built-in skill: {definition.skill_id}")
    if existing is not None and not replace:
        raise ValueError(f"custom skill already exists: {definition.skill_id}")
    runtime.catalog.skills[definition.skill_id] = definition
    custom_ids.add(definition.skill_id)
    return definition


def register_custom_sword_skill(runtime, definition: SwordSkillDefinition, *, replace: bool = False) -> SwordSkillDefinition:
    custom_ids = _sword_skill_ids(runtime)
    existing = runtime.catalog.sword_skills.get(definition.skill_id)
    if existing is not None and definition.skill_id not in custom_ids:
        raise ValueError(f"cannot replace built-in Sword Skill: {definition.skill_id}")
    if existing is not None and not replace:
        raise ValueError(f"custom Sword Skill already exists: {definition.skill_id}")
    if definition.proficiency_skill_id is not None and definition.proficiency_skill_id not in runtime.catalog.skills:
        raise ValueError(f"unknown proficiency skill: {definition.proficiency_skill_id}")
    runtime.catalog.sword_skills[definition.skill_id] = definition
    custom_ids.add(definition.skill_id)
    return definition


def dump_custom_catalog_state(runtime) -> dict:
    return {
        "schema": "custom-catalog.v2",
        "weapons": WEAPONS_ADAPTER.dump_python({key: runtime.catalog.weapons[key] for key in sorted(_weapon_ids(runtime))}, mode="json"),
        "armors": ARMORS_ADAPTER.dump_python({key: runtime.catalog.armors[key] for key in sorted(_armor_ids(runtime))}, mode="json"),
        "consumables": CONSUMABLES_ADAPTER.dump_python({key: runtime.catalog.consumables[key] for key in sorted(_consumable_ids(runtime))}, mode="json"),
        "items": ITEMS_ADAPTER.dump_python({key: runtime.catalog.items[key] for key in sorted(_item_ids(runtime))}, mode="json"),
        "skills": SKILLS_ADAPTER.dump_python({key: runtime.catalog.skills[key] for key in sorted(_skill_ids(runtime))}, mode="json"),
        "sword_skills": SWORD_SKILLS_ADAPTER.dump_python({key: runtime.catalog.sword_skills[key] for key in sorted(_sword_skill_ids(runtime))}, mode="json"),
    }


def load_custom_catalog_state(runtime, payload: dict | None) -> None:
    for mapping, custom_ids, _ in _all_item_mappings(runtime):
        for template_id in tuple(custom_ids):
            mapping.pop(template_id, None)
        custom_ids.clear()
    for skill_id in tuple(_skill_ids(runtime)):
        runtime.catalog.skills.pop(skill_id, None)
    for skill_id in tuple(_sword_skill_ids(runtime)):
        runtime.catalog.sword_skills.pop(skill_id, None)
    _skill_ids(runtime).clear()
    _sword_skill_ids(runtime).clear()

    if not payload:
        return
    schema = payload.get("schema", "custom-catalog.v1")
    if schema not in {"custom-catalog.v1", "custom-catalog.v2"}:
        raise ValueError(f"unsupported custom catalog schema: {schema!r}")

    if schema == "custom-catalog.v2":
        for definition in WEAPONS_ADAPTER.validate_python(payload.get("weapons", {})).values():
            register_custom_weapon(runtime, definition)
        for definition in ARMORS_ADAPTER.validate_python(payload.get("armors", {})).values():
            register_custom_armor(runtime, definition)
        for definition in CONSUMABLES_ADAPTER.validate_python(payload.get("consumables", {})).values():
            register_custom_consumable(runtime, definition)
        for definition in ITEMS_ADAPTER.validate_python(payload.get("items", {})).values():
            register_custom_item(runtime, definition)

    for definition in SKILLS_ADAPTER.validate_python(payload.get("skills", {})).values():
        register_custom_skill(runtime, definition)
    for definition in SWORD_SKILLS_ADAPTER.validate_python(payload.get("sword_skills", {})).values():
        register_custom_sword_skill(runtime, definition)

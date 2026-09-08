from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ArmorTemplate, ItemKind, ItemTemplate, Provenance, ProvenanceKind


ITEMS_REFERENCE = "https://swordartonline.fandom.com/wiki/Items"


def _item(
    template_id: str,
    name: str,
    kind: ItemKind,
    *,
    weight: float,
    stack_limit: int = 1,
    value: int | None = None,
    tags: tuple[str, ...] = (),
    sources: tuple[str, ...] = (ITEMS_REFERENCE,),
    notes: str = "",
) -> ItemTemplate:
    return ItemTemplate(
        template_id=template_id,
        name=name,
        kind=kind,
        weight=weight,
        stack_limit=stack_limit,
        base_value_col=value,
        tags=tags,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=sources,
            notes=(
                "Item identity and explicitly described effect/acquisition are canon-backed; weight, stack and price are "
                "simulation values unless the note states a canon amount. " + notes
            ).strip(),
        ),
    )


def _armor(
    template_id: str,
    name: str,
    armor: int,
    durability: int,
    weight: float,
    slot: str,
    *,
    tags: tuple[str, ...] = (),
    sources: tuple[str, ...] = (ITEMS_REFERENCE,),
    notes: str = "",
) -> ArmorTemplate:
    return ArmorTemplate(
        template_id=template_id,
        name=name,
        kind=ItemKind.ARMOR,
        weight=weight,
        armor=armor,
        base_durability=durability,
        slot=slot,
        tags=tags,
        provenance=Provenance(
            ProvenanceKind.CANON_INFERRED,
            sources=sources,
            notes=(
                "Armour identity and explicitly stated special properties are canon-backed; armour, durability and weight "
                "numbers are simulation calibration. " + notes
            ).strip(),
        ),
    )


def apply_aincrad_item_seed(catalog: Catalog) -> Catalog:
    armors = {
        "coat_of_midnight": _armor(
            "coat_of_midnight",
            "Coat of Midnight",
            armor=48,
            durability=340,
            weight=8.5,
            slot="body",
            tags=("leather", "floor_1", "last_attack_bonus", "hiding_bonus"),
            sources=("https://swordartonline.fandom.com/wiki/Coat_of_Midnight",),
            notes="Illfang's Floor 1 Last Attack bonus and a Hiding-enhancing black leather coat.",
        ),
        "blackwyrm_coat": _armor(
            "blackwyrm_coat",
            "Blackwyrm Coat",
            armor=420,
            durability=980,
            weight=12.0,
            slot="body",
            tags=("leather", "player_made", "ashley", "black_dragon_leather", "high_hiding_bonus"),
            sources=("https://swordartonline.fandom.com/wiki/Blackwyrm_Coat",),
            notes="Made by Ashley from high-grade black dragon leather and canonically grants a high Hiding bonus.",
        ),
        "black_boots": _armor(
            "black_boots", "Black Boots", 85, 430, 5.0, "feet", tags=("kirito", "leather"),
        ),
        "boots_of_hornet": _armor(
            "boots_of_hornet", "Boots of Hornet", 74, 390, 4.2, "feet", tags=("asuna", "light"),
        ),
        "breastplate_of_steel": _armor(
            "breastplate_of_steel", "Breastplate of Steel", 150, 620, 18.0, "body", tags=("metal",),
        ),
        "fencers_tunic": _armor(
            "fencers_tunic", "Fencer's Tunic", 92, 430, 6.0, "body", tags=("asuna", "light"),
        ),
    }
    for template_id, armor in armors.items():
        catalog.armors.setdefault(template_id, armor)

    items = {
        "crystallite_ingot": _item(
            "crystallite_ingot", "Crystallite Ingot", ItemKind.MATERIAL,
            weight=3.0, tags=("rare_material", "weapon_crafting", "dark_repulser_material"),
            notes="Special quest material used by Lisbeth to forge Dark Repulser.",
        ),
        "dusk_lizard_hide": _item(
            "dusk_lizard_hide", "Dusk Lizard Hide", ItemKind.MATERIAL,
            weight=2.2, stack_limit=20, tags=("leatherworking", "rare_material"),
        ),
        "ragout_rabbit_meat": _item(
            "ragout_rabbit_meat", "Ragout Rabbit's Meat", ItemKind.FOOD,
            weight=1.0, value=100_000, tags=("s_rank", "rare_ingredient", "high_cooking_required"),
            sources=("https://swordartonline.fandom.com/wiki/Ragout_Rabbit%27s_Meat",),
            notes="Canon calls it an S-rank ingredient and states it can sell for at least 100,000 Cor.",
        ),
        "pneuma_flower": _item(
            "pneuma_flower", "Pneuma Flower", ItemKind.QUEST,
            weight=0.1, tags=("floor_47", "hill_of_memories", "tamed_monster_revive", "three_day_limit"),
            sources=("https://swordartonline.fandom.com/wiki/Pneuma_Flower",),
            notes="Rare Floor 47 item that can revive a Beast Tamer's dead Tamed Monster if used within three days.",
        ),
        "ring_of_agility": _item(
            "ring_of_agility", "Ring of Agility", ItemKind.MISC,
            weight=0.05, tags=("accessory", "rare_drop", "agility_bonus:+20", "golden_apple"),
            sources=("https://swordartonline.fandom.com/wiki/Ring_of_Agility",),
            notes="The source name is unofficial; the ring's canon effect is +20 AGI and it was the rare drop behind the Golden Apple dispute.",
        ),
        "ring_of_angels_whisper": _item(
            "ring_of_angels_whisper", "Ring of Angel's Whisper", ItemKind.MISC,
            weight=0.05, tags=("accessory", "quest_reward", "friend_voice_message", "once_per_month"),
            sources=("https://swordartonline.fandom.com/wiki/Ring_of_Angel%27s_Whisper",),
            notes="Angel's Ring quest reward; permits one voice message to a registered friend per month and grants no stat increase.",
        ),
        "mirage_sphere": _item(
            "mirage_sphere", "Mirage Sphere", ItemKind.TOOL,
            weight=1.1, tags=("map_tool", "3d_map", "hologram"),
            sources=("https://swordartonline.fandom.com/wiki/Mirage_Sphere",),
            notes="Produces a detailed 3D map of a selected area.",
        ),
        "vendor_carpet": _item(
            "vendor_carpet", "Vendor's Carpet", ItemKind.TOOL,
            weight=2.0, tags=("merchant", "player_shop", "street_vendor"),
            notes="Known SAO player-vendor equipment; runtime market integration can use this tag without another subsystem.",
        ),
        "hand_mirror": _item(
            "hand_mirror", "Hand Mirror", ItemKind.MISC,
            weight=0.2, tags=("tutorial_event", "avatar_reflection"),
        ),
        "mighty_strap_of_leather": _item(
            "mighty_strap_of_leather", "Mighty Strap of Leather", ItemKind.MISC,
            weight=0.3, tags=("equipment_accessory", "strength_related"),
        ),
        "eternal_storage_trinket": _item(
            "eternal_storage_trinket", "Eternal Storage Trinket", ItemKind.MISC,
            weight=0.1, tags=("storage_related", "rare"),
        ),
        "tremble_shortcake": _item(
            "tremble_shortcake", "Tremble Shortcake", ItemKind.FOOD,
            weight=0.4, stack_limit=5, tags=("dessert",),
        ),
        "scavenge_toad_meat": _item(
            "scavenge_toad_meat", "Scavenge Toad Meat", ItemKind.FOOD,
            weight=0.8, stack_limit=20, tags=("ingredient",),
        ),
        "yuis_heart": _item(
            "yuis_heart", "Yui's Heart", ItemKind.QUEST,
            weight=0.0, tags=("unique", "system_object", "mhcp001"),
            notes="Unique story object associated with Yui/MHCP001; no generic shop or drop acquisition is assigned.",
        ),
    }
    for template_id, item in items.items():
        catalog.items.setdefault(template_id, item)
    return catalog

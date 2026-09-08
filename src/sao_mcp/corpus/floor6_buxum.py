from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import DamageType, ItemKind, Provenance, ProvenanceKind, WeaponClass, WeaponTemplate
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
BUXUM_ID = "pc_floor6_buxum"
BUXUM_LONGSWORD_ID = "buxum_long_sword"


def apply_floor6_buxum_corpus(catalog: Catalog) -> Catalog:
    catalog.weapons.setdefault(
        BUXUM_LONGSWORD_ID,
        WeaponTemplate(
            template_id=BUXUM_LONGSWORD_ID,
            name="Buxum's Longsword",
            kind=ItemKind.WEAPON,
            weapon_class=WeaponClass.ONE_HAND_SWORD,
            damage_type=DamageType.SLASH,
            attack_min=142,
            attack_max=188,
            required_level=1,
            required_strength=1,
            weight=28,
            base_durability=690,
            base_speed_ms=630,
            reach_m=1.7,
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_6,),
                notes=(
                    "Buxum canonically draws a modest-looking but clearly high-performance longsword in the Floor 6 boss room. "
                    "The weapon is not given a proper name in the verified passage; this descriptive template and all numeric stats are simulation."
                ),
            ),
        ),
    )
    CORE_NPCS.setdefault(
        BUXUM_ID,
        NPCDefinition(
            npc_id=BUXUM_ID,
            name="Buxum",
            home_location_id="floor_6_boss_room",
            roles=(
                "named_player",
                "dkb_infiltrator",
                "black_poncho_group",
                "golden_cube_thief",
                "longsword_user",
            ),
            quest_ids=(),
            knowledge_tags=(
                "combined_iron_key",
                "irrational_cube_reverse_keyhole",
                "golden_cube_bind",
                "morte",
                "joe",
                "black_poncho_player",
            ),
            provenance=Provenance(
                ProvenanceKind.CANON,
                sources=(PROGRESSIVE_6,),
                notes=(
                    "Buxum is a player who infiltrated the DKB on behalf of the same PK conspiracy as Morte and Joe. "
                    "At the Floor 6 boss's final HP pixel he already possesses the combined iron key, uses the reverse keyhole to eject the Golden Cube, then uses Bind on the raid. "
                    "The novel explicitly leaves unexplained how the key stolen by Kysarah reached Buxum."
                ),
            ),
        ),
    )
    return catalog

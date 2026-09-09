from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_8 = "Sword Art Online Progressive Volume 8: Rhapsody of Crimson Heat (Finish)"
MAP_OF_SCYIA_ID = "map_of_scyia"
GREENLEAF_CAPE_ID = "greenleaf_cape"
RUBY_KEY_ID = "elf_war_ruby_key"
ARGO_ID = "pc_argo"

FIELD_OF_BONES = "floor_7_field_of_bones"
ANT_TUNNEL_VALLEY = "floor_7_ant_tunnel_valley"
LABYRINTH = "floor_7_labyrinth"


def _canon(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(PROGRESSIVE_8,), notes=notes)


def apply_floor7_pursuit_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        MAP_OF_SCYIA_ID,
        ItemTemplate(
            template_id=MAP_OF_SCYIA_ID,
            name="Map of Scyia",
            kind=ItemKind.TOOL,
            weight=0.08,
            stack_limit=1,
            tags=(
                "floor_7",
                "elf_war",
                "fallen_elf_contact",
                "blood_map",
                "location_marker",
                "time_marker",
                "yes_no_response",
            ),
            provenance=_canon(
                "Bardun's paired parchment map transfers fresh-blood marks to its counterpart; "
                "the Floor 7 party uses it to exchange a rendezvous location/time with the Fallen Elves "
                "and accept the counteroffer with Y. Weight is simulation."
            ),
        ),
    )
    catalog.items.setdefault(
        GREENLEAF_CAPE_ID,
        ItemTemplate(
            template_id=GREENLEAF_CAPE_ID,
            name="Greenleaf Cape",
            kind=ItemKind.MISC,
            weight=1.1,
            stack_limit=1,
            tags=("floor_7", "elf_war", "kizmel", "castle_galey_treasury", "arid_weakness_protection"),
            provenance=_canon(
                "Treasured cape borrowed from Castle Galey's treasury. It protects Kizmel from the arid-region weakness that would otherwise affect an elf in the Field of Bones. Weight is simulation."
            ),
        ),
    )
    catalog.items.setdefault(
        RUBY_KEY_ID,
        ItemTemplate(
            template_id=RUBY_KEY_ID,
            name="Ruby Key",
            kind=ItemKind.QUEST,
            weight=0.12,
            stack_limit=1,
            tags=("floor_7", "elf_war", "sacred_key", "ruby_key"),
            provenance=_canon(
                "The Ruby Key is the Floor 7 sacred key pursued by the Dark Elves and Fallen Elves. Weight is simulation."
            ),
        ),
    )
    CORE_NPCS.setdefault(
        ARGO_ID,
        NPCDefinition(
            npc_id=ARGO_ID,
            name="Argo",
            home_location_id="floor_7_volupta",
            roles=("named_player", "information_broker", "frontline_scout", "claw_user"),
            quest_ids=(),
            knowledge_tags=("floor_7", "volupta", "fallen_elves", "field_of_bones", "ant_tunnel_valley", "labyrinth"),
            provenance=_canon(
                "Named player information broker accompanying Kirito, Asuna, Kizmel, Kio and Nirrnir during the Floor 7 Fallen Elf pursuit."
            ),
        ),
    )
    return catalog

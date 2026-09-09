from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.floor8_world import ACORN_SHOP
from sao_mcp.corpus.progressive_guilds import ALS_GUILD_ID, DKB_GUILD_ID
from sao_mcp.domain.models import Provenance, ProvenanceKind
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_9 = "Sword Art Online Progressive Volume 9: Nocturne of the Blue Reflected Moon (Start)"
KLEIN_ID = "pc_klein"


@dataclass(slots=True, frozen=True)
class Floor8GuildCrisisReport:
    affected_guild_ids: tuple[str, ...]
    affected_member_scope: str
    trigger_kind: str
    trigger_location_scope: str
    escalation_depends_on_guild_leaders: bool
    provenance: Provenance


FLOOR8_GUILD_CRISIS_REPORT = Floor8GuildCrisisReport(
    affected_guild_ids=(DKB_GUILD_ID, ALS_GUILD_ID),
    affected_member_scope="majority_of_each_guild",
    trigger_kind="felled_large_living_tree",
    trigger_location_scope="forest_elf_capital_area",
    escalation_depends_on_guild_leaders=True,
    provenance=Provenance(
        ProvenanceKind.CANON_INFERRED,
        sources=(PROGRESSIVE_9,),
        notes=(
            "Late in Progressive 9, Argo reports a Floor 8 Forest Elf crisis involving most members of both DKB and ALS. "
            "The immediate cause is the felling of a large living tree in the Forest Elf capital area, and further escalation depends on the two guild leaders' decisions. "
            "No exact affected-member count or forced leader decision is asserted."
        ),
    ),
)


def apply_floor8_progressive_corpus(catalog: Catalog) -> Catalog:
    CORE_NPCS.setdefault(
        KLEIN_ID,
        NPCDefinition(
            npc_id=KLEIN_ID,
            name="Klein",
            home_location_id=ACORN_SHOP,
            roles=("named_player", "frontline_player", "katana_user"),
            quest_ids=(),
            knowledge_tags=("floor_1", "floor_8", "frieben", "argo", "acorn_shop"),
            provenance=Provenance(
                ProvenanceKind.CANON_INFERRED,
                sources=(PROGRESSIVE_9,),
                notes=(
                    "Progressive 9 reunites Kirito with Klein at Argo's Acorn Shop rendezvous in Frieben. "
                    "The runtime keeps Klein's exact combat level and numeric stats outside this corpus as simulation fields."
                ),
            ),
        ),
    )
    return catalog

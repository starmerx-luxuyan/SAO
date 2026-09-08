from __future__ import annotations

from sao_mcp.corpus.core import Catalog
from sao_mcp.corpus.floor6_stachion import QUEST_ID
from sao_mcp.domain.models import ItemKind, ItemTemplate, Provenance, ProvenanceKind
from sao_mcp.rules.npcs import CORE_NPCS, NPCDefinition


PROGRESSIVE_6 = "Sword Art Online Progressive Volume 6: Canon of the Golden Rule (Finish)"
MYIA_ID = "npc_floor6_myia"
THEANO_ID = "npc_floor6_theano"
BARRO_ID = "npc_floor6_pithagrus_former_gardener"
THEANO_IRON_KEY_ID = "theano_iron_key"


def _canon(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON, sources=(PROGRESSIVE_6,), notes=notes)


def _inferred(notes: str) -> Provenance:
    return Provenance(ProvenanceKind.CANON_INFERRED, sources=(PROGRESSIVE_6,), notes=notes)


def apply_floor6_trials_corpus(catalog: Catalog) -> Catalog:
    catalog.items.setdefault(
        THEANO_IRON_KEY_ID,
        ItemTemplate(
            template_id=THEANO_IRON_KEY_ID,
            name="Theano's Iron Key",
            kind=ItemKind.QUEST,
            weight=0.08,
            stack_limit=1,
            tags=(
                "floor_6",
                "curse_of_stachion",
                "paired_iron_key",
                "theano",
                "direction_vibration",
                "distance_resonance",
            ),
            provenance=_canon(
                "Theano leaves her iron key to Myia when she disappears after Cylon's death. It forms a paired set with Cylon's iron key: vibration indicates direction and resonance indicates distance. Weight is simulation."
            ),
        ),
    )

    CORE_NPCS.setdefault(
        MYIA_ID,
        NPCDefinition(
            npc_id=MYIA_ID,
            name="Myia",
            home_location_id="floor_6_myia_house",
            roles=("theano_daughter", "swordswoman", "curse_of_stachion_release_route"),
            quest_ids=(QUEST_ID,),
            knowledge_tags=(
                "theano_missing",
                "paired_iron_keys",
                "barro",
                "cylon_death",
                "dungeon_of_trials",
            ),
            provenance=_canon(
                "Theano's young daughter. After Cylon's death, she carries her mother's iron key and explains that Theano vanished after leaving a note."
            ),
        ),
    )
    CORE_NPCS.setdefault(
        THEANO_ID,
        NPCDefinition(
            npc_id=THEANO_ID,
            name="Theano",
            home_location_id="floor_6_myia_house",
            roles=("former_servant", "puzzle_expert", "swordswoman", "missing_npc"),
            quest_ids=(QUEST_ID,),
            knowledge_tags=(
                "pithagrus_murder_truth",
                "dungeon_of_trials",
                "bloody_golden_cube",
                "secret_back_door",
                "paired_iron_keys",
            ),
            provenance=_canon(
                "Former servant of the Stachion lord's manor, secretly trained by Pithagrus as his intended successor, and witness to Cylon's murder of Pithagrus. In the release route she disappears into the Dungeon of Trials after Cylon dies."
            ),
        ),
    )

    # The former gardener from the seven-person investigation is canonically Barro.
    CORE_NPCS[BARRO_ID] = NPCDefinition(
        npc_id=BARRO_ID,
        name="Barro",
        home_location_id="floor_6_stachion_puzzle_quarter",
        roles=("stachion_witness", "pithagrus_associate", "former_gardener", "terro_father"),
        quest_ids=(),
        knowledge_tags=("pithagrus", "theano", "suribus_second_home", "curse_of_stachion"),
        provenance=_canon(
            "Former gardener at the lord's mansion during Theano's service and father of Terro. Theano's disappearance note tells Myia to visit Barro if she does not return."
        ),
    )
    return catalog

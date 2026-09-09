from __future__ import annotations

from dataclasses import dataclass

from sao_mcp.corpus.floor8_world import SLUVA
from sao_mcp.domain.models import Provenance, ProvenanceKind


DARK_ELVES = "dark_elves"
FOREST_ELVES = "forest_elves"
FALLEN_ELVES = "fallen_elves"


@dataclass(slots=True, frozen=True)
class LocationAccessRule:
    location_id: str
    forbidden_faction_ids: tuple[str, ...] = ()
    provenance: Provenance = Provenance(ProvenanceKind.SIMULATION)


LOCATION_ACCESS_RULES: dict[str, LocationAccessRule] = {
    SLUVA: LocationAccessRule(
        location_id=SLUVA,
        forbidden_faction_ids=(DARK_ELVES,),
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=("Sword Art Online Progressive Volume 9",),
            notes="Dark Elves cannot enter the Forest Elf capital Sluva on Floor 8.",
        ),
    ),
}

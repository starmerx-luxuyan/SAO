from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sao_mcp.domain.models import Provenance, ProvenanceKind


DAY_MS = 24 * 60 * 60 * 1000
HOUR_MS = 60 * 60 * 1000
SAO_LAUNCH_DATE = date(2022, 11, 6)
SAO_LAUNCH_TIME_OF_DAY_MS = 13 * HOUR_MS
SAO_LAUNCH_ANCHOR_LABEL = "2022-11-06T13:00:00+09:00"


@dataclass(slots=True, frozen=True)
class CanonicalMilestoneSeed:
    seed_id: str
    milestone_kind: str
    subject_id: str
    calendar_date: str
    window_start_offset_ms: int
    window_end_offset_ms: int
    provenance: Provenance
    notes: str = ""


@dataclass(slots=True, frozen=True)
class CanonicalTimelineProfile:
    profile_id: str
    name: str
    continuity: str
    anchor_label: str
    seeds: tuple[CanonicalMilestoneSeed, ...]

    def seed(self, seed_id: str) -> CanonicalMilestoneSeed:
        for seed in self.seeds:
            if seed.seed_id == seed_id:
                return seed
        raise KeyError(seed_id)


def _calendar_day_window(target: date) -> tuple[int, int]:
    """Map a canon calendar date onto world-ms without inventing an exact event clock time."""

    midnight_offset = (target - SAO_LAUNCH_DATE).days * DAY_MS - SAO_LAUNCH_TIME_OF_DAY_MS
    return midnight_offset, midnight_offset + DAY_MS - 1


def _floor_boss_seed(
    floor_number: int,
    defeated_on: date,
    *,
    source: str,
    continuity: str,
) -> CanonicalMilestoneSeed:
    start_ms, end_ms = _calendar_day_window(defeated_on)
    return CanonicalMilestoneSeed(
        seed_id=f"floor{floor_number}.boss_defeated",
        milestone_kind="floor_boss_defeated",
        subject_id=f"floor:{floor_number}",
        calendar_date=defeated_on.isoformat(),
        window_start_offset_ms=start_ms,
        window_end_offset_ms=end_ms,
        provenance=Provenance(
            ProvenanceKind.CANON,
            sources=(source,),
            notes=(
                f"{continuity} gives the calendar date for this clear. The profile deliberately keeps a full-day "
                "window unless the source establishes an exact event time; runtime timing remains simulation-authoritative."
            ),
        ),
        notes="Canonical expectation only; it never unlocks a floor or forces a boss outcome.",
    )


PROGRESSIVE_NOVEL_EARLY_AINCRAD = CanonicalTimelineProfile(
    profile_id="progressive_novel_early_aincrad_v1",
    name="Progressive novel early Aincrad",
    continuity="Sword Art Online Progressive light-novel continuity",
    anchor_label=SAO_LAUNCH_ANCHOR_LABEL,
    seeds=(
        _floor_boss_seed(
            1,
            date(2022, 12, 4),
            source="Sword Art Online Progressive Volume 1: Aria of a Starless Night, Part 6",
            continuity="Progressive novel continuity",
        ),
        _floor_boss_seed(
            2,
            date(2022, 12, 14),
            source="Sword Art Online Progressive Volume 1: Rondo of a Fragile Blade, Part 12",
            continuity="Progressive novel continuity",
        ),
        _floor_boss_seed(
            3,
            date(2022, 12, 21),
            source="Sword Art Online Progressive Volume 2: Concerto of Black and White, Part 9",
            continuity="Progressive novel continuity",
        ),
        _floor_boss_seed(
            4,
            date(2022, 12, 27),
            source="Sword Art Online Progressive Volume 3: Barcarolle of Froth, Part 8",
            continuity="Progressive novel continuity",
        ),
        _floor_boss_seed(
            5,
            date(2022, 12, 31),
            source="Sword Art Online Progressive Volume 4: Scherzo of Deep Night, Part 10",
            continuity="Progressive novel continuity",
        ),
    ),
)


ANIME_CORE_AINCRAD = CanonicalTimelineProfile(
    profile_id="anime_core_aincrad_v1",
    name="Anime core Aincrad",
    continuity="Sword Art Online television-anime continuity",
    anchor_label=SAO_LAUNCH_ANCHOR_LABEL,
    seeds=(
        _floor_boss_seed(
            1,
            date(2022, 12, 3),
            source="Sword Art Online official chronology: Episode 2, Beater",
            continuity="Anime continuity",
        ),
    ),
)


CANONICAL_TIMELINE_PROFILES: dict[str, CanonicalTimelineProfile] = {
    profile.profile_id: profile
    for profile in (PROGRESSIVE_NOVEL_EARLY_AINCRAD, ANIME_CORE_AINCRAD)
}
DEFAULT_CANONICAL_TIMELINE_PROFILE_ID = PROGRESSIVE_NOVEL_EARLY_AINCRAD.profile_id

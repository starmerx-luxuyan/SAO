from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:150]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# A detainee may move only as the explicit object of an escorted movement authority.
# This is intentionally a separate API, not a generic ignore-restriction switch.
path = "src/sao_mcp/rules/group_travel.py"
replace_once(
    path,
    '''def exit_encounter_via_travel(
''',
    '''def escorted_travel_together(
    runtime,
    detainee_ids: list[str] | tuple[str, ...],
    escort_ids: list[str] | tuple[str, ...],
    destination_id: str,
) -> GroupTravelResolution:
    detainees = tuple(detainee_ids)
    escorts = tuple(escort_ids)
    if not detainees or not escorts:
        raise ValueError("escorted travel requires detainees and escorts")
    if len(set(detainees)) != len(detainees) or len(set(escorts)) != len(escorts):
        raise ValueError("escorted travel actor ids must be unique")
    if set(detainees).intersection(escorts):
        raise ValueError("an actor cannot be both detainee and escort")

    members = detainees + escorts
    actors = [runtime.actors[actor_id] for actor_id in members]
    if any(not actor.alive for actor in actors):
        raise ValueError("all escorted travellers must be alive")
    if any(actor.location_id is None for actor in actors):
        raise ValueError("all escorted travellers must have a current world location")
    origins = {actor.location_id for actor in actors}
    if len(origins) != 1:
        raise ValueError("detainees and escorts must be colocated")
    origin = str(actors[0].location_id)

    for actor_id in detainees:
        custody = runtime.legal.custody_for(actor_id)
        if custody is None:
            raise ValueError(f"escorted traveller {actor_id} is not in custody")
    for actor_id in escorts:
        runtime.require_actor_autonomous_travel(actor_id)
    if any(actor.metadata.get("active_duel_id") for actor in actors):
        raise ValueError("escorted travel is unavailable while a traveller has an active duel")

    member_ids = set(members)
    for encounter in runtime.encounters.values():
        if not encounter.active or not member_ids.intersection(encounter.participants):
            continue
        if has_surviving_colocated_outsider(encounter, member_ids, origin):
            raise ValueError("escorted travel is unavailable while a live encounter has surviving colocated outsiders")

    if destination_id not in runtime.world_map.locations:
        raise KeyError(destination_id)
    _require_group_can_enter(runtime, actors, destination_id)
    edge = _direct_edge(runtime, origin, destination_id)
    runtime.advance_world(edge.travel_ms)
    newly_discovered = _commit_group_destination(runtime, members, actors, destination_id)
    return GroupTravelResolution(
        actor_ids=members,
        from_location_id=origin,
        to_location_id=destination_id,
        elapsed_ms=edge.travel_ms,
        newly_discovered=newly_discovered,
        traversal_tags=edge.traversal_tags,
    )


def exit_encounter_via_travel(
''',
)

# Kysarah's theft is an explicit encounter resolution. Remove the other participants through
# the encounter authority; the last-player state then closes the encounter automatically.
path = "src/sao_mcp/scenarios/floor6_elfwar.py"
replace_once(
    path,
    '''        kysarah.metadata["retreated_with_stolen_keys"] = True
        encounter.participants = {actor_id: actor}
        encounter.positions = {actor_id: encounter.positions.get(actor_id, (-1.15, 0.0))}
        kizmel_route = travel_route_together(self.runtime, [kizmel.actor_id], CASTLE_GALEY)
''',
    '''        kysarah.metadata["retreated_with_stolen_keys"] = True
        self.runtime.remove_encounter_participants(
            encounter.encounter_id,
            [myia.actor_id, gindo.actor_id, kizmel.actor_id, kysarah.actor_id],
            reason="kysarah_escape_after_theft",
        )
        kizmel_route = travel_route_together(self.runtime, [kizmel.actor_id], CASTLE_GALEY)
''',
)

# Completed First Strike duel is historical. A later safe-area attack is a new encounter,
# which proves PvP authorization ended without mutating the closed duel encounter.
path = "tests/test_duels_death.py"
replace_once(
    path,
    '''    # Advance through the first attack's post-motion; safe-zone protection should now block more damage.
    runtime.advance_encounter(encounter.encounter_id, max(0, a.recovery_until_ms - encounter.time_ms))
    hp_before = b.hp
    second, _ = runtime.attack_authoritative(
        encounter.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=2,
    )
''',
    '''    assert encounter.active is False
    assert encounter.end_reason == f"duel_completed:{duel.duel_id}"
    a.recovery_until_ms = 0
    b.recovery_until_ms = 0
    later = runtime.start_encounter(
        [a.actor_id, b.actor_id],
        zone_id="floor_1_town_of_beginnings",
    )
    hp_before = b.hp
    second, _ = runtime.attack_authoritative(
        later.encounter_id,
        a.actor_id,
        b.actor_id,
        defense=DefenseMode.NONE,
        seed=2,
    )
''',
)

# Custody begins at the cave mouth after voluntary surrender. Subsequent movement is escorted.
path = "src/sao_mcp/scenarios/floor8_standoff.py"
replace_once(
    path,
    'from sao_mcp.rules.group_travel import group_travel_record, travel_together\nfrom sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY\n',
    'from sao_mcp.rules.group_travel import escorted_travel_together, group_travel_record, travel_together\n',
)
replace_once(
    path,
    '''        representative_ids = self._frontline_ids(state)
        forest_ids = self._forest_ids(state)
        segments = [
            travel_together(self.runtime, representative_ids, FOREST_ELF_ESCAPE_CAVE_MOUTH),
            travel_together(self.runtime, representative_ids + forest_ids, FOREST_ELF_SACRED_WOODS),
            travel_together(self.runtime, representative_ids + forest_ids, SLUVA),
        ]
        state["custody_transfer_route"] = [group_travel_record(segment) for segment in segments]
        for actor_id in representative_ids:
            actor = self.runtime.actors[actor_id]
            actor.metadata["forest_elf_custody_started_at_ms"] = self.runtime.world.now_ms
            actor.metadata[AUTONOMOUS_TRAVEL_RESTRICTION_KEY] = FOREST_ELF_CUSTODY_RESTRICTION
        state["custody_actor_ids"] = list(representative_ids)
''',
    '''        representative_ids = self._frontline_ids(state)
        forest_ids = self._forest_ids(state)
        approach = travel_together(self.runtime, representative_ids, FOREST_ELF_ESCAPE_CAVE_MOUTH)
        case_id = f"floor8_sluva:{instance_id}"
        authority_id = self._forest_leader_id(state)
        for actor_id in representative_ids:
            self.runtime.take_actor_custody(
                actor_id,
                custody_id=f"custody:{case_id}:{actor_id}",
                authority_id=authority_id,
                case_id=case_id,
                restriction_code=FOREST_ELF_CUSTODY_RESTRICTION,
                reason="protected_tree_incident_local_representative_handoff",
            )
        segments = [
            approach,
            escorted_travel_together(
                self.runtime, representative_ids, forest_ids, FOREST_ELF_SACRED_WOODS
            ),
            escorted_travel_together(self.runtime, representative_ids, forest_ids, SLUVA),
        ]
        state["custody_transfer_route"] = [group_travel_record(segment) for segment in segments]
        state["custody_actor_ids"] = list(representative_ids)
        state["custody_case_id"] = case_id
''',
)

# Sluva docket is evidence/audit. LegalStateLedger decides current custody and sentence state.
path = "src/sao_mcp/scenarios/floor8_sluva.py"
replace_once(
    path,
    'from sao_mcp.rules.group_travel import group_travel_record, travel_together\n',
    'from sao_mcp.rules.group_travel import escorted_travel_together, group_travel_record\nfrom sao_mcp.rules.legal_state import SentenceKind, SentenceStatus\n',
)
replace_once(
    path,
    'from sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY\n',
    '',
)
replace_once(
    path,
    '''    def _require_custody(self, actor_ids: list[str]) -> None:
        wrong = [
            actor_id
            for actor_id in actor_ids
            if self.runtime.actors[actor_id].metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY)
            != FOREST_ELF_CUSTODY_RESTRICTION
        ]
        if wrong:
            raise RuntimeError(f"actors are no longer in authoritative Forest Elf custody: {', '.join(wrong)}")
''',
    '''    def _require_custody(self, actor_ids: list[str]) -> None:
        wrong = []
        for actor_id in actor_ids:
            custody = self.runtime.legal.custody_for(actor_id)
            if custody is None or custody.restriction_code != FOREST_ELF_CUSTODY_RESTRICTION:
                wrong.append(actor_id)
        if wrong:
            raise RuntimeError(f"actors are no longer in authoritative Forest Elf custody: {', '.join(wrong)}")
''',
)
replace_once(
    path,
    '''    def _release_actor_custody(self, actor_id: str, *, resolution: str) -> None:
        actor = self.runtime.actors[actor_id]
        if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) != FOREST_ELF_CUSTODY_RESTRICTION:
            raise RuntimeError(f"actor {actor_id} is not in authoritative Forest Elf custody")
        actor.metadata["forest_elf_custody_ended_at_ms"] = self.runtime.world.now_ms
        actor.metadata["forest_elf_custody_resolution"] = resolution
        del actor.metadata[AUTONOMOUS_TRAVEL_RESTRICTION_KEY]
''',
    '''    def _release_actor_custody(self, actor_id: str, *, resolution: str) -> None:
        custody = self.runtime.legal.custody_for(actor_id)
        if custody is None or custody.restriction_code != FOREST_ELF_CUSTODY_RESTRICTION:
            raise RuntimeError(f"actor {actor_id} is not in authoritative Forest Elf custody")
        self.runtime.release_actor_custody(actor_id, resolution=resolution)
''',
)
replace_once(
    path,
    '''            "status": "hearing_open",
            "arbiter_actor_id": arbiter.actor_id,
''',
    '''            "status": "hearing_open",
            "case_id": state["custody_case_id"],
            "arbiter_actor_id": arbiter.actor_id,
''',
)
replace_once(
    path,
    '''        outward = travel_together(self.runtime, custody_ids + forest_ids, FOREST_ELF_SACRED_WOODS)
        service_started = self.runtime.world.now_ms
        self.runtime.advance_world(RESTORATIVE_SERVICE_MS)
        returning = travel_together(self.runtime, custody_ids + forest_ids, SLUVA)
''',
    '''        outward = escorted_travel_together(
            self.runtime, custody_ids, forest_ids, FOREST_ELF_SACRED_WOODS
        )
        service_started = self.runtime.world.now_ms
        self.runtime.advance_world(RESTORATIVE_SERVICE_MS)
        returning = escorted_travel_together(self.runtime, custody_ids, forest_ids, SLUVA)
''',
)
replace_once(
    path,
    '''        if disposition == "strict":
            sentences = {
                actor_id: "execution_ordered" if actor_id == principal_actor_id else "imprisonment_ordered"
                for actor_id in custody_ids
            }
            state["stage"] = "sluva_disposition_strict"
        elif disposition == "commuted":
            sentences = {actor_id: "imprisonment_ordered" for actor_id in custody_ids}
            state["stage"] = "sluva_disposition_commuted"
        else:
            self._release_custody(state, resolution="sluva_explicit_pardon")
            sentences = {actor_id: "pardoned" for actor_id in custody_ids}
            state["stage"] = "sluva_disposition_pardon"
''',
    '''        sentence_ids: dict[str, str] = {}
        if disposition == "strict":
            sentences = {}
            for actor_id in custody_ids:
                kind = SentenceKind.EXECUTION if actor_id == principal_actor_id else SentenceKind.IMPRISONMENT
                sentence = self.runtime.issue_sentence_order(
                    actor_id,
                    sentence_id=f"sluva_sentence:{instance_id}:{actor_id}",
                    case_id=docket["case_id"],
                    authority_id=arbiter_actor_id,
                    kind=kind,
                )
                sentence_ids[actor_id] = sentence.sentence_id
                sentences[actor_id] = "execution_ordered" if kind is SentenceKind.EXECUTION else "imprisonment_ordered"
            state["stage"] = "sluva_disposition_strict"
        elif disposition == "commuted":
            sentences = {}
            for actor_id in custody_ids:
                sentence = self.runtime.issue_sentence_order(
                    actor_id,
                    sentence_id=f"sluva_sentence:{instance_id}:{actor_id}",
                    case_id=docket["case_id"],
                    authority_id=arbiter_actor_id,
                    kind=SentenceKind.IMPRISONMENT,
                )
                sentence_ids[actor_id] = sentence.sentence_id
                sentences[actor_id] = "imprisonment_ordered"
            state["stage"] = "sluva_disposition_commuted"
        else:
            self._release_custody(state, resolution="sluva_explicit_pardon")
            sentences = {actor_id: "pardoned" for actor_id in custody_ids}
            state["stage"] = "sluva_disposition_pardon"
''',
)
replace_once(
    path,
    '''            "sentences": sentences,
            "issued_at_ms": self.runtime.world.now_ms,
''',
    '''            "sentences": sentences,
            "sentence_ids": sentence_ids,
            "issued_at_ms": self.runtime.world.now_ms,
''',
)
replace_once(
    path,
    '''        sentences = docket["disposition"]["sentences"]
        imprisonment_actor_ids = [
            actor_id for actor_id, sentence in sentences.items() if sentence == "imprisonment_ordered"
        ]
        execution_order_actor_ids = [
            actor_id for actor_id, sentence in sentences.items() if sentence == "execution_ordered"
        ]
        if not imprisonment_actor_ids:
            raise ValueError("this disposition contains no imprisonment order to enforce")
        self._require_ids_at(imprisonment_actor_ids + execution_order_actor_ids, SLUVA)
        self._require_custody(imprisonment_actor_ids + execution_order_actor_ids)

        started_at_ms = self.runtime.world.now_ms
''',
    '''        current_sentences = {
            actor_id: self.runtime.legal.sentence_for(actor_id)
            for actor_id in self._custody_ids(state)
        }
        imprisonment_actor_ids = [
            actor_id
            for actor_id, sentence in current_sentences.items()
            if sentence is not None
            and sentence.case_id == docket["case_id"]
            and sentence.kind is SentenceKind.IMPRISONMENT
            and sentence.status is SentenceStatus.ORDERED
        ]
        execution_order_actor_ids = [
            actor_id
            for actor_id, sentence in current_sentences.items()
            if sentence is not None
            and sentence.case_id == docket["case_id"]
            and sentence.kind is SentenceKind.EXECUTION
            and sentence.status is SentenceStatus.ORDERED
        ]
        if not imprisonment_actor_ids:
            raise ValueError("this disposition contains no imprisonment order to enforce")
        self._require_ids_at(imprisonment_actor_ids + execution_order_actor_ids, SLUVA)
        self._require_custody(imprisonment_actor_ids + execution_order_actor_ids)

        started_at_ms = self.runtime.world.now_ms
        for actor_id in imprisonment_actor_ids:
            self.runtime.begin_imprisonment_sentence(actor_id, duration_ms=imprisonment_duration_ms)
''',
)
replace_once(
    path,
    '''        enforcement = docket["sentence_enforcement"]
        release_at_ms = enforcement["imprisonment_release_at_ms"]
        if self.runtime.world.now_ms < release_at_ms:
            raise ValueError("the active imprisonment term has not reached its release time")
        imprisonment_actor_ids = list(enforcement["imprisonment_actor_ids"])
        self._require_ids_at(imprisonment_actor_ids, SLUVA)
        self._require_custody(imprisonment_actor_ids)
        for actor_id in imprisonment_actor_ids:
            self._release_actor_custody(actor_id, resolution="sluva_imprisonment_completed")
''',
    '''        enforcement = docket["sentence_enforcement"]
        imprisonment_actor_ids = [
            actor_id
            for actor_id in self._custody_ids(state)
            if (
                (sentence := self.runtime.legal.sentence_for(actor_id)) is not None
                and sentence.case_id == docket["case_id"]
                and sentence.kind is SentenceKind.IMPRISONMENT
                and sentence.status is SentenceStatus.ACTIVE
            )
        ]
        if not imprisonment_actor_ids:
            raise ValueError("there is no active Sluva imprisonment term to complete")
        release_at_ms = max(
            int(self.runtime.legal.sentence_for(actor_id).release_at_ms)
            for actor_id in imprisonment_actor_ids
        )
        if self.runtime.world.now_ms < release_at_ms:
            raise ValueError("the active imprisonment term has not reached its release time")
        self._require_ids_at(imprisonment_actor_ids, SLUVA)
        self._require_custody(imprisonment_actor_ids)
        for actor_id in imprisonment_actor_ids:
            self.runtime.complete_imprisonment_sentence(
                actor_id, resolution="sluva_imprisonment_completed"
            )
''',
)
replace_once(
    path,
    '''        disposition = docket["disposition"]
        sentences = (
            dict(disposition["sentences"])
            if disposition is not None
            else {actor_id: None for actor_id in docket["custody_actor_ids"]}
        )
        enforcement = docket["sentence_enforcement"]
        remaining_ms = (
            max(0, enforcement["imprisonment_release_at_ms"] - self.runtime.world.now_ms)
            if enforcement is not None and enforcement["status"] == "imprisonment_active"
            else None
        )
''',
    '''        disposition = docket["disposition"]
        sentences: dict[str, str | None] = {}
        active_release_times: list[int] = []
        for actor_id in docket["custody_actor_ids"]:
            sentence = self.runtime.legal.sentence_for(actor_id)
            if sentence is not None:
                if sentence.kind is SentenceKind.EXECUTION:
                    sentences[actor_id] = "execution_ordered"
                elif sentence.status is SentenceStatus.ACTIVE:
                    sentences[actor_id] = "imprisonment_active"
                    if sentence.release_at_ms is not None:
                        active_release_times.append(sentence.release_at_ms)
                else:
                    sentences[actor_id] = "imprisonment_ordered"
            elif disposition is not None and disposition["kind"] == "pardon":
                sentences[actor_id] = "pardoned"
            elif (
                docket["sentence_enforcement"] is not None
                and actor_id in docket["sentence_enforcement"]["imprisonment_actor_ids"]
                and docket["sentence_enforcement"]["status"] == "imprisonment_completed"
            ):
                sentences[actor_id] = "imprisonment_completed"
            else:
                sentences[actor_id] = None
        remaining_ms = (
            max(0, max(active_release_times) - self.runtime.world.now_ms)
            if active_release_times
            else None
        )
''',
)
replace_once(
    path,
    '''                "custody_active": {
                    actor_id: (
                        self.runtime.actors[actor_id].metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY)
                        == FOREST_ELF_CUSTODY_RESTRICTION
                    )
                    for actor_id in docket["custody_actor_ids"]
                },
''',
    '''                "custody_active": {
                    actor_id: self.runtime.legal.custody_for(actor_id) is not None
                    for actor_id in docket["custody_actor_ids"]
                },
''',
)

# Test fixtures create actual LegalState custody rather than writing a travel metadata projection.
path = "tests/test_floor8_sluva.py"
replace_once(
    path,
    'from sao_mcp.rules.travel import AUTONOMOUS_TRAVEL_RESTRICTION_KEY\n',
    '',
)
replace_once(
    path,
    '''        actor = runtime.create_character(f"Sluva Custody {index}", level=26)
        actor.location_id = SLUVA
        actor.metadata[AUTONOMOUS_TRAVEL_RESTRICTION_KEY] = FOREST_ELF_CUSTODY_RESTRICTION
        guild = guilds[guild_id]
''',
    '''        actor = runtime.create_character(f"Sluva Custody {index}", level=26)
        actor.location_id = SLUVA
        guild = guilds[guild_id]
''',
)
replace_once(
    path,
    '''    runtime.world.global_flags["floor8_forest_emergency_instances"] = {
        INSTANCE_ID: {
            "instance_id": INSTANCE_ID,
            "stage": "standoff_resolved_custody",
            "floor8_actor_ids": [players[0].actor_id],
            "custody_actor_ids": [actor.actor_id for actor in players],
''',
    '''    case_id = f"floor8_sluva:{INSTANCE_ID}"
    for actor in players:
        runtime.take_actor_custody(
            actor.actor_id,
            custody_id=f"custody:{case_id}:{actor.actor_id}",
            authority_id=forest[0].actor_id,
            case_id=case_id,
            restriction_code=FOREST_ELF_CUSTODY_RESTRICTION,
            reason="test_sluva_fixture",
        )
    runtime.world.global_flags["floor8_forest_emergency_instances"] = {
        INSTANCE_ID: {
            "instance_id": INSTANCE_ID,
            "stage": "standoff_resolved_custody",
            "floor8_actor_ids": [players[0].actor_id],
            "custody_actor_ids": [actor.actor_id for actor in players],
            "custody_case_id": case_id,
''',
)
replace_once(
    path,
    '''    assert players[0].metadata[AUTONOMOUS_TRAVEL_RESTRICTION_KEY] == FOREST_ELF_CUSTODY_RESTRICTION
    assert all(AUTONOMOUS_TRAVEL_RESTRICTION_KEY not in actor.metadata for actor in players[1:])
    assert all(actor.metadata["forest_elf_custody_resolution"] == "sluva_imprisonment_completed" for actor in players[1:])
''',
    '''    assert runtime.actor_custody_state(players[0].actor_id)["restriction_code"] == FOREST_ELF_CUSTODY_RESTRICTION
    assert all(runtime.actor_custody_state(actor.actor_id) is None for actor in players[1:])
    assert all("autonomous_travel_restriction" not in actor.metadata for actor in players)
''',
)
replace_once(
    path,
    '''    assert all(AUTONOMOUS_TRAVEL_RESTRICTION_KEY not in actor.metadata for actor in players)
    assert all(pardoned["custody_active"][actor.actor_id] is False for actor in players)
''',
    '''    assert all(runtime.actor_custody_state(actor.actor_id) is None for actor in players)
    assert all("autonomous_travel_restriction" not in actor.metadata for actor in players)
    assert all(pardoned["custody_active"][actor.actor_id] is False for actor in players)
''',
)
replace_once(
    path,
    '''    assert all(completed["custody_active"][actor.actor_id] is False for actor in players)
    assert all(AUTONOMOUS_TRAVEL_RESTRICTION_KEY not in actor.metadata for actor in players)
    assert all(actor.alive for actor in players)
''',
    '''    assert all(completed["custody_active"][actor.actor_id] is False for actor in players)
    assert all(runtime.actor_custody_state(actor.actor_id) is None for actor in players)
    assert all("autonomous_travel_restriction" not in actor.metadata for actor in players)
    assert all(actor.alive for actor in players)
''',
)

path = "tests/test_floor8_standoff.py"
replace_once(
    path,
    '''    assert all(
        runtime.actors[actor_id].metadata[AUTONOMOUS_TRAVEL_RESTRICTION_KEY] == FOREST_ELF_CUSTODY_RESTRICTION
        for actor_id in representative_ids
    )
''',
    '''    assert all(
        runtime.actor_custody_state(actor_id)["restriction_code"] == FOREST_ELF_CUSTODY_RESTRICTION
        and runtime.actor_custody_state(actor_id)["case_id"] == f"floor8_sluva:{instance_id}"
        for actor_id in representative_ids
    )
''',
)
replace_once(
    path,
    '''    assert all(
        "forest_elf_custody" not in runtime.actors[actor_id].metadata
        and "forest_elf_custody_location_id" not in runtime.actors[actor_id].metadata
        for actor_id in representative_ids
    )
''',
    '''    assert all(
        AUTONOMOUS_TRAVEL_RESTRICTION_KEY not in runtime.actors[actor_id].metadata
        and "forest_elf_custody_location_id" not in runtime.actors[actor_id].metadata
        for actor_id in representative_ids
    )
''',
)

from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Encounter current time/lifecycle belongs to EncounterState, not to an event payload.
replace_once(
    "src/sao_mcp/domain/models.py",
    '''class EncounterState:\n    encounter_id: str\n    participants: dict[str, CombatantState]\n    zone_id: str\n    time_ms: int = 0\n    safe_zone: bool = False\n    anti_crystal: bool = False\n    threat: dict[str, dict[str, float]] = field(default_factory=dict)\n    last_attacker_by_target: dict[str, str] = field(default_factory=dict)\n    last_attack_time_by_target: dict[str, int] = field(default_factory=dict)\n    events: list[CombatEvent] = field(default_factory=list)\n    positions: dict[str, tuple[float, float]] = field(default_factory=dict)\n    arena_radius_m: float = 30.0\n''',
    '''class EncounterState:\n    encounter_id: str\n    participants: dict[str, CombatantState]\n    zone_id: str\n    world_started_at_ms: int = 0\n    time_ms: int = 0\n    safe_zone: bool = False\n    anti_crystal: bool = False\n    ended_at_world_ms: int | None = None\n    end_reason: str | None = None\n    threat: dict[str, dict[str, float]] = field(default_factory=dict)\n    last_attacker_by_target: dict[str, str] = field(default_factory=dict)\n    last_attack_time_by_target: dict[str, int] = field(default_factory=dict)\n    events: list[CombatEvent] = field(default_factory=list)\n    positions: dict[str, tuple[float, float]] = field(default_factory=dict)\n    arena_radius_m: float = 30.0\n\n    @property\n    def active(self) -> bool:\n        return self.ended_at_world_ms is None\n''',
)

# GameRuntime owns the legal ledger and explicit encounter membership/lifecycle authority.
path = "src/sao_mcp/runtime/engine.py"
replace_once(
    path,
    'from sao_mcp.rules.items import ConsumableResolution, tick_statuses, use_consumable\n',
    'from sao_mcp.rules.items import ConsumableResolution, tick_statuses, use_consumable\nfrom sao_mcp.rules.legal_state import LegalStateLedger, SentenceKind\n',
)
replace_once(
    path,
    '        self.npcs = NPCRuntime()\n        self.actors: dict[str, CombatantState] = {}\n',
    '        self.npcs = NPCRuntime()\n        self.legal = LegalStateLedger()\n        self.actors: dict[str, CombatantState] = {}\n',
)
replace_once(
    path,
    '''        location = self.world_map.locations.get(zone_id)\n        resolved_safe = location.safe_zone if location and safe_zone is None else bool(safe_zone)\n        resolved_anti = location.anti_crystal if location and anti_crystal is None else bool(anti_crystal)\n        encounter = EncounterState(\n            encounter_id=_id("enc"),\n            participants={actor_id: self.actors[actor_id] for actor_id in actor_ids},\n            zone_id=zone_id,\n            safe_zone=resolved_safe,\n            anti_crystal=resolved_anti,\n        )\n''',
    '''        for actor_id in actor_ids:\n            conflicts = [\n                encounter_id\n                for encounter_id, existing in self.encounters.items()\n                if existing.active and actor_id in existing.participants\n            ]\n            if conflicts:\n                raise ValueError(f"actor {actor_id} is already in active encounter {conflicts[0]}")\n        location = self.world_map.locations.get(zone_id)\n        resolved_safe = location.safe_zone if location and safe_zone is None else bool(safe_zone)\n        resolved_anti = location.anti_crystal if location and anti_crystal is None else bool(anti_crystal)\n        encounter = EncounterState(\n            encounter_id=_id("enc"),\n            participants={actor_id: self.actors[actor_id] for actor_id in actor_ids},\n            zone_id=zone_id,\n            world_started_at_ms=self.world.now_ms,\n            safe_zone=resolved_safe,\n            anti_crystal=resolved_anti,\n        )\n''',
)
replace_once(
    path,
    '''        self._append(\n            encounter,\n            "encounter_started",\n            None,\n            None,\n            world_started_at_ms=self.world.now_ms,\n        )\n''',
    '''        self._append(encounter, "encounter_started", None, None)\n''',
)
replace_once(
    path,
    '''    @staticmethod\n    def _encounter_world_started_at_ms(encounter: EncounterState) -> int:\n        anchors = [event for event in encounter.events if event.event_type == "encounter_started"]\n        if len(anchors) != 1:\n            raise RuntimeError(\n                f"encounter {encounter.encounter_id} must contain exactly one encounter_started event"\n            )\n        anchor = anchors[0]\n        if anchor.time_ms != 0:\n            raise RuntimeError(\n                f"encounter {encounter.encounter_id} start event must be at encounter time zero"\n            )\n        value = anchor.payload.get("world_started_at_ms")\n        if not isinstance(value, int) or isinstance(value, bool) or value < 0:\n            raise RuntimeError(\n                f"encounter {encounter.encounter_id} has an invalid world_started_at_ms anchor"\n            )\n        return value\n\n    def encounter_world_time_ms(self, encounter_id: str) -> int:\n        encounter = self.encounters[encounter_id]\n        return self._encounter_world_started_at_ms(encounter) + encounter.time_ms\n''',
    '''    @staticmethod\n    def _encounter_world_started_at_ms(encounter: EncounterState) -> int:\n        value = encounter.world_started_at_ms\n        if not isinstance(value, int) or isinstance(value, bool) or value < 0:\n            raise RuntimeError(\n                f"encounter {encounter.encounter_id} has an invalid world_started_at_ms anchor"\n            )\n        return value\n\n    def encounter_world_time_ms(self, encounter_id: str) -> int:\n        encounter = self.encounters[encounter_id]\n        return encounter.world_started_at_ms + encounter.time_ms\n\n    def require_active_encounter(self, encounter_id: str) -> EncounterState:\n        encounter = self.encounters[encounter_id]\n        if not encounter.active:\n            raise ValueError(f"encounter {encounter_id} has ended")\n        return encounter\n\n    def add_encounter_participant(\n        self,\n        encounter_id: str,\n        actor_id: str,\n        *,\n        position: tuple[float, float] | None = None,\n    ) -> CombatantState:\n        encounter = self.require_active_encounter(encounter_id)\n        actor = self.actors[actor_id]\n        if actor_id in encounter.participants:\n            raise ValueError("actor is already an encounter participant")\n        for other_id, other in self.encounters.items():\n            if other_id != encounter_id and other.active and actor_id in other.participants:\n                raise ValueError(f"actor {actor_id} is already in active encounter {other_id}")\n        if actor.location_id != encounter.zone_id:\n            raise ValueError("encounter participant must be physically present in the encounter zone")\n        encounter.participants[actor_id] = actor\n        if position is not None:\n            encounter.positions[actor_id] = (float(position[0]), float(position[1]))\n        self._append(encounter, "participant_joined", actor_id, None)\n        return actor\n\n    def remove_encounter_participants(\n        self,\n        encounter_id: str,\n        actor_ids: list[str] | tuple[str, ...],\n        *,\n        reason: str,\n    ) -> None:\n        encounter = self.require_active_encounter(encounter_id)\n        members = tuple(dict.fromkeys(actor_ids))\n        if not members or len(members) != len(tuple(actor_ids)):\n            raise ValueError("encounter removal requires unique actor ids")\n        missing = [actor_id for actor_id in members if actor_id not in encounter.participants]\n        if missing:\n            raise ValueError(f"actors are not encounter participants: {missing}")\n        for actor_id in members:\n            encounter.participants.pop(actor_id)\n            encounter.positions.pop(actor_id, None)\n            encounter.threat.pop(actor_id, None)\n            encounter.last_attacker_by_target.pop(actor_id, None)\n            encounter.last_attack_time_by_target.pop(actor_id, None)\n            for table in encounter.threat.values():\n                table.pop(actor_id, None)\n        self._append(\n            encounter,\n            "participants_left",\n            None,\n            None,\n            actor_ids=list(members),\n            reason=reason,\n        )\n\n    def end_encounter(self, encounter_id: str, *, reason: str) -> EncounterState:\n        if not reason:\n            raise ValueError("encounter end reason is required")\n        encounter = self.require_active_encounter(encounter_id)\n        absolute_ms = self.encounter_world_time_ms(encounter_id)\n        if self.world.now_ms < absolute_ms:\n            raise RuntimeError("world clock precedes encounter clock")\n        encounter.ended_at_world_ms = self.world.now_ms\n        encounter.end_reason = reason\n        self._append(encounter, "encounter_ended", None, None, reason=reason)\n        return encounter\n\n    def require_actor_autonomous_travel(self, actor_id: str) -> None:\n        actor = self.actors[actor_id]\n        custody = self.legal.custody_for(actor_id)\n        if custody is not None:\n            raise ValueError(f"autonomous travel is restricted by {custody.restriction_code}")\n        from sao_mcp.rules.travel import require_autonomous_travel\n\n        require_autonomous_travel(actor)\n\n    def take_actor_custody(\n        self,\n        actor_id: str,\n        *,\n        custody_id: str,\n        authority_id: str,\n        case_id: str,\n        restriction_code: str,\n        reason: str,\n    ):\n        actor = self.actors[actor_id]\n        if not actor.alive or actor.location_id is None:\n            raise ValueError("custody requires a living actor at a settled world location")\n        return self.legal.take_custody(\n            custody_id=custody_id,\n            actor_id=actor_id,\n            authority_id=authority_id,\n            case_id=case_id,\n            restriction_code=restriction_code,\n            reason=reason,\n            started_at_ms=self.world.now_ms,\n        )\n\n    def release_actor_custody(self, actor_id: str, *, resolution: str):\n        return self.legal.release_custody(\n            actor_id, resolution=resolution, released_at_ms=self.world.now_ms\n        )\n\n    def actor_custody_state(self, actor_id: str):\n        from dataclasses import asdict as _asdict\n\n        state = self.legal.custody_for(actor_id)\n        return _asdict(state) if state is not None else None\n\n    def issue_sentence_order(\n        self,\n        actor_id: str,\n        *,\n        sentence_id: str,\n        case_id: str,\n        authority_id: str,\n        kind: SentenceKind | str,\n    ):\n        custody = self.legal.custody_for(actor_id)\n        if custody is None or custody.case_id != case_id:\n            raise ValueError("sentence order requires custody in the same case")\n        return self.legal.issue_sentence(\n            sentence_id=sentence_id,\n            actor_id=actor_id,\n            case_id=case_id,\n            authority_id=authority_id,\n            kind=kind,\n            issued_at_ms=self.world.now_ms,\n        )\n\n    def begin_imprisonment_sentence(self, actor_id: str, *, duration_ms: int):\n        if self.legal.custody_for(actor_id) is None:\n            raise ValueError("imprisonment enforcement requires active custody")\n        return self.legal.begin_imprisonment(\n            actor_id, started_at_ms=self.world.now_ms, duration_ms=duration_ms\n        )\n\n    def complete_imprisonment_sentence(self, actor_id: str, *, resolution: str):\n        custody = self.legal.custody_for(actor_id)\n        if custody is None:\n            raise ValueError("imprisonment completion requires active custody")\n        sentence = self.legal.complete_imprisonment(actor_id, completed_at_ms=self.world.now_ms)\n        self.release_actor_custody(actor_id, resolution=resolution)\n        return sentence\n\n    def actor_sentence_state(self, actor_id: str):\n        from dataclasses import asdict as _asdict\n\n        state = self.legal.sentence_for(actor_id)\n        return _asdict(state) if state is not None else None\n''',
)
replace_once(
    path,
    '''    def advance_encounter(self, encounter_id: str, elapsed_ms: int) -> EncounterState:\n        if elapsed_ms < 0:\n            raise ValueError("elapsed_ms must be >= 0")\n        encounter = self.encounters[encounter_id]\n''',
    '''    def advance_encounter(self, encounter_id: str, elapsed_ms: int) -> EncounterState:\n        if elapsed_ms < 0:\n            raise ValueError("elapsed_ms must be >= 0")\n        encounter = self.require_active_encounter(encounter_id)\n''',
)
replace_once(path, '        encounter = self.encounters[encounter_id]\n        attacker = encounter.participants[attacker_id]\n', '        encounter = self.require_active_encounter(encounter_id)\n        attacker = encounter.participants[attacker_id]\n')
replace_once(path, '        encounter = self.encounters[encounter_id]\n        outgoing = encounter.participants[outgoing_id]\n', '        encounter = self.require_active_encounter(encounter_id)\n        outgoing = encounter.participants[outgoing_id]\n')
replace_once(path, '        encounter = self.encounters[encounter_id]\n        monster = encounter.participants[monster_id]\n', '        encounter = self.require_active_encounter(encounter_id)\n        monster = encounter.participants[monster_id]\n')
replace_once(
    path,
    '        encounter = self.encounters.get(encounter_id) if encounter_id else None\n        now = encounter.time_ms if encounter else self.world.now_ms\n',
    '        encounter = self.require_active_encounter(encounter_id) if encounter_id else None\n        if encounter is not None and actor_id not in encounter.participants:\n            raise ValueError("item user is not an active encounter participant")\n        now = encounter.time_ms if encounter else self.world.now_ms\n',
)
replace_once(
    path,
    '        for encounter in self.encounters.values():\n            if actor_id not in encounter.participants:\n',
    '        for encounter in self.encounters.values():\n            if not encounter.active or actor_id not in encounter.participants:\n',
)
replace_once(
    path,
    '''    def travel_actor(self, actor_id: str, destination_id: str) -> TravelResolution:\n        actor = self.actors[actor_id]\n        if self._in_live_encounter(actor_id):\n''',
    '''    def travel_actor(self, actor_id: str, destination_id: str) -> TravelResolution:\n        actor = self.actors[actor_id]\n        self.require_actor_autonomous_travel(actor_id)\n        if self._in_live_encounter(actor_id):\n''',
)
replace_once(
    path,
    '''    ) -> TravelResolution:\n        actor = self.actors[actor_id]\n        destination = require_active_teleport_gate(\n''',
    '''    ) -> TravelResolution:\n        actor = self.actors[actor_id]\n        self.require_actor_autonomous_travel(actor_id)\n        encounter = self.require_active_encounter(encounter_id) if encounter_id else None\n        if encounter is not None and actor_id not in encounter.participants:\n            raise ValueError("teleport escape requires an active encounter participant")\n        destination = require_active_teleport_gate(\n''',
)
replace_once(
    path,
    '''        if encounter_id and actor_id in self.encounters[encounter_id].participants:\n            encounter = self.encounters[encounter_id]\n            self._append(encounter, "teleport_escape", actor_id, actor_id, destination_id=destination_id)\n            encounter.participants.pop(actor_id, None)\n''',
    '''        if encounter is not None:\n            self._append(encounter, "teleport_escape", actor_id, actor_id, destination_id=destination_id)\n            self.remove_encounter_participants(\n                encounter_id, [actor_id], reason="teleport_escape"\n            )\n''',
)

# Ended encounter history must never constrain current movement.
replace_once(
    "src/sao_mcp/rules/travel.py",
    '''def has_surviving_colocated_outsider(\n    encounter: EncounterState,\n    member_ids: set[str] | frozenset[str],\n    origin_location_id: str,\n) -> bool:\n    return any(\n''',
    '''def has_surviving_colocated_outsider(\n    encounter: EncounterState,\n    member_ids: set[str] | frozenset[str],\n    origin_location_id: str,\n) -> bool:\n    if not encounter.active:\n        return False\n    return any(\n''',
)

# Group travel uses the runtime authority for custody + generic restrictions and centralized encounter exit.
path = "src/sao_mcp/rules/group_travel.py"
replace_once(
    path,
    '''    actors = [runtime.actors[actor_id] for actor_id in members]\n    if any(not actor.alive for actor in actors):\n''',
    '''    actors = [runtime.actors[actor_id] for actor_id in members]\n    for actor_id in members:\n        runtime.require_actor_autonomous_travel(actor_id)\n    if any(not actor.alive for actor in actors):\n''',
)
replace_once(
    path,
    '''    if encounter_id not in runtime.encounters:\n        raise KeyError(encounter_id)\n    encounter = runtime.encounters[encounter_id]\n''',
    '''    encounter = runtime.require_active_encounter(encounter_id)\n''',
)
replace_once(
    path,
    '''    for actor_id in members:\n        encounter.participants.pop(actor_id, None)\n        encounter.positions.pop(actor_id, None)\n        encounter.threat.pop(actor_id, None)\n        encounter.last_attacker_by_target.pop(actor_id, None)\n        encounter.last_attack_time_by_target.pop(actor_id, None)\n        for table in encounter.threat.values():\n            table.pop(actor_id, None)\n\n    return GroupTravelResolution(\n''',
    '''    runtime.remove_encounter_participants(\n        encounter_id, members, reason="world_graph_exit"\n    )\n\n    return GroupTravelResolution(\n''',
)

# NPC/Guild autonomous routes use the same current restriction authority.
path = "src/sao_mcp/runtime/npc_autonomy_runtime.py"
replace_once(
    path,
    '''        if materialized.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:\n            return True\n''',
    '''        if self.legal.custody_for(materialized.actor_id) is not None:\n            return True\n        if materialized.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:\n            return True\n''',
)
replace_once(path, '            require_autonomous_travel(materialized)\n', '            self.require_actor_autonomous_travel(materialized.actor_id)\n')

path = "src/sao_mcp/runtime/guild_autonomy_runtime.py"
replace_once(
    path,
    '''        for actor in self._assigned_members(agenda.guild_id, agenda.assigned_member_ids):\n            if actor.metadata.get(AUTONOMOUS_TRAVEL_RESTRICTION_KEY) is not None:\n                raise ValueError("an assigned guild member has restricted autonomous travel")\n            if actor.metadata.get("active_duel_id"):\n''',
    '''        for actor in self._assigned_members(agenda.guild_id, agenda.assigned_member_ids):\n            self.require_actor_autonomous_travel(actor.actor_id)\n            if actor.metadata.get("active_duel_id"):\n''',
)

# Persistence v3 records current encounter anchor/lifecycle and legal ledger directly.
path = "src/sao_mcp/runtime/persistence.py"
replace_once(
    path,
    'from sao_mcp.rules.spatial import default_formation\nfrom sao_mcp.rules.state_authority import assert_runtime_state_authority\n',
    'from sao_mcp.rules.live_state import assert_runtime_live_state\nfrom sao_mcp.rules.spatial import default_formation\nfrom sao_mcp.rules.state_authority import assert_runtime_state_authority\n',
)
replace_once(
    path,
    'SAVE_SCHEMA_V1 = "sao.aincrad.save.v1"\nSAVE_SCHEMA = "sao.aincrad.save.v2"\n',
    'SAVE_SCHEMA_V1 = "sao.aincrad.save.v1"\nSAVE_SCHEMA_V2 = "sao.aincrad.save.v2"\nSAVE_SCHEMA = "sao.aincrad.save.v3"\n',
)
replace_once(
    path,
    '''    if schema == SAVE_SCHEMA_V1:\n        if payload.get("encounters"):\n            raise ValueError(\n                "sao.aincrad.save.v1 encounters cannot be migrated exactly because v1 did not record encounter world-time anchors"\n            )\n        upgraded = dict(payload)\n        upgraded["schema"] = SAVE_SCHEMA\n        return upgraded\n''',
    '''    if schema in {SAVE_SCHEMA_V1, SAVE_SCHEMA_V2}:\n        if payload.get("encounters"):\n            missing = "world-time anchors" if schema == SAVE_SCHEMA_V1 else "explicit encounter lifecycle"\n            raise ValueError(\n                f"{schema} encounters cannot be migrated exactly because the schema did not record {missing}"\n            )\n        upgraded = dict(payload)\n        upgraded["schema"] = SAVE_SCHEMA\n        upgraded.setdefault("legal_state", {})\n        return upgraded\n''',
)
replace_once(path, 'def export_runtime(runtime: GameRuntime) -> str:\n    assert_runtime_state_authority(runtime)\n', 'def export_runtime(runtime: GameRuntime) -> str:\n    assert_runtime_state_authority(runtime)\n    assert_runtime_live_state(runtime)\n')
replace_once(
    path,
    '''            "zone_id": encounter.zone_id,\n            "time_ms": encounter.time_ms,\n            "safe_zone": encounter.safe_zone,\n''',
    '''            "zone_id": encounter.zone_id,\n            "world_started_at_ms": encounter.world_started_at_ms,\n            "time_ms": encounter.time_ms,\n            "safe_zone": encounter.safe_zone,\n            "ended_at_world_ms": encounter.ended_at_world_ms,\n            "end_reason": encounter.end_reason,\n''',
)
replace_once(
    path,
    '        "npc_state": runtime.npcs.dump_state(),\n        "economy_state": economy.dump_state() if economy is not None else {},\n',
    '        "npc_state": runtime.npcs.dump_state(),\n        "legal_state": runtime.legal.dump_state(),\n        "economy_state": economy.dump_state() if economy is not None else {},\n',
)
replace_once(
    path,
    '''            participants={actor_id: runtime.actors[actor_id] for actor_id in participant_ids},\n            zone_id=value["zone_id"],\n            time_ms=int(value.get("time_ms", 0)),\n            safe_zone=bool(value.get("safe_zone", False)),\n            anti_crystal=bool(value.get("anti_crystal", False)),\n''',
    '''            participants={actor_id: runtime.actors[actor_id] for actor_id in participant_ids},\n            zone_id=value["zone_id"],\n            world_started_at_ms=int(value["world_started_at_ms"]),\n            time_ms=int(value.get("time_ms", 0)),\n            safe_zone=bool(value.get("safe_zone", False)),\n            anti_crystal=bool(value.get("anti_crystal", False)),\n            ended_at_world_ms=value.get("ended_at_world_ms"),\n            end_reason=value.get("end_reason"),\n''',
)
replace_once(
    path,
    '    runtime.quests.load_state(payload.get("quest_state", {}))\n    runtime.npcs.load_state(payload.get("npc_state", {}))\n\n',
    '    runtime.quests.load_state(payload.get("quest_state", {}))\n    runtime.npcs.load_state(payload.get("npc_state", {}))\n    runtime.legal.load_state(payload.get("legal_state", {}))\n\n',
)
replace_once(
    path,
    '''    if hasattr(runtime, "relationships"):\n        from sao_mcp.runtime.community_hooks import attach_community_economy\n\n        attach_community_economy(runtime, economy)\n    return runtime\n''',
    '''    if hasattr(runtime, "relationships"):\n        from sao_mcp.runtime.community_hooks import attach_community_economy\n\n        attach_community_economy(runtime, economy)\n    assert_runtime_state_authority(runtime)\n    assert_runtime_live_state(runtime)\n    return runtime\n''',
)

# Existing clock tests now assert direct current-state anchors and explicit encounter ending.
path = "tests/test_encounter_world_clock.py"
replace_once(
    path,
    'from sao_mcp.runtime.persistence import SAVE_SCHEMA, SAVE_SCHEMA_V1, export_runtime, import_runtime\n',
    'from sao_mcp.runtime.persistence import SAVE_SCHEMA, SAVE_SCHEMA_V1, SAVE_SCHEMA_V2, export_runtime, import_runtime\n',
)
replace_once(
    path,
    '''    assert first.events[0].event_type == "encounter_started"\n    assert first.events[0].payload["world_started_at_ms"] == 0\n    assert second.events[0].payload["world_started_at_ms"] == 0\n''',
    '''    assert first.world_started_at_ms == 0\n    assert second.world_started_at_ms == 0\n    assert first.events[0].event_type == "encounter_started"\n    assert "world_started_at_ms" not in first.events[0].payload\n''',
)
replace_once(
    path,
    '''def test_historical_encounter_only_blocks_world_travel_while_outsider_is_colocated():\n    runtime = GameRuntime(seed=312)\n    player = runtime.create_character("Traveller", level=8)\n    monster = runtime.create_training_monster(level=4)\n    player.location_id = "floor_1_west_field"\n    monster.location_id = "floor_1_west_field"\n    runtime.start_encounter(\n        [player.actor_id, monster.actor_id],\n        zone_id="floor_1_west_field",\n    )\n\n    with pytest.raises(ValueError, match="ordinary travel is unavailable during a live encounter"):\n        runtime.travel_actor(player.actor_id, "floor_1_horunka")\n\n    # Encounter history remains intact, but a participant that has physically left its old scene\n    # is no longer remotely locked by a surviving actor at the former location.\n    player.location_id = "floor_1_town_of_beginnings"\n    moved = runtime.travel_actor(player.actor_id, "floor_1_west_field")\n    assert moved.to_location_id == "floor_1_west_field"\n\n    with pytest.raises(ValueError, match="ordinary travel is unavailable during a live encounter"):\n        runtime.travel_actor(player.actor_id, "floor_1_horunka")\n\n    monster.location_id = "floor_1_horunka"\n    moved = runtime.travel_actor(player.actor_id, "floor_1_horunka")\n    assert moved.to_location_id == "floor_1_horunka"\n''',
    '''def test_ended_encounter_history_no_longer_participates_in_live_travel_or_combat():\n    runtime = GameRuntime(seed=312)\n    player = runtime.create_character("Traveller", level=8)\n    monster = runtime.create_training_monster(level=4)\n    player.location_id = "floor_1_west_field"\n    monster.location_id = "floor_1_west_field"\n    encounter = runtime.start_encounter(\n        [player.actor_id, monster.actor_id],\n        zone_id="floor_1_west_field",\n    )\n\n    with pytest.raises(ValueError, match="ordinary travel is unavailable during a live encounter"):\n        runtime.travel_actor(player.actor_id, "floor_1_horunka")\n\n    ended = runtime.end_encounter(encounter.encounter_id, reason="combat_disengaged")\n    assert ended.active is False\n    assert ended.ended_at_world_ms == runtime.world.now_ms\n    assert ended.end_reason == "combat_disengaged"\n\n    moved = runtime.travel_actor(player.actor_id, "floor_1_horunka")\n    assert moved.to_location_id == "floor_1_horunka"\n    with pytest.raises(ValueError, match="has ended"):\n        runtime.advance_encounter(encounter.encounter_id, 1)\n    with pytest.raises(ValueError, match="has ended"):\n        runtime.attack(encounter.encounter_id, player.actor_id, monster.actor_id)\n''',
)
replace_once(
    path,
    '''def test_v1_save_migrates_only_when_no_unanchored_encounter_state_exists():\n''',
    '''def test_legacy_saves_migrate_only_when_no_unrepresentable_encounter_state_exists():\n''',
)
replace_once(
    path,
    '''    legacy = json.loads(export_runtime(runtime_with_encounter))\n    legacy["schema"] = SAVE_SCHEMA_V1\n    with pytest.raises(ValueError, match="cannot be migrated exactly"):\n        import_runtime(json.dumps(legacy))\n''',
    '''    legacy = json.loads(export_runtime(runtime_with_encounter))\n    legacy["schema"] = SAVE_SCHEMA_V1\n    with pytest.raises(ValueError, match="cannot be migrated exactly"):\n        import_runtime(json.dumps(legacy))\n\n    v2 = json.loads(export_runtime(HousingAincradRuntime(seed=316)))\n    v2["schema"] = SAVE_SCHEMA_V2\n    assert import_runtime(json.dumps(v2)).encounters == {}\n\n    v2_with_encounter = json.loads(export_runtime(runtime_with_encounter))\n    v2_with_encounter["schema"] = SAVE_SCHEMA_V2\n    with pytest.raises(ValueError, match="explicit encounter lifecycle"):\n        import_runtime(json.dumps(v2_with_encounter))\n''',
)

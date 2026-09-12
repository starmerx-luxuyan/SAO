# SAO — Aincrad Runtime & ChatGPT Plugin

A production-oriented Sword Art Online / Aincrad game runtime, MCP server, GM skill and ChatGPT-native UI plugin.

> Fan-made, non-commercial engineering project. It is not affiliated with or endorsed by the Sword Art Online rights holders. The repository ships code, compact rule/data records and provenance metadata; it does not ship copyrighted novel/anime/game text, ripped databases, art, audio or game assets. Canonically unspecified numbers are represented as clearly labelled simulation rules rather than invented official values.

## Release status

**v1.2.0** completes the arbitrary custom-start workflow. A single versioned Campaign Blueprint can now declare campaign-local Skills and Sword Skills, equipment and items, one or more starting characters, level/stats/Col/location, proficiencies, loadout, inventory, progression rules and declarative custom mechanics. The same blueprint can be semantically validated, previewed without mutation, then applied as one setup transaction before explicit finalization.

The runtime provides one authoritative campaign state shared by mechanics, GM observation/decision flow, persistence and UI. It supports persistent Aincrad play across combat, exploration, floor progression, inventory, economy, crafting/reinforcement, parties and raids, PvP/legal state, quests, NPC schedules and autonomy, relationships/family/housing, guild activity, population/ecology, communications, world events and save/load.

## Runtime guarantees

- **One source of truth.** Mechanical mutations happen in the runtime and are read by MCP tools, GM output and UI.
- **Deterministic campaign state.** Seeded mechanics, world time, scheduler boundaries and save/load are regression-tested for replay equivalence.
- **Observation purity.** Player/GM observation queries do not lazily repair or mutate authoritative campaign state.
- **Canon/simulation provenance.** Data records distinguish canon, inferred canon and simulation material.
- **Versioned persistence.** The current save schema is `sao.aincrad.save.v4`; v3 migrates exactly with an empty custom catalog and finalized legacy setup state, while v1/v2 migrate only where exact reconstruction is possible.
- **Separated authorities.** Ordinary play uses the GM observation/decision gate. Campaign setup is a separate one-time authority and is locked after finalization on the hosted surface.
- **Transactional blueprints.** Blueprint validation/preview execute against cloned authoritative state. Apply commits only after the complete blueprint succeeds and never finalizes setup implicitly.

## Architecture

```text
SAO/
├─ .codex-plugin/plugin.json
├─ .mcp.json
├─ Dockerfile
├─ skills/sao-gm/SKILL.md
├─ docs/
├─ src/sao_mcp/
│  ├─ corpus/                    canon/simulation records with provenance
│  ├─ domain/                    state models
│  ├─ rules/                     deterministic mechanics
│  ├─ runtime/                   authoritative state transitions and Campaign Blueprint
│  ├─ scenarios/                 installable floor/adventure services
│  ├─ ui/                        packaged MCP Apps resources
│  ├─ server_public.py           hosted ChatGPT surface
│  ├─ server_bootstrap.py        full internal/development surface
│  └─ cli.py
└─ tests/
```

`server_bootstrap.py` is the complete composition root. `server_public.py` reuses the same authoritative runtime but exposes only the hosted player/GM/setup surface.

## Hosted plugin endpoint

```text
https://sao-aincrad-mcp-production.up.railway.app/mcp
```

The hosted runtime is currently a **single private campaign process**, not a public multi-tenant service.

## Custom-start workflow

For a new custom campaign, the preferred flow is:

```text
get_campaign_setup_status
→ begin_campaign_setup
→ validate_campaign_blueprint
→ preview_campaign_blueprint
→ apply_campaign_blueprint
→ finalize_campaign_setup
```

The blueprint schema is:

```text
sao.aincrad.campaign-blueprint.v1
```

A blueprint may contain:

- custom weapons, armor/shields, consumables and ordinary items;
- custom Skills and Sword Skills, including `proficiency_skill_id`;
- one or more characters with stable blueprint-local keys;
- level, XP, STR/AGI, HP, Col, location and profile;
- proficiencies, equipped skills and unlocked Extra/Unique Skills;
- exact starting inventory, equipment, durability, reinforcement attempts and enhancement tracks;
- legacy `progression_rules` where exact v1.1 compatibility is needed;
- declarative `custom_mechanics` for level growth, proficiency routing/gain, reinforcement caps, normal-attack curves and threshold unlocks.

`preview_campaign_blueprint` never commits provisional actor/item IDs. `apply_campaign_blueprint` returns committed state and leaves setup open so the caller can inspect it before `finalize_campaign_setup`.

Individual setup tools remain available for iterative editing and debugging.

## Hosted public MCP surface

The hosted public surface includes health/state/catalog access, the setup lifecycle, individual custom-definition/setup tools, Campaign Blueprint validate/preview/apply, save export/import, the GM observation/decision gate, and the Aincrad HUD/System Menu/Boss Raid UI resources.

Direct floor-boss completion flags, raw world advancement, NPC/guild administration, population/ecology controls and setup reopening remain outside the hosted public surface. Only the full internal surface exposes `reopen_campaign_setup`.

## Persistence

The authoritative save schema is:

```text
sao.aincrad.save.v4
```

`export_save_json` serializes the deterministic campaign state, including actors, encounters, world/RNG state, custom catalog, setup lifecycle, quests/NPC/legal state, economy, timeline, relationships/family, communications, knowledge, autonomy/schedulers, guilds, housing, population/ecology and world/canonical-event state.

Campaign Blueprint does not add another persistence layer: once applied, its catalog definitions, actor metadata, mechanics and item instances are ordinary v4 authoritative state.

## Local development and self-hosting

Requires **Python 3.12+**.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
```

The package entry point is `sao-mcp = sao_mcp.cli:main`. Local stdio defaults to the `full` surface; Streamable HTTP defaults to `public`. `SAO_MCP_SURFACE` may be set explicitly to `public` or `full`.

## Release validation

Normal CI performs development install, compile, full pytest, exact hosted-public-tool and UI-resource checks, wheel build, clean-environment wheel installation/smoke, and plugin-bundle assembly.

See `AGENTS.md`, `docs/SETUP_API.md`, `docs/MECHANICS.md`, `docs/UI.md` and `docs/RELEASE.md` for maintained contracts.

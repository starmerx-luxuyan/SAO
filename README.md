# SAO — Aincrad Runtime & ChatGPT Plugin

A production-oriented Sword Art Online / Aincrad game runtime, MCP server, GM skill and ChatGPT-native UI plugin.

> Fan-made, non-commercial engineering project. It is not affiliated with or endorsed by the Sword Art Online rights holders. The repository ships code, compact rule/data records and provenance metadata; it does not ship copyrighted novel/anime/game text, ripped databases, art, audio or game assets. Canonically unspecified numbers are represented as clearly labelled simulation rules rather than invented official values.

## Release status

**v1.1.0** extends the release-ready Aincrad runtime with authoritative campaign setup, persistent custom Skills/Sword Skills, and a player-grounded field-encounter entry path.

The runtime provides one authoritative campaign state shared by mechanics, GM observation/decision flow and UI. It supports persistent Aincrad play across combat, exploration, floor progression, inventory, economy, crafting/reinforcement, parties and raids, PvP/legal state, quests, NPC schedules and autonomy, relationships/family/housing, guild activity, population/ecology, communications, world events and save/load.

The world model contains all 100 floors. Canon-backed and authored scenario coverage is intentionally denser on floors for which this repository has explicit corpus/scenario material; unsupported canon details are not fabricated as official facts.

## Runtime guarantees

- **One source of truth.** Mechanical mutations happen in the runtime and are read by MCP tools, GM output and UI rather than being re-invented by narration.
- **Deterministic campaign state.** Seeded mechanics, world time, scheduler boundaries and save/load are regression-tested for replay equivalence.
- **Observation purity.** Player/GM observation queries do not lazily repair or mutate authoritative campaign state.
- **Canon/simulation provenance.** Data records distinguish canon, inferred canon and simulation material.
- **Versioned persistence.** The current save schema is `sao.aincrad.save.v4`; v3 saves migrate exactly with an empty custom-catalog registry, while v1/v2 payloads are migrated only where exact migration is possible.
- **Separated MCP surfaces.** Ordinary play still passes through the observation/decision gate. Explicit setup tools are a separate authority for character initialization, setup inventory, campaign-local custom Skills and Sword Skills.

## Architecture

```text
SAO/
├─ .codex-plugin/plugin.json     plugin metadata
├─ .mcp.json                     hosted Streamable HTTP MCP configuration
├─ Dockerfile                    reproducible hosted MCP deployment
├─ skills/sao-gm/SKILL.md        host-model GM workflow and state discipline
├─ docs/                         mechanics, UI and release contracts
├─ src/sao_mcp/
│  ├─ corpus/                    compact canon/simulation data with provenance
│  ├─ domain/                    dataclasses/enums/state models
│  ├─ rules/                     deterministic rule functions
│  ├─ runtime/                   authoritative campaign/state transitions
│  ├─ scenarios/                 installable floor/adventure scenario services
│  ├─ ui/                        packaged HTML resources, CSP/domain metadata and view models
│  ├─ server_public.py           narrow hosted ChatGPT surface
│  ├─ server_bootstrap.py        complete internal/development surface
│  └─ cli.py                     surface + stdio / Streamable HTTP selection
└─ tests/                        mechanics, authority, persistence and campaign stress regressions
```

`server_bootstrap.py` remains the complete composition root: it creates the single authoritative Aincrad runtime and installs every scenario/runtime service. `server_public.py` reuses that same runtime but publishes only the tools appropriate for ordinary ChatGPT play.

## Hosted plugin endpoint

The bundled plugin MCP configuration points directly at the hosted Streamable HTTP server:

```text
https://sao-aincrad-mcp-production.up.railway.app/mcp
```

Streamable HTTP defaults to the `public` surface. It does not advertise direct floor-boss completion flags, raw world advancement, NPC/guild administration, population/ecology controls or other maintenance tools. Ordinary in-world mutations must pass through the fresh-observation GM Decision Gate.

The hosted runtime is currently a **single private campaign process**, not a public multi-tenant game service. Authentication and per-user/per-campaign isolation are separate deployment work and are required before opening this endpoint to unrelated users.

## Hosted public MCP surface

The hosted server intentionally exposes a bounded player/GM surface. v1.1 setup is the foundation for arbitrary custom starts: definitions become normal catalog/runtime state rather than narration-only exceptions. Campaign setup is a one-time `begin -> configure -> finalize` phase; after finalization, public setup mutations are locked and only the full internal surface can explicitly reopen them.

The hosted server exposes these capability groups:

- health and character creation/state
- explicit campaign setup lifecycle plus configured character creation, character patching, setup inventory, and authoritative setup-state inspection
- persistent campaign-local custom weapons, armor/shields, consumables, ordinary items, Skills and Sword Skills
- declarative custom mechanics for level growth, proficiency routing/gain, reinforcement caps, normal-attack curves and threshold unlocks
- catalog listing and provenance-aware entry inspection, including armor and generic item categories
- `get_gm_observation`
- `get_gm_decision_contract`
- `preview_gm_decision`
- `execute_gm_decision`, including grounded `engage_monster` actions from current field encounter options
- explicit save export/import
- Aincrad HUD, System Menu and Boss Raid UI tools

The three UI resources declare explicit MCP Apps CSP metadata and a dedicated widget domain. Their HTML is self-contained, so the CSP grants no external network, static-resource, nested-frame or base-URI domains.

## Full internal surface

The full surface still contains the detailed combat, inventory, economy, spatial, timeline, duel, relationship, housing, population, ecology, autonomy, floor-scenario and boss administration tools used by development and maintenance. It is intentionally not the default hosted ChatGPT surface.

Local stdio defaults to `full`. You can select the surface explicitly with:

```text
SAO_MCP_SURFACE=public
SAO_MCP_SURFACE=full
```

## Plugin bundle

The CI release job assembles `SAO-Aincrad-v1.0.0-plugin` with:

- `.codex-plugin/plugin.json`
- `.mcp.json` pointing to the hosted MCP endpoint
- `skills/sao-gm/SKILL.md`
- the v1.0.0 Python wheel for self-hosting
- release/source-policy/license/privacy/terms documentation

## Local development and self-hosting

Requires **Python 3.12+**.

For development:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

python -m pip install -e ".[dev]"
pytest -q
```

For a normal local install from a checkout:

```bash
python -m pip install .
sao-mcp
```

The package entry point is `sao-mcp = sao_mcp.cli:main`.

## Transport

`stdio` is the default local transport and defaults to the full development surface:

```bash
sao-mcp
```

For self-hosted Streamable HTTP, the public surface is the default:

```bash
# macOS/Linux
SAO_MCP_TRANSPORT=streamable-http SAO_MCP_HOST=127.0.0.1 SAO_MCP_PORT=8000 sao-mcp
```

PowerShell:

```powershell
$env:SAO_MCP_TRANSPORT = "streamable-http"
$env:SAO_MCP_HOST = "127.0.0.1"
$env:SAO_MCP_PORT = "8000"
sao-mcp
```

`SAO_MCP_TRANSPORT` accepts only `stdio` or `streamable-http`; `SAO_MCP_SURFACE` accepts only `public` or `full`.

## Persistence

The current authoritative save schema is:

```text
sao.aincrad.save.v3
```

`export_save_json` serializes the deterministic runtime state, including actors, encounters, RNG state, world time, quest/NPC/legal state, economy, timeline, relationships/family, communications, knowledge, autonomy/schedulers, guilds, housing, population, monster/quest ecology, social communications and world-event/canonical-timeline state.

`import_save_json` accepts the current schema and supported legacy payloads. Legacy encounter saves that omitted information required for exact reconstruction are rejected rather than guessed or silently repaired.

## Release validation

The normal CI path performs:

1. editable development install;
2. Python compile pass;
3. full pytest suite, including campaign stress and release-contract invariants;
4. exact hosted-public-tool-surface and UI CSP/domain checks;
5. real wheel build;
6. installation of that wheel into a clean virtual environment;
7. smoke import of both the public and full surfaces plus packaged UI resources;
8. assembly of the installable plugin bundle including hidden manifest/config files.

This is intentionally aimed at release failures that ordinary source-tree unit tests do not catch.

## Development contract

The project follows `AGENTS.md`: implement real game capability first, keep MCP/UI adapters thin, preserve provenance, avoid fake canon precision, and use tests for concrete mechanics and invariants rather than defensive scaffolding.

See `ROADMAP.md`, `docs/MECHANICS.md`, `docs/UI.md` and `docs/RELEASE.md` for the maintained project contracts.

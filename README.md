# SAO — Aincrad Runtime & ChatGPT Plugin

A production-oriented Sword Art Online / Aincrad game runtime, MCP server, GM skill and ChatGPT-native UI plugin.

> Fan-made, non-commercial engineering project. It is not affiliated with or endorsed by the Sword Art Online rights holders. The repository ships code, compact rule/data records and provenance metadata; it does not ship copyrighted novel/anime/game text, ripped databases, art, audio or game assets. Canonically unspecified numbers are represented as clearly labelled simulation rules rather than invented official values.

## Release status

**v1.0.0** is the first release-ready Aincrad runtime baseline.

The runtime provides one authoritative campaign state shared by mechanics, MCP tools, GM observation/decision flow and UI. It supports persistent Aincrad play across combat, exploration, floor progression, inventory, economy, crafting/reinforcement, parties and raids, PvP/legal state, quests, NPC schedules and autonomy, relationships/family/housing, guild activity, population/ecology, communications, world events and save/load.

The world model contains all 100 floors. Canon-backed and authored scenario coverage is intentionally denser on floors for which this repository has explicit corpus/scenario material; unsupported canon details are not fabricated as official facts.

## Runtime guarantees

- **One source of truth.** Mechanical mutations happen in the runtime and are read by MCP tools, GM output and UI rather than being re-invented by narration.
- **Deterministic campaign state.** Seeded mechanics, world time, scheduler boundaries and save/load are regression-tested for replay equivalence.
- **Observation purity.** Player/GM observation queries do not lazily repair or mutate authoritative campaign state.
- **Canon/simulation provenance.** Data records distinguish canon, inferred canon and simulation material.
- **Versioned persistence.** The current save schema is `sao.aincrad.save.v3`; legacy v1/v2 payloads are migrated only where exact migration is possible.
- **Thin MCP surface.** Tool adapters expose normal Python rules/runtime behavior instead of containing a second rules engine.

## Architecture

```text
SAO/
├─ .codex-plugin/plugin.json     plugin metadata
├─ .mcp.json                     local MCP command configuration
├─ skills/sao-gm/SKILL.md        host-model GM workflow and state discipline
├─ docs/                         mechanics, UI and release contracts
├─ src/sao_mcp/
│  ├─ corpus/                    compact canon/simulation data with provenance
│  ├─ domain/                    dataclasses/enums/state models
│  ├─ rules/                     deterministic rule functions
│  ├─ runtime/                   authoritative campaign/state transitions
│  ├─ scenarios/                 installable floor/adventure scenario services
│  ├─ ui/                        packaged HTML resources and view models
│  ├─ server*.py                 thin MCP tool-registration modules
│  ├─ server_bootstrap.py        full production MCP/runtime composition
│  └─ cli.py                     stdio / Streamable HTTP entry point
└─ tests/                        mechanics, authority, persistence and campaign stress regressions
```

`server_bootstrap.py` is the production composition root. It creates the single authoritative Aincrad runtime, installs scenario services and registers the complete public MCP tool families onto one `MCPServer`.

## Public MCP surface

The full server exposes tools in these stable capability families:

- health, character creation/state and catalog inspection
- combat, Sword Skills, Switch, parties and raids
- inventory, equipment, loot, crafting, repair and reinforcement
- world locations, travel, teleportation, floor gates and world time
- monsters, bosses, spatial combat and ecology
- quests, NPC interaction, NPC schedules/autonomy and knowledge boundaries
- economy, property, housing, relationships, family and communications
- PvP/duels, legal state and social/guild autonomy
- population, quest ecology, world events and canonical timeline profiles
- GM observation -> decision -> execution tools
- complete runtime save export/import
- packaged Aincrad HUD, system-menu and boss/raid UI resources

The release contract tests assert a critical subset of these tools through the SDK's public `MCPServer.list_tools()` API so accidental bootstrap omissions fail CI.

## Installation

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

The package entry point is `sao-mcp = sao_mcp.cli:main`. The bundled `.mcp.json` uses that command directly.

## Transport

`stdio` is the default transport:

```bash
sao-mcp
```

For Streamable HTTP:

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

`SAO_MCP_TRANSPORT` accepts only `stdio` or `streamable-http`.

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
4. real wheel build;
5. installation of that wheel into a clean virtual environment;
6. smoke import of the packaged production bootstrap and packaged UI resources.

This is intentionally aimed at release failures that ordinary source-tree unit tests do not catch.

## Development contract

The project follows `AGENTS.md`: implement real game capability first, keep MCP/UI adapters thin, preserve provenance, avoid fake canon precision, and use tests for concrete mechanics and invariants rather than defensive scaffolding.

See `ROADMAP.md`, `docs/MECHANICS.md`, `docs/UI.md` and `docs/RELEASE.md` for the maintained project contracts.

# SAO — Aincrad Runtime & ChatGPT Plugin

A production-oriented Sword Art Online / Aincrad rules runtime, corpus, GM skill, MCP server, and ChatGPT-native UI plugin.

> Fan-made, non-commercial engineering project. This repository does **not** ship copyrighted novel/anime/game text, art, audio, or ripped assets. Canon facts are represented as compact rule/data records with source provenance; where canon leaves numbers unspecified, the runtime uses clearly-labelled simulation rules.

## Goal

Build a system that can actually **run Aincrad as a game**, not merely answer lore questions.

The finished system is expected to support:

- 100-floor world progression and floor unlock state
- settlements, field zones, dungeons, labyrinths, safe areas and anti-crystal areas
- players, NPCs, monsters, elites, field bosses and floor bosses
- level progression, attributes, skill slots and 0–1000 skill proficiency
- weapon skills, Sword Skills, Extra Skills and gated Unique Skills
- normal attacks, guarding, parrying, evasion, movement, aggro, threat, Switch and raid tactics
- Sword Skill pre-motion, commit, hit windows and post-motion rigidity
- HP, healing-over-time, instant crystal healing, potion cooldowns and status effects
- weapon/armour durability, breakage, repairs, appraisal and enhancement
- five canonical enhancement dimensions: sharpness/toughness, quickness, accuracy, heaviness and durability
- blacksmith production, material quality, recipes, salvage and enhancement attempts
- inventory, weight limits, stacks, Col, shops, trading, loot ownership and drops
- crime cursor/alignment, PvP, duels, safe-zone protection and orange-player restrictions
- parties (up to six), raid groups (up to eight parties), guilds and shared combat state
- quests, NPC relationships, event flags, time progression and respawn schedules
- save/load world state with deterministic seeds and audit-friendly combat logs
- ChatGPT-native rich UI: HUD, character sheet, inventory, skill panel, combat panel, boss panel and floor panel
- GM skill instructions that keep model narration subordinate to mechanical state

## Architecture

```text
SAO/
├─ .codex-plugin/          ChatGPT/Codex plugin manifest
├─ skills/                 host-model GM workflow and rules discipline
├─ docs/                   design, source policy, mechanics specs
├─ src/sao_mcp/
│  ├─ domain/              dataclasses/enums/state models
│  ├─ rules/               pure deterministic rules
│  ├─ runtime/             encounter/world/state transitions
│  ├─ corpus/              compact factual rules/catalog records
│  ├─ ui/                  structured UI view-models
│  └─ server.py            thin MCP tool layer
├─ web/                    React MCP App component(s)
└─ tests/                  high-value regression tests
```

### Design contract

1. **Rules first.** MCP tools stay thin; mechanics live in normal Python modules.
2. **One source of truth.** UI and GM narration read the same authoritative state transitions.
3. **Canon vs simulation is explicit.** Every important data/rule record may carry provenance such as `canon`, `canon_inferred`, `simulation`, and source references.
4. **No fake precision.** Canonically unspecified numbers are tuned simulation parameters, not presented as official values.
5. **Deterministic when needed.** Random mechanics accept explicit seeds/RNG streams so encounters can be replayed and tested.
6. **Detailed without defensive overengineering.** pytest covers high-value mechanics and invariants; abstractions exist only when game functionality needs them.

## Initial mechanical core

The first implementation establishes:

- combatants, weapons, armour, status effects and encounters
- physical hit resolution with accuracy/evasion, guard, parry and criticals
- Sword Skill timing and post-motion vulnerability
- threat/aggro and player-devised Switch windows
- durability loss and breakage
- potion/crystal consumption rules
- skill proficiency and slot progression
- weapon enhancement attempts and five enhancement tracks
- item/catalog schemas with provenance
- MCP read/simulate tools and ChatGPT UI view-models

Later releases expand corpus coverage and full world/adventure runtime without replacing the core contracts.

## Development

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -e .[dev]
pytest
sao-mcp
```

The React component is built separately from `web/` and is served as an MCP App UI resource by the server once the web bundle is present.

## Status

Active development. See `ROADMAP.md` and `docs/MECHANICS.md`.

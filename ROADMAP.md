# SAO Aincrad Runtime roadmap

The project target is a playable Aincrad runtime rather than a lore-search demo. **v1.0.0 completes the original R0-R10 release plan.** Further work may expand corpus/scenario density or add adapters, but the v1 runtime contracts below are the maintained baseline.

A phase is considered complete only when its rules execute through normal Python code, are exposed through thin MCP tools where appropriate, share the authoritative runtime state, and are covered by high-value regressions.

## v1.0.0 baseline — complete

### R0 — Foundation and source discipline ✅

- package layout, development contract and provenance model
- MCP Python SDK v2 server and MCP Apps UI binding
- plugin manifest, bundled GM skill and local MCP configuration
- deterministic RNG and serializable state contracts

### R1 — Character / skill / equipment core ✅

- level, HP, STR, AGI and carry capacity
- canonical skill-slot curve and 0–1000 proficiency
- skill/equipment legality and prerequisite handling
- weapons, armour/shields, requirements, weight and durability
- inventory stacks, equipment slots, Col and ownership
- compact canon seeds plus explicitly labelled simulation data

### R2 — Combat runtime ✅

- targeting, spatial range, movement and encounter/world clocks
- normal attacks, guard, parry, evade, critical/weak-point resolution
- Sword Skill timing and post-motion rigidity
- multi-hit/interruption/stagger/knockback/clash behavior where represented
- threat/aggro, monster targeting, Switch and raid combat state
- healing, cooldowns, crystals, statuses, anti-crystal/silence constraints
- defeat/death, loot ownership and combat audit state

### R3 — Production / economy ✅

- crafting, materials, recipes, quality and provenance
- enhancement/reinforcement and the five Aincrad enhancement dimensions
- repair, durability, salvage and inventory integration
- shops/trade/economy loops and property-facing economy state
- life-skill/crafting hooks used by the campaign runtime

### R4 — Social / PvP / organization ✅

- legal/cursor state, crime and hostile-action constraints
- safe areas, duels and PvP resolution
- parties up to six and raids up to eight parties
- guild state/autonomy and shared operations
- relationships, family/shared property hooks and social communications

### R5 — Aincrad world runtime ✅

- 100-floor world state and unlock progression
- towns/fields/dungeons/boss-space location model
- monster ecology and respawn/lifecycle state
- teleport gates, travel time, discoveries and map knowledge
- floor-boss defeat, delayed gate activation and scheduler-boundary correctness
- persistent time, scheduled events and deterministic world ticks

### R6 — Quest / NPC / adventure runtime ✅

- quest definitions, prerequisites, branching/progress/rewards/failure state
- NPC schedules, knowledge boundaries, goals and relationships
- procedural/simulation content kept distinct from canon-backed facts
- canonical timeline/event profiles
- GM observation -> decision -> execution flow grounded in player-visible state

### R7 — Corpus expansion ✅ for v1 baseline

The repository contains the compact item/weapon/skill/monster/world/boss/quest corpus and authored scenario material required by the v1 campaign surface. Corpus density remains intentionally extensible: future canon-backed records can be added without changing the runtime architecture.

Unknown canonical numeric fields remain absent or use separately labelled simulation profiles; they are not promoted to invented official values.

### R8 — ChatGPT-native UI ✅

- packaged character/HUD view
- system-menu UI
- boss/raid UI
- shared authoritative view models
- MCP Apps resources distributed inside the Python wheel

### R9 — Persistence / campaign tooling ✅

- versioned save format (`sao.aincrad.save.v3`)
- exact migration/rejection rules for older payloads
- deterministic save/load and checkpoint equivalence
- GM observation filtering and authority checks
- campaign stress coverage across combat, NPC, guild, population, ecology, quest and communication state

### R10 — Release hardening ✅

- full regression suite and deterministic replay/state-equivalence checks
- campaign-scale stress tests
- observation-purity regressions
- plugin/package metadata and deployment documentation
- stdio and Streamable HTTP launch profiles
- wheel build + clean-environment installation smoke test
- release-contract checks for version, persistence schema, packaged UI and critical MCP tools

## Definition of “done”

The v1 baseline is complete when a host model can create and run a persistent Aincrad campaign while treating the runtime—not narration—as mechanical authority: characters can explore the world model, fight normal enemies and bosses, obtain/craft/enhance/equip items, use parties/raids, interact with quests/NPCs/economy/social systems, advance an autonomous world, persist and restore campaign state, and render high-frequency state through the bundled plugin UI.

That baseline is now the maintenance contract for v1. Future development should add real gameplay/corpus capability without reintroducing parallel state authorities, model-invented mechanics or defensive fallback layers.

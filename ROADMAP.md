# SAO Aincrad Runtime roadmap

The target is a complete, playable Aincrad runtime rather than a lore search demo. Releases are vertical slices; a phase is not considered complete until its rules are executable through normal Python code, exposed through thin MCP tools, visible through the UI where appropriate, and covered by high-value regressions.

## R0 — Foundation and source discipline

- package layout, development contract, provenance model
- current MCP Python SDK v2 server and MCP Apps UI binding
- plugin manifest, bundled skill, local MCP configuration
- deterministic RNG and serializable state contracts

## R1 — Character / skill / equipment core

- level, HP, STR, AGI, carry capacity
- canonical skill-slot curve and 0–1000 proficiency
- skill equip/remove/mastery and prerequisite graph
- weapon families, armour/shields, requirements, weight, durability
- inventory stacks, equipment slots, Col and ownership
- compact canon item/skill seeds plus simulation templates

## R2 — Combat runtime

- targeting, range, movement and encounter clock
- normal attacks, guard, parry, evade, weak-point/critical resolution
- Sword Skill pre-motion -> commit -> hit windows -> post-motion rigidity
- single/multi-hit skills, interruption, stagger, knockback and weapon clash
- threat/aggro, monster target selection, AI reaction delay and Switch
- healing, potion cooldown, crystals, statuses, anti-crystal areas and silence
- defeat/death, drops, loot ownership and combat audit log

## R3 — Production/economy

- blacksmith crafting, materials, recipes, quality and maker provenance
- enhancement attempts and five enhancement tracks
- appraisal, repair, durability breakage and salvage/ingot conversion
- shops, buy/sell spread, player trade, auction-like listings, inn/food services
- gathering, fishing, cooking, sewing/leather/metal life skills

## R4 — Social / PvP / organization

- cursor/alignment and criminal acts
- safe areas, duels, hostile actions, orange-player access constraints
- parties up to six, raid groups up to eight parties
- guilds, guild treasury/permissions, shared markers and raid roles
- friends, marriage/shared storage hooks, NPC relationship state

## R5 — Aincrad world runtime

- 100-floor graph and unlock progression
- towns, fields, dungeons, labyrinth towers, boss rooms, anti-crystal zones
- spawn tables, respawn schedules, elite/field-boss/floor-boss lifecycle
- teleport gates, travel time, discoveries, map knowledge and fog of war
- floor-boss defeat, next-floor activation delay and early physical activation
- persistent time, scheduled events and deterministic world ticks

## R6 — Quest / NPC / adventure runtime

- quest definitions, prerequisites, branching flags, rewards and failures
- NPC schedules, knowledge boundaries, goals and relationship state
- procedural non-canon side quests marked as simulation content
- event flags and canon-event profiles that can be enabled/disabled
- GM turn executor: intent -> mechanical actions -> world tick -> observable result

## R7 — Corpus expansion

- weapon and armour catalog
- named items and consumables
- Sword Skills, weapon skills, support/life skills, Extra Skills and Unique Skills
- monsters, bosses, materials and recipes
- known floors/settlements/dungeons/quests/NPCs
- provenance audit and duplicate/alias resolution

The corpus target is **high granular coverage**, not a tiny handpicked list. Unknown canonical numeric fields remain null or receive separately-labelled simulation profiles rather than invented 'official' values.

## R8 — ChatGPT-native UI

- compact inline status card
- immersive fullscreen system menu
- character/equipment/inventory/skills
- combat HUD, target frame, party/raid frames, buffs/debuffs and Sword Skill state
- boss multi-bar display and raid status
- floor/map/quest panels
- production/enhancement dialogs with before/after probabilities and consumed attempts
- UI event -> MCP tool -> authoritative runtime -> refreshed view model loop

## R9 — Persistence / campaign tooling

- versioned save format and migrations
- campaign slots, checkpoints and replayable encounter seeds
- GM-visible audit stream and player-knowledge filtering
- import/export of compact campaign state without copyrighted corpus payloads

## R10 — Release hardening

- full rule-flow regression suite, fuzzing only where it finds game bugs
- deterministic replay tests
- performance on large raids / monster groups
- plugin metadata, privacy/terms placeholders, deployment docs
- remote Streamable HTTP deployment profile

## Definition of “done”

A complete v1 is reached when a host model can start a fresh Aincrad campaign, create a player, explore floors, fight normal enemies and bosses, obtain/craft/enhance/equip items, use parties/raids, interact with quests/NPCs/economy, persist state, and render all high-frequency states through the plugin UI without the model inventing mechanical results outside the runtime.

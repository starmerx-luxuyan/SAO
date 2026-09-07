# SAO UI system

The UI should feel like a clean, floating VRMMO system interface while remaining original, readable and appropriate for ChatGPT plugin surfaces.

## Visual language

- translucent glass-like panels, restrained borders and soft depth
- high information density without dashboard clutter
- HP is always the strongest combat signal
- statuses use icon + label/tooltip rather than relying on color alone
- equipment rarity and warning states never depend on hue alone
- compact inline cards for immediate state; fullscreen for immersive inventory/skill/map/combat management
- no decorative navigation that competes with the chat itself

## Core views

### Inline status

Shows character name/level, HP, location/floor, equipped weapon, current target if fighting, and at most two high-value actions.

### Character / equipment

Paper-doll style equipment slots, STR/AGI/derived values, level/XP, current weight/capacity, cursor state and skill-slot usage.

### Inventory

Filter by weapon/armour/material/consumable/quest item; display stack count, weight, durability, enhancement shorthand and provenance-safe description. Actions are contextual: equip, use, inspect, trade, discard where allowed.

### Skills

Slot capacity, equipped skills, 0–1000 proficiency bars, prerequisites and Sword Skill technique list. Unique/Extra Skills remain hidden until the viewer has legitimately discovered them.

### Combat HUD

Player HP and state, target HP where observable, weapon durability warning, Sword Skill phase/recovery, potion cooldown, statuses, party frames, threat cues that a player could plausibly infer, and a concise event strip.

### Boss / raid

Boss bars/phases that have been observed, up to eight party groups, deaths/critical HP, role markers and raid callouts. Hidden boss scripting stays server-side.

### Craft / enhance

Input weapon, remaining enhancement attempts, five enhancement tracks, materials, smith proficiency, success probability as a simulation estimate, and a clear warning for destructive over-cap attempts.

### Floor / map

Current floor, known town/field/dungeon nodes, discovered teleport gate, known labyrinth progress and party markers only where allowed by game state.

## Data contract

UI components consume view models produced in `sao_mcp.ui`. They never calculate authoritative damage, healing, enhancement success, inventory costs, skill unlocks or world transitions in JavaScript. UI actions call MCP tools; the server mutates state; the component renders the returned snapshot.

---
name: sao-aincrad-gm
description: Run a persistent Sword Art Online Aincrad campaign using the SAO MCP runtime as the mechanical source of truth.
---

# SAO Aincrad GM

Use this skill when the user wants to play, simulate, inspect, build, or adjudicate an Aincrad campaign.

## Authority order

1. Current campaign/runtime state returned by the SAO MCP.
2. Canon-backed corpus facts with provenance.
3. Explicit simulation rules returned by the runtime.
4. Free narration only for details that do not mutate authoritative game state.

Never invent a mechanical outcome because it sounds dramatic. If HP, durability, inventory, proficiency, Col, cooldown, status, crime state, encounter timing, quest/world flags or loot can change, call the relevant runtime tool first.

## Turn loop

For an in-world player action:

1. Recover the current player/world/encounter snapshot when needed.
2. Translate natural-language intent into the smallest relevant runtime action(s).
3. Execute the mechanical transition.
4. Advance encounter/world time when the action consumes time.
5. Read the returned observable events and updated snapshot.
6. Narrate naturally from the player's knowledge and senses.
7. Prefer the UI-bound snapshot tool when a HUD/panel materially improves readability.

Do not turn gameplay into a menu unless the user asks for options. NPCs and monsters act from their own state, goals, AI profile and information; they are not extensions of the user's plan.

## GM observation and decision gate

For ordinary in-world play, start from `get_gm_observation` for the explicit player viewpoint. The observation packet is the narration/decision boundary: it contains that player's current UI state, beliefs, visible entities, encounters, messages and currently usable capability references, but not NPC actor-core plans, guild strategy internals, world-event occurrences, canonical expectation overlays or another entity's private knowledge.

Translate the user's prose into one ordinary player action, then use `execute_gm_decision`. The GM Decision Runtime receives only the fresh observation packet and rejects action references that are not grounded in that packet. Use `preview_gm_decision` when you need to validate the plan without mutation and `get_gm_decision_contract` for the exact allowed action shapes.

Do not call the internal `GMTurnExecutor` as a narration shortcut. It remains a mechanical dispatcher under the decision gate. NPC/guild administrative goal controls, direct knowledge injection and raw world advancement are deliberately absent from the player-observable decision surface; NPCs, guilds, events, population, economy and ecology continue through their own autonomous runtimes.

Each decision is bound to the observation digest that justified it and may authorize at most one ordinary player action. Re-observe before deciding the next action, because location, identity, inventory, encounter membership and other visibility may have changed. World-only waiting is represented by a positive `world_tick_ms` with no proposed player action.

## Combat

Respect action commitment. Sword Skills have pre-motion, active execution and post-motion rigidity. Do not let a character freely cancel a committed action unless a runtime mechanic explicitly allows it. `Switch` is a player-devised coordination tactic: describe the actual opening, movement and AI reaction rather than calling it a magical system button.

Use party/raid membership, range, target legality, safe-zone/anti-crystal rules, potion cooldowns, statuses, durability and death state as returned. A model-written flourish never overrides a failed hit or creates an unearned critical/drop.

## Equipment and items

When comparing equipment, distinguish raw attack, requirements, weight, durability, enhancement tracks, bonuses and the character's current STR/AGI/proficiency. Consuming/equipping/trading/enhancing items requires runtime mutation. Never duplicate an item in prose after the runtime consumed or transferred it.

## Canon discipline

When the user asks whether a number/rule is 'official', surface its provenance. `simulation` is valid game logic but must be described as this plugin's calibration rather than canon. Do not import mechanics from separate SAO games into default Aincrad unless an explicit variant/profile enables them.

## Information discipline

Do not reveal hidden drop rates, boss scripts, undiscovered Unique Skills, NPC private state, unseen map nodes or other server-only knowledge during ordinary play. Use player-visible view models.

## UI

Use compact HUD output during ordinary chat. Use richer/fullscreen panels for inventory, skills, equipment, crafting/enhancement, map and raids. UI buttons call the MCP; JavaScript is presentation, not rules authority.

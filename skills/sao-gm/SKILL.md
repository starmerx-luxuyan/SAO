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

## Structured GM turn executor

For tightly coupled ordinary mechanics, prefer `execute_gm_turn` over manually stitching many MCP calls when one player intent clearly maps to a known sequence. The executor does not understand prose and does not decide what the player meant. Translate the user's intent first, then submit exact structured actions.

Use `get_gm_turn_action_contract` when the exact action shape is needed. The v1 executor covers ordinary travel/teleport, encounter movement, timeline attacks and timeline processing, Switch, inventory item use, equip/unequip, NPC interaction, quest accept/claim, and explicit world/encounter time advancement. Floor/campaign-specific story actions remain scenario tools and must not be smuggled through the generic executor.

The executor validates the complete action-plan shape before performing the first mutation. Once mechanical execution begins, each step is authoritative and is not transactionally rolled back if a later game action is illegal. Keep batches small and only combine actions that are already decided; never put conditional alternatives, speculative retries, or a player/NPC choice into one batch. A failed hit, blocked route or invalid action is the result, not an invitation to substitute a fallback action.

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

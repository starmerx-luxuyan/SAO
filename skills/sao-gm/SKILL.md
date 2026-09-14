---
name: sao-aincrad-gm
description: Run a persistent Sword Art Online Aincrad campaign using the SAO MCP runtime as the mechanical source of truth.
---

# SAO Aincrad GM

Use the runtime as the authority for every state-changing part of Aincrad play.

## Ordinary play: one runtime line

Ordinary play has exactly one public mutation entry: `turn_execute`.

The model translates the player's intent into one or more semantic actions and submits them together. It does **not** decide the runtime sequence. For every action the server itself always performs, in order:

`fresh observation → player projection → GATE → execute → settle to the next decision boundary → fresh observation → System Menu projection`

Compound requests repeat the exact same micro-line for each action. The second action can never reuse the first action's pre-state.

The model must not call or emulate `get_gm_observation → preview_gm_decision → execute_gm_decision`, must not choose `world_tick_ms`, and must not issue `advance_encounter` or `process_timeline`. Those are internal engine responsibilities.

If the user says “sell these materials, reinforce the sword, then buy food”, submit the intended semantic actions through `turn_execute`; never narrate any Col, inventory, durability, enhancement, proficiency, cooldown, quest or encounter change that is absent from the returned receipt/System Menu.

## UI

The hosted player surface exposes one visual UI: `system_menu`.

Do not invoke or refer players to separate Character HUD or Boss Raid HUD surfaces. Combat/raid state belongs in the System Menu projection so there is one visible source of truth and one refresh target after mutations.

## Campaign setup

Campaign setup remains a separate explicit authority. Prefer Campaign Blueprint for a coherent custom start, then finalize setup before ordinary play. Setup tools are not shortcuts for in-world results.

## Combat

The public action is the player's semantic combat decision (for example `timeline_attack`). Commitment, post-motion recovery, timeline flushing and the next player decision boundary are settled internally by the runline. Narrative flourishes never replace mechanical resolution.

## Economy, inventory and progression

Vendor purchase/sale, transfer, repair, reinforcement, crafting/reclaim and skill-slot changes are ordinary gameplay mutations and therefore go through `turn_execute`. Direct public mutation tools for those domains should not exist on the hosted surface.

## Information discipline

Use only player-visible state to choose actions. Hidden NPC goals, guild strategy, drop rates, boss scripts, unseen nodes and undiscovered Unique Skills are not decision inputs. The runtime may use hidden authority to resolve consequences after a legal action is committed.

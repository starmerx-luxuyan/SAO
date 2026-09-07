# Aincrad mechanical specification

This document is the executable design contract for the default runtime. `CANON` statements are source-backed setting mechanics. `SIM` statements are original engine rules introduced where the novels/material do not provide a complete numeric algorithm.

## 1. Character state

### Canon layer

A player has a character level, HP, Strength and Agility progression, a finite set of equipped skill slots, inventory/equipment, Col, cursor/alignment state and social memberships. Skill proficiency is independent of character level and reaches 1000 at completion.

Skill slots:

| Level | slots |
|---:|---:|
| 1–5 | 2 |
| 6–11 | 3 |
| 12–19 | 4 |
| 20–29 | 5 |
| 30–39 | 6 |
| +10 levels | +1 |

Removing a skill normally forfeits proficiency unless a preservation mechanic/item is explicitly present.

### Simulation layer

`CharacterStats` uses only SAO-appropriate core values instead of importing D&D attributes. Level, STR and AGI drive derived combat values. HP and carry capacity use replaceable tuning functions so later corpus evidence can recalibrate them without changing the data model.

## 2. Items and equipment

Every item template has an ID, name, kind, weight, stack limit, rarity/tier hints, vendor value where known or simulated, tags and provenance. Every durable instance additionally tracks maximum/current durability, enhancement attempts and enhancement levels.

Weapon records support attack range, required level/STR, weight, damage type, reach, base speed and optional stat bonuses. Armour supports mitigation and weight. Shields are defensive equipment and may participate in guard/parry resolution.

Durability is an actual resource: attacks, guards, clashes and hostile effects can wear items. At zero durability an instance is broken and cannot provide its normal combat contribution until repaired or replaced. Exact wear quantities are `SIM`.

## 3. Weapon enhancement

### Canon layer

Five enhancement dimensions exist:

- `sharpness`: damage effectiveness (or `toughness` naming for blunt weapons)
- `quickness`: regular attack/Sword Skill speed
- `accuracy`: targeting/critical or weak-point assistance
- `heaviness`: ability to overpower/break opposing equipment
- `durability`: resistance to item damage

Enhancement consumes a limited attempt regardless of success or failure. When an item has exhausted its enhancement potential it is an end product; recklessly attempting further enhancement may destroy it.

### Simulation layer

Success probability is a bounded function of smith proficiency, material quality, recipe/item difficulty and accumulated enhancement pressure. The runtime exposes the probability before mutation. Default API refuses destructive over-cap enhancement unless explicitly requested.

## 4. Sword Skills

### Canon layer

A Sword Skill begins when the player deliberately enters an appropriate pre-motion. The system recognizes it, the weapon emits a skill effect, and the system assists execution along the technique trajectory. Completion creates post-motion rigidity; stronger/longer techniques generally create a larger commitment/recovery burden.

### Simulation state machine

```text
READY
  -> WINDUP / PRE_MOTION
  -> COMMITTED
  -> one or more ACTIVE_HIT windows
  -> POST_MOTION
  -> READY
```

Movement/defense availability is restricted by phase. A combatant in post-motion is easier to punish. Multi-hit Sword Skills carry individual hit windows but a single commitment/recovery envelope unless the skill definition says otherwise.

A Sword Skill definition includes weapon family, prerequisite proficiency, windup milliseconds, hit timing, damage multipliers, accuracy modifiers, movement/lunge properties, post-motion milliseconds and optional status/knockback/stagger effects. Exact milliseconds and multipliers are `SIM` calibration fields.

## 5. Normal combat

The runtime resolves discrete actions against an encounter clock. A normal physical attack performs:

1. legality/range/alive checks;
2. current commitment/recovery checks;
3. hit probability from attacker AGI/proficiency/weapon accuracy versus defender AGI/evasion/state;
4. optional defense reaction (evade, guard or parry) if the defender is eligible;
5. base weapon roll and STR/proficiency scaling;
6. critical/weak-point modification when applicable;
7. armour/guard mitigation;
8. HP change, durability wear, stagger and threat;
9. death/defeat/drop transition;
10. append-only combat event log.

The formulas are intentionally centralized in `CombatTuning`; they are simulation parameters and may be rebalanced without rewriting combat state flow.

### Guard

Guard converts a portion of incoming damage to prevented damage and equipment durability pressure. A sufficiently strong/heavy strike can cause guard break/stagger.

### Parry

Parry is timing-sensitive and proficiency-weighted. Success prevents or greatly reduces damage and can open a short punish window. Failure may leave the defender committed.

### Evasion

Evasion consumes a reaction opportunity and shifts hit probability according to AGI, state and action timing. It is less effective during post-motion or other commitment.

## 6. Threat, aggro and Switch

Threat is an engine representation of monster attention. Damage and selected supportive actions add threat; monsters choose targets through their AI profile rather than a universal magical taunt rule.

`Switch` is canonically a player-created tactic, not a formal menu skill. Runtime implementation therefore models the circumstances that make it work: one player creates an enemy recovery/attention window, a party member enters, and the AI experiences a reaction penalty when the attack rhythm/style changes. A successful switch can also transfer practical front-line pressure/threat without pretending that a hidden 'Switch button' exists in the world.

## 7. Healing and consumables

Normal healing potions restore HP over a duration and start a potion cooldown; chugging another potion during the cooldown does not provide a new useful heal. Exact duration/cooldown are `SIM` per item.

Healing crystals resolve essentially immediately and can restore the target according to crystal type; the default healing crystal performs a full heal. Curing crystals remove supported abnormal conditions. Teleport/corridor crystals perform travel actions. Anti-crystal fields block crystal effects, and voice-dependent activation can be prevented by an appropriate silence effect.

Consumables are inventory mutations. A failed legality check must not consume the item.

## 8. Status effects

Statuses are typed timed effects with source, magnitude, stack policy, tick interval and tags. The core supports poison, bleed, paralysis, silence, stun/stagger, movement impairment and buffs/debuffs. Status semantics are data-driven; unsupported canon-specific effects can be added without changing the encounter engine.

## 9. Parties and raids

A party may contain at most six members. A full raid contains at most eight parties, therefore 48 players. Party/raid membership controls friendly targeting, Switch eligibility, shared UI frames and optional loot/experience distribution rules; it does not grant omniscient information.

## 10. PvP and cursor state

Safe/protected areas block ordinary hostile damage according to zone rules. Outside protection, an unlawful hostile act against an eligible green player can change the attacker to orange. Hostile action against an already-orange target does not itself criminalize a green attacker. 'Red player' is treated as social terminology for player killers rather than a replacement for the system cursor field.

Criminal recovery is represented as a separate alignment/infamy ledger with quests/decay hooks so campaign content can implement the increasingly difficult restoration described by sources.

## 11. Crafting and repair

Blacksmith crafting consumes a recipe/material bundle, item difficulty and smith proficiency. Canon describes weapon production through heating/hammering and quality variation rather than a binary 'nothing created' failure; the simulation therefore always creates a product when valid materials are consumed, with quality/stat outcome varying within bounded ranges.

Repair restores durability subject to smith proficiency, item difficulty, material/fee requirements and possible maximum-durability wear for poor work. Salvage can convert eligible equipment back into material/ingot value.

## 12. Loot and economy

Defeated monsters can award Col and item/material drops from weighted loot tables. Ownership/party distribution is resolved before inventory mutation. Shop prices, drop weights and economic sinks are content data, not hardwired into combat.

## 13. Floors, fields and bosses

Aincrad is represented as one hundred floor states. Each floor may contain safe settlements, field zones, dungeon spaces, a labyrinth and boss room. Zone rules carry safe/anti-crystal flags and spawn/respawn profiles.

Field bosses may respawn. A floor boss is a persistent progression gate and does not normally respawn after defeat. Default world logic schedules the next-floor teleport-gate activation two in-world hours after floor-boss defeat, while allowing early activation when a player physically reaches/activates the next main-town gate.

## 14. Knowledge and GM discipline

The runtime's state is authoritative. The GM may describe sensory consequences and NPC interpretation but must not silently change HP, inventory, durability, loot, skill proficiency, quest flags, cursor state, encounter timing or world progression. When a rule action matters, the GM calls the runtime first and narrates the returned transition.

Character knowledge and GM/system knowledge are distinct. UI view models filter information by viewer and discovery state; a monster's hidden drop weights or boss AI state should not be exposed merely because the runtime knows it.

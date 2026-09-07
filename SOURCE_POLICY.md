# Source and provenance policy

This project separates **what Sword Art Online explicitly establishes** from **what a runnable game engine must simulate**.

## Provenance classes

Every important catalog/rule record should use one of these classes:

- `canon`: directly established by a primary or reliable secondary source.
- `canon_inferred`: a narrow consequence of canon, with the inference recorded.
- `simulation`: an engine rule/number introduced for deterministic play because canon does not specify the exact value.
- `optional_variant`: a deliberate table/game variant that is not part of the default Aincrad simulation.

A simulation number must never be described to the host model as an official SAO number.

## Source priority

Use, in descending preference:

1. Japanese/officially licensed Sword Art Online light novels and official supplementary material.
2. Official anime/game/site material when it describes the original Aincrad setting rather than a separate game adaptation.
3. Reliable reference summaries that cite the above sources, used as navigation and cross-checking rather than as a license to copy text.
4. Fan material only as design inspiration. Fan-created formulas and statistics are never promoted to canon.

Do not import mechanics from modern SAO games merely because they are convenient. A separate adaptation can later be represented by an explicit adapter/profile.

## Copyright/data policy

The repository stores compact facts, identifiers, derived schemas, source references, and original simulation rules. It must not contain substantial copied light-novel prose, subtitle scripts, episode transcripts, ripped game databases, copyrighted images, audio, models, or textures.

## Required provenance fields

Catalog entities should be able to carry:

```text
provenance.kind
provenance.sources[]
provenance.notes
```

`notes` should explain any inference or simulation calibration that could otherwise be mistaken for canon.

## Canon rules already locked for the core

- Skill proficiency is separate from player level and ranges to 1000.
- Initial skill-slot count is 2; slot 3 unlocks at Lv6, slot 4 at Lv12, slot 5 at Lv20, then one additional slot every ten levels.
- Removing an equipped skill normally loses its accumulated proficiency unless a special preservation mechanism applies.
- A party supports up to six members; a full raid supports up to eight parties (48 players).
- Sword Skills are initiated from a recognized pre-motion, receive system-assisted execution, and leave post-motion rigidity/recovery.
- `Switch` is a player-devised tactic rather than a formal system command.
- Weapon enhancement has five tracks: Sharpness/Toughness, Quickness, Accuracy, Heaviness, and Durability; success and failure both consume limited enhancement attempts.
- Healing crystals are effectively immediate; normal healing potions restore over time and are constrained by a potion-use cooldown.
- Attacking a green-cursor player outside protected rules can make the attacker orange; attacking an orange player does not cause the same criminal flag.
- Floor bosses do not normally respawn; field bosses may respawn.

Exact damage coefficients, HP curves, threat multipliers, durability wear, crafting-quality distributions, status tick timing, and most item prices are therefore `simulation` unless a source specifically establishes them.

# Development contract

Build the SAO/Aincrad plugin as production game software, not as a defensive-programming exercise.

- Implement real game/rules capability first.
- MCP tools and UI adapters stay thin; mechanics belong in normal Python modules.
- The authoritative mechanical state is shared by GM output, MCP tools and UI.
- Preserve canon/simulation provenance on rules and catalog data.
- Never present invented numeric formulas as official SAO canon.
- Use pytest for high-value mechanics, invariants and regressions; do not build elaborate harnesses without a concrete need.
- When a mechanic changes, follow its actual state flow through character -> action -> encounter -> inventory/world -> UI.
- Prefer functional vertical slices over piles of schemas with no executable behavior.
- Do not commit copyrighted novel/anime/game text, ripped databases, images, audio or game assets.
- Keep the primary v1 world focused on Aincrad; other VRMMO worlds should be adapters, not contaminating Aincrad rules.

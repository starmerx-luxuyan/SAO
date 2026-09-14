# v1.3.3 Playability Closure

This release is blocked until ordinary chat play closes the loop from player-visible observation to an executable GM decision and an authoritative runtime mutation.

A feature is not considered playable merely because an internal rule or MCP tool exists.

Required closure for an ordinary action:

1. Player-visible capability is present in `get_gm_observation`.
2. The action is accepted by `GMDecisionRuntime` from that fresh observation.
3. `GMTurnExecutor` delegates to the authoritative runtime/economy/relationship implementation.
4. The mutation survives save/export/import.
5. Hosted public MCP exposes the observation/decision path needed by the GM skill.
6. A scenario-level test executes the action through the same hosted GM path used in chat.

## High-frequency acceptance scenario

The Floor 1 frontline scenario must support, without setup/admin mutations or fabricated results:

- fight a real labyrinth monster with a party;
- receive EXP, Col and material drops;
- return to Tolbana;
- sell selected materials to a live merchant;
- have an NPC blacksmith reinforce an owned weapon using owned materials and a paid service;
- buy ordinary food/drink from a live food merchant;
- export and re-import the resulting campaign with identical authoritative balances and item state.

The release is not playable if any step can only be narrated.

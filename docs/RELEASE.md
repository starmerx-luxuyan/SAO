# Release contract

This document defines the invariants for the SAO Aincrad v1 release line.

## Version

`src/sao_mcp/__init__.py::__version__` is the Python package version source. `pyproject.toml` reads it through Hatch's version source instead of duplicating the package version. The ChatGPT/Codex plugin manifest must carry the same release number and is checked in CI.

## Production entry point

The installed console script is `sao-mcp`, implemented by `sao_mcp.cli:main`. It imports `sao_mcp.server_bootstrap`, not the partial core server module. `server_bootstrap` is therefore the production composition root for the complete tool/runtime surface.

Supported transports are:

- `stdio` (default)
- `streamable-http`, configured with `SAO_MCP_HOST` and `SAO_MCP_PORT`

## Runtime authority

A release has one authoritative campaign runtime. Scenario modules install content/services into that runtime; they do not create competing campaign states. MCP tools and UI read or mutate the same runtime authority.

Player/GM observation functions are queries. They must not normalize, repair or otherwise mutate campaign state as a side effect.

## Public MCP surface

Release CI imports the full production bootstrap and asks `MCPServer.list_tools()` for the registered public surface. A critical cross-section must remain present, including character, combat, inventory, world/adventure, persistence and GM observation/decision/execution tools.

Adding or removing public tools is allowed when gameplay requires it, but an accidental registration loss is a release failure.

## Persistence

The current save schema is `sao.aincrad.save.v3`.

A save migration is valid only when it reconstructs the authoritative state exactly. Older payloads that lack required encounter timing/lifecycle information are rejected rather than filled with guessed defaults. Save/load equivalence and checkpoint churn are covered by regression tests.

Changing the save schema requires:

1. a new explicit schema identifier;
2. an exact migration for supported older payloads, or a clear rejection path where exact migration is impossible;
3. regression coverage for the new boundary;
4. updated README/release documentation.

## Packaging

The wheel is part of the product. Release CI must build it and install it into a clean virtual environment. The installed package must expose:

- `sao_mcp.__version__` matching release metadata;
- the complete `server_bootstrap` composition;
- packaged HUD/system-menu/boss UI resources used by the MCP Apps surface.

A green editable-source test run is insufficient if the built wheel cannot satisfy those checks.

## Release gate

A release candidate is ready only when the repository's normal CI passes from a clean commit and no temporary audit workflow/script is left in the release tree. Campaign stress tests remain part of the permanent suite.

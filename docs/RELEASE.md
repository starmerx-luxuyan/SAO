# Release contract

This document defines the invariants for the SAO Aincrad v1 release line.

## Version

`src/sao_mcp/__init__.py::__version__` is the Python package version source. `pyproject.toml` reads it through Hatch instead of duplicating the version. The plugin manifest must match it and CI enforces the equality.

## Production entry points

The installed console script is `sao-mcp`, implemented by `sao_mcp.cli:main`. `server_bootstrap.py` is the complete internal composition root. `server_public.py` reuses the same authoritative runtime but exposes the bounded hosted player/GM/setup surface.

Supported transports are `stdio` and `streamable-http`; `SAO_MCP_SURFACE` selects `public` or `full`.

## Runtime authority

A release has one authoritative campaign runtime. Scenario modules install content/services into that runtime; they do not create competing campaign states. MCP tools and UI read or mutate the same authority.

Player/GM observation functions are queries and must not repair or otherwise mutate authoritative state as a side effect.

## Setup and Campaign Blueprint

Hosted setup follows `begin -> configure/apply -> finalize`. A finalized hosted campaign cannot reopen setup; only the full internal surface exposes explicit maintenance reopening.

`validate_campaign_blueprint` and `preview_campaign_blueprint` must remain non-mutating. `apply_campaign_blueprint` must require open setup, must complete the whole blueprint off-state before committing, and must not finalize setup implicitly. Campaign Blueprint is a composition layer over the same custom catalog, character, inventory and custom-mechanics authorities rather than a second rules engine.

The current blueprint schema is `sao.aincrad.campaign-blueprint.v1`.

## Public MCP surface

Release CI asks the public and full `MCPServer` instances for their registered tool sets. The hosted public tool set is exact and intentional; new public tools require an explicit release-contract update. Internal administration tools such as setup reopening, raw world advancement and direct floor-boss completion must remain absent from the hosted surface.

## Persistence

The current save schema is `sao.aincrad.save.v4`. It persists campaign setup state, campaign-local custom definitions, actor custom mechanics, item instances and the rest of the deterministic campaign state. Campaign Blueprint does not introduce another persistence format; after apply, its result is ordinary v4 runtime state.

v3 migrates exactly with an empty custom catalog and finalized legacy setup state. Older payloads that lack information required for exact reconstruction are rejected rather than completed with guessed defaults.

Changing the save schema requires a new identifier, exact supported migrations or explicit rejection, regression coverage and updated release documentation.

## Packaging

The wheel is part of the product. Release CI builds it and installs it into a clean virtual environment. The installed package must expose the release version, both public/full MCP compositions and packaged HUD/System Menu/Boss Raid resources. The exact hosted tool set is checked from the installed wheel, not only the editable source tree.

## Release gate

A release candidate is ready only when clean CI passes compile, the full pytest suite, wheel build, clean-wheel smoke, exact public-surface checks, UI CSP/domain checks and plugin-bundle assembly. No temporary integration workflow or staging file may remain in the release tree.

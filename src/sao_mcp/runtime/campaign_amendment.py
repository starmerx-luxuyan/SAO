from __future__ import annotations

import hashlib
import json
from typing import Any

from sao_mcp.rules.inventory import carry_capacity, inventory_weight
from sao_mcp.runtime.character_setup import (
    SETUP_FINALIZED,
    campaign_setup_state,
    character_setup_state,
    configure_character,
    grant_character_item,
)
from sao_mcp.runtime.persistence import export_runtime, import_runtime


AMENDMENT_SCHEMA = "sao.aincrad.campaign-amendment.v1"


def _digest(amendment: dict[str, Any]) -> str:
    canonical = json.dumps(amendment, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _clone_runtime(runtime):
    clone = type(runtime)(seed=0)
    import_runtime(export_runtime(runtime), into=clone)
    return clone


def _target(runtime, amendment: dict[str, Any]):
    actor_id = str(amendment.get("actor_id", "")).strip()
    if not actor_id:
        raise ValueError("campaign amendment requires actor_id")
    actor = runtime.actors[actor_id]
    expected_name = amendment.get("actor_name")
    if expected_name is not None and actor.name != str(expected_name):
        raise ValueError("campaign amendment actor_name does not match authoritative actor")
    return actor


def _item_rows(amendment: dict[str, Any]) -> list[dict[str, Any]]:
    rows = amendment.get("grant_items", [])
    if not isinstance(rows, list):
        raise ValueError("grant_items must be a list")
    clean: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"grant_items[{index}] must be an object")
        template_id = str(row.get("template_id", "")).strip()
        if not template_id:
            raise ValueError(f"grant_items[{index}] requires template_id")
        clean.append(dict(row))
    return clean


def _apply_in_place(runtime, amendment: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(amendment, dict):
        raise ValueError("campaign amendment must be an object")
    if amendment.get("schema") != AMENDMENT_SCHEMA:
        raise ValueError(f"campaign amendment schema must be {AMENDMENT_SCHEMA!r}")
    amendment_id = str(amendment.get("amendment_id", "")).strip()
    if not amendment_id:
        raise ValueError("campaign amendment requires amendment_id")
    state = campaign_setup_state(runtime)
    if state["status"] != SETUP_FINALIZED:
        raise ValueError("campaign amendments apply only to a finalized campaign")
    actor = _target(runtime, amendment)

    configure: dict[str, Any] = {}
    if "set_col" in amendment:
        configure["col"] = int(amendment["set_col"])
    if "custom_mechanics" in amendment:
        mechanics = amendment["custom_mechanics"]
        if not isinstance(mechanics, list):
            raise ValueError("custom_mechanics must be a list")
        configure["custom_mechanics"] = mechanics
        configure["apply_custom_mechanics_retroactive"] = bool(
            amendment.get("apply_custom_mechanics_retroactive", True)
        )
    if configure:
        configure_character(runtime, actor.actor_id, **configure)

    granted: list[dict[str, Any]] = []
    for row in _item_rows(amendment):
        item = grant_character_item(
            runtime,
            actor.actor_id,
            str(row["template_id"]),
            quantity=int(row.get("quantity", 1)),
            durability=row.get("durability"),
            max_durability=row.get("max_durability"),
            max_enhancement_attempts=row.get("max_enhancement_attempts"),
            enhancement_attempts_used=int(row.get("enhancement_attempts_used", 0)),
            enhancements=row.get("enhancements"),
            quality=float(row.get("quality", 1.0)),
            maker_id=row.get("maker_id"),
            metadata=dict(row.get("metadata") or {}),
            equip_now=bool(row.get("equip_now", False)),
            allow_overweight=False,
        )
        granted.append(
            {
                "instance_id": item.instance_id,
                "template_id": item.template_id,
                "quantity": item.quantity,
            }
        )

    state = campaign_setup_state(runtime)
    state["revision"] = int(state.get("revision", 0)) + 1
    state["last_amended_at_world_ms"] = int(runtime.world.now_ms)
    state["last_amendment_id"] = amendment_id
    weight = inventory_weight(actor, runtime.catalog)
    capacity = carry_capacity(actor)
    if weight > capacity + 1e-9:
        raise RuntimeError("campaign amendment committed an overweight inventory")
    return {
        "schema": AMENDMENT_SCHEMA,
        "amendment_id": amendment_id,
        "digest_sha256": _digest(amendment),
        "actor_id": actor.actor_id,
        "granted_items": granted,
        "inventory_weight": round(weight, 4),
        "carry_capacity": round(capacity, 4),
        "setup_revision": int(state["revision"]),
        "character": character_setup_state(runtime, actor.actor_id),
    }


def validate_campaign_amendment(runtime, amendment: dict[str, Any]) -> dict[str, Any]:
    clone = _clone_runtime(runtime)
    result = _apply_in_place(clone, amendment)
    return {
        "valid": True,
        "schema": result["schema"],
        "amendment_id": result["amendment_id"],
        "digest_sha256": result["digest_sha256"],
        "actor_id": result["actor_id"],
        "inventory_weight": result["inventory_weight"],
        "carry_capacity": result["carry_capacity"],
    }


def preview_campaign_amendment(runtime, amendment: dict[str, Any]) -> dict[str, Any]:
    clone = _clone_runtime(runtime)
    result = _apply_in_place(clone, amendment)
    result["committed"] = False
    return result


def apply_campaign_amendment(runtime, amendment: dict[str, Any]) -> dict[str, Any]:
    clone = _clone_runtime(runtime)
    result = _apply_in_place(clone, amendment)
    import_runtime(export_runtime(clone), into=runtime)
    result["committed"] = True
    return result

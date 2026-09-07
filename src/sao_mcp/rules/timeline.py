from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class QueuedPlayerAttack:
    action_id: str
    encounter_id: str
    attacker_id: str
    target_id: str
    sword_skill_id: str | None
    defense: str
    started_at_ms: int
    impact_at_ms: int
    seed: int
    start_distance_m: float
    sequence: int
    interrupted_reason: str | None = None

    def dump(self) -> dict:
        return asdict(self)

    @classmethod
    def load(cls, payload: dict) -> "QueuedPlayerAttack":
        return cls(
            action_id=str(payload["action_id"]),
            encounter_id=str(payload["encounter_id"]),
            attacker_id=str(payload["attacker_id"]),
            target_id=str(payload["target_id"]),
            sword_skill_id=payload.get("sword_skill_id"),
            defense=str(payload.get("defense", "auto")),
            started_at_ms=int(payload["started_at_ms"]),
            impact_at_ms=int(payload["impact_at_ms"]),
            seed=int(payload["seed"]),
            start_distance_m=float(payload.get("start_distance_m", 0.0)),
            sequence=int(payload.get("sequence", 0)),
            interrupted_reason=payload.get("interrupted_reason"),
        )

from pathlib import Path

path = Path("src/sao_mcp/runtime/npc_autonomy_runtime.py")
text = path.read_text(encoding="utf-8")
old = '''    def _on_knowledge_update(self, event) -> None:\n        if event.knower_id not in self.npcs.definitions:\n            return\n        agenda = self._agenda(event.knower_id)\n        if not agenda.active:\n            self._evaluate_npc_decision(event.knower_id, self.world.now_ms)\n\n'''
new = '''    def _knowledge_event_affects_goal_selection(self, npc_id: str, fact_id: str) -> bool:\n        core = self._ensure_actor_core(npc_id)\n        if any(goal.required_fact_id == fact_id for goal in core.long_term_goals.values()):\n            return True\n        definition = self.npcs.definitions[npc_id]\n        if "shop_owner" in definition.roles:\n            return fact_id == f"{LOCATION_UNAVAILABLE_FACT_PREFIX}{definition.home_location_id}"\n        return False\n\n    def _on_knowledge_update(self, event) -> None:\n        if event.knower_id not in self.npcs.definitions:\n            return\n        if not self._knowledge_event_affects_goal_selection(event.knower_id, event.fact_id):\n            return\n        agenda = self._agenda(event.knower_id)\n        if not agenda.active:\n            self._evaluate_npc_decision(event.knower_id, self.world.now_ms)\n\n'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"expected one knowledge-update hook anchor, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

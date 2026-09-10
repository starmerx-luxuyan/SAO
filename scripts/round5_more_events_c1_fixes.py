from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one exact match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_in_method(path: str, method_name: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    marker = f"    def {method_name}("
    start = text.find(marker)
    if start < 0:
        raise RuntimeError(f"method {method_name} not found in {path}")
    end = text.find("\n    def ", start + len(marker))
    if end < 0:
        end = len(text)
    block = text[start:end]
    count = block.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected one exact match inside {path}:{method_name}, found {count}"
        )
    rewritten = block.replace(old, new, 1)
    file.write_text(text[:start] + rewritten + text[end:], encoding="utf-8")


# Event rule identity remains strict; scenario/event services themselves are the idempotent unit.
replace_once(
    "src/sao_mcp/runtime/world_event_runtime.py",
    '''        self.world_event_rules: dict[str, WorldEventRule] = {}\n        self.world_events = WorldEventLedger()\n        self._evaluating_world_events = False\n''',
    '''        self.world_event_rules: dict[str, WorldEventRule] = {}\n        self.world_event_services: dict[str, object] = {}\n        self.world_events = WorldEventLedger()\n        self._evaluating_world_events = False\n''',
)
replace_once(
    "src/sao_mcp/runtime/world_event_runtime.py",
    '''    def register_world_event_rule(\n        self,\n        rule_id: str,\n        discover: WorldEventDiscover,\n        resolve: WorldEventResolver,\n    ) -> None:\n''',
    '''    def install_world_event_service(self, service_id: str, factory: Callable[[], object]) -> object:\n        clean_service_id = service_id.strip()\n        if not clean_service_id:\n            raise ValueError("world-event service id is required")\n        existing = self.world_event_services.get(clean_service_id)\n        if existing is not None:\n            return existing\n        service = factory()\n        self.world_event_services[clean_service_id] = service\n        return service\n\n    def register_world_event_rule(\n        self,\n        rule_id: str,\n        discover: WorldEventDiscover,\n        resolve: WorldEventResolver,\n    ) -> None:\n''',
)

replace_once(
    "src/sao_mcp/scenarios/floor5_fuscus.py",
    '''def install_floor5_fuscus_scenario(runtime) -> Floor5FuscusScenario:\n    return Floor5FuscusScenario(runtime)\n''',
    '''def install_floor5_fuscus_scenario(runtime) -> Floor5FuscusScenario:\n    service = runtime.install_world_event_service(\n        "floor5.fuscus", lambda: Floor5FuscusScenario(runtime)\n    )\n    if not isinstance(service, Floor5FuscusScenario):\n        raise RuntimeError("floor5.fuscus service registry contains the wrong service type")\n    return service\n''',
)

# No Harin instance yet means there are zero eligible event occurrences; operational APIs remain strict.
replace_in_method(
    "src/sao_mcp/scenarios/floor7_pursuit.py",
    "_discover_labyrinth_pursuit_events",
    '''        for instance_id, state in self._harin_states().items():\n''',
    '''        states = self.runtime.world.global_flags.get("floor7_harin_escape_instances", {})\n        for instance_id, state in states.items():\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor7_pursuit.py",
    '''    return Floor7PursuitScenario(runtime)\n''',
    '''    service = runtime.install_world_event_service(\n        "floor7.pursuit", lambda: Floor7PursuitScenario(runtime)\n    )\n    if not isinstance(service, Floor7PursuitScenario):\n        raise RuntimeError("floor7.pursuit service registry contains the wrong service type")\n    return service\n''',
)

# Existing Phase-B event services use the same installation authority so repeated composition cannot
# create duplicate rule registrations.
replace_once(
    "src/sao_mcp/scenarios/floor6_stachion.py",
    '''    return Floor6StachionScenario(runtime)\n''',
    '''    service = runtime.install_world_event_service(\n        "floor6.stachion", lambda: Floor6StachionScenario(runtime)\n    )\n    if not isinstance(service, Floor6StachionScenario):\n        raise RuntimeError("floor6.stachion service registry contains the wrong service type")\n    return service\n''',
)
replace_once(
    "src/sao_mcp/scenarios/floor6_buxum.py",
    '''    return Floor6BuxumScenario(runtime, cube)\n''',
    '''    service = runtime.install_world_event_service(\n        "floor6.buxum", lambda: Floor6BuxumScenario(runtime, cube)\n    )\n    if not isinstance(service, Floor6BuxumScenario):\n        raise RuntimeError("floor6.buxum service registry contains the wrong service type")\n    if service.cube is not cube:\n        raise RuntimeError("floor6.buxum service is already bound to a different Cube service")\n    return service\n''',
)

# C1 extended the authority test with Fuscus/Pursuit IDs; actually install those services before
# asserting their rules, and lock idempotent installation as part of the contract.
replace_once(
    "tests/test_world_event_authority.py",
    '''from sao_mcp.scenarios.floor5_fuscus import FUSCUS_FLAG_DROP_EVENT_RULE_ID, Floor5FuscusScenario\nfrom sao_mcp.scenarios.floor7_pursuit import LABYRINTH_PURSUIT_EVENT_RULE_ID, Floor7PursuitScenario\n''',
    '''from sao_mcp.scenarios.floor5_fuscus import (\n    FUSCUS_FLAG_DROP_EVENT_RULE_ID,\n    Floor5FuscusScenario,\n    install_floor5_fuscus_scenario,\n)\nfrom sao_mcp.scenarios.floor7_pursuit import (\n    LABYRINTH_PURSUIT_EVENT_RULE_ID,\n    Floor7PursuitScenario,\n    install_floor7_pursuit_scenario,\n)\n''',
)
replace_once(
    "tests/test_world_event_authority.py",
    '''def test_floor6_conditional_scene_transitions_are_registered_world_event_rules():\n    runtime = HousingAincradRuntime(seed=811)\n    cube = install_floor6_irrational_cube_scenario(runtime)\n    install_floor6_buxum_scenario(runtime, cube)\n    install_floor6_stachion_scenario(runtime)\n\n    assert set(runtime.world_event_rules).issuperset(\n''',
    '''def test_conditional_scene_transitions_are_registered_world_event_rules():\n    runtime = HousingAincradRuntime(seed=811)\n    cube = install_floor6_irrational_cube_scenario(runtime)\n    buxum = install_floor6_buxum_scenario(runtime, cube)\n    stachion = install_floor6_stachion_scenario(runtime)\n    fuscus = install_floor5_fuscus_scenario(runtime)\n    pursuit = install_floor7_pursuit_scenario(runtime)\n\n    assert install_floor6_buxum_scenario(runtime, cube) is buxum\n    assert install_floor6_stachion_scenario(runtime) is stachion\n    assert install_floor5_fuscus_scenario(runtime) is fuscus\n    assert install_floor7_pursuit_scenario(runtime) is pursuit\n\n    assert set(runtime.world_event_rules).issuperset(\n''',
)

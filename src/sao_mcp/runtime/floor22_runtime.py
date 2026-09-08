"""Floor 22 is scenario content, not a game-runtime subclass.

Import the scenario service from here only for old module-path compatibility. New code should use
``sao_mcp.scenarios.floor22_witch`` directly.
"""

from sao_mcp.scenarios.floor22_witch import Floor22WitchScenario, install_floor22_witch_scenario

__all__ = ["Floor22WitchScenario", "install_floor22_witch_scenario"]

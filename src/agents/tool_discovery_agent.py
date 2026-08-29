from typing import List

from mcp_tools.weather_tools import registry as weather_registry
from mcp_tools.news_tools import registry as news_registry
from mcp_tools.recipe_tools import registry as recipe_registry
from mcp_tools.commute_tools import registry as commute_registry


class ToolDiscoveryAgent:
    def __init__(self) -> None:
        self.registries = [
            weather_registry,
            news_registry,
            recipe_registry,
            commute_registry,
        ]

    def discover(self) -> List[str]:
        tools = []
        for registry in self.registries:
            tools.extend(registry.list_tools())
        return tools

    def describe(self, tool_name: str) -> str:
        for registry in self.registries:
            if tool_name in registry.list_tools():
                schema = registry.describe(tool_name)
                return f"{schema.name}: {schema.description}"
        return f"Tool '{tool_name}' not found."

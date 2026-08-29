from typing import Dict, List


class ToolRegistry:
    """Simple registry that resembles multiple MCP tool servers for a beginner-friendly agent workflow."""

    def __init__(self) -> None:
        self.tools: Dict[str, object] = {}

    def register(self, name: str, tool: object) -> None:
        self.tools[name] = tool

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())

    def get_tool(self, name: str) -> object:
        return self.tools[name]

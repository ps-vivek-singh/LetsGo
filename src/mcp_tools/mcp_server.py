from typing import Callable, Dict, List


class MCPToolServer:
    """A lightweight MCP-style server wrapper for beginner-friendly tool registration."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: Dict[str, Callable] = {}

    def tool(self, name: str | None = None) -> Callable:
        def decorator(func: Callable) -> Callable:
            tool_name = name or func.__name__
            self._tools[tool_name] = func
            return func

        return decorator

    def list_tools(self) -> List[str]:
        return list(self._tools.keys())

    def call(self, tool_name: str, *args, **kwargs):
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' not found in server '{self.name}'.")
        return self._tools[tool_name](*args, **kwargs)

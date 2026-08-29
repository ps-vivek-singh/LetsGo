import asyncio
from typing import Any, Callable, Dict, List
from fastmcp import FastMCP


class RealMCPServer:
    """An MCP server wrapping FastMCP from the official MCP SDK."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.fast_mcp = FastMCP(name)

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        self.fast_mcp.tool(name=name)(func)

    def list_tools(self) -> List[str]:
        tools_list = asyncio.run(self.fast_mcp.list_tools())
        return [t.name for t in tools_list]

    def call_tool(self, name: str, *args, **kwargs) -> Any:
        tool = asyncio.run(self.fast_mcp.get_tool(name))
        return tool.fn(*args, **kwargs)

    def health_check(self) -> Dict[str, Any]:
        tools_list = asyncio.run(self.fast_mcp.list_tools())
        return {"server": self.name, "tool_count": len(tools_list), "status": "ok"}

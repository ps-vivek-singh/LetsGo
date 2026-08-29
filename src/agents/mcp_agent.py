"""MCPAgent — an agent that connects to an MCP server and invokes tools.

Supports the connect → list_tools → invoke pattern required by the
agentic loop:

    agent = MCPAgent("weather", weather_server)
    agent.connect()                        # handshake
    tools = agent.list_tools()             # discover capabilities
    result = agent.invoke("get_weather", location="Chicago")
"""
from __future__ import annotations

from typing import Any, Dict, List

from mcp_tools.real_mcp_server import RealMCPServer


class MCPAgent:
    """Lightweight agent that wraps a single RealMCPServer."""

    def __init__(self, name: str, server: RealMCPServer) -> None:
        self.name = name
        self.server = server
        self._connected = False
        self._available_tools: List[str] = []

    # ── Connection lifecycle ───────────────────────────────────────────────

    def connect(self) -> Dict[str, Any]:
        """Establish a connection to the MCP server and cache its tool list.

        Returns a handshake dict with server name, tool count, and status.
        """
        health = self.server.health_check()
        self._available_tools = self.server.list_tools()
        self._connected = True
        return {
            "server": self.name,
            "tools": self._available_tools,
            "tool_count": len(self._available_tools),
            "status": health.get("status", "ok"),
        }

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Tool discovery ─────────────────────────────────────────────────────

    def list_tools(self) -> List[str]:
        """Return the list of tools exposed by the connected server."""
        if not self._connected:
            self.connect()
        return list(self._available_tools)

    def has_tool(self, tool_name: str) -> bool:
        """Check whether a specific tool is available on this server."""
        return tool_name in self._available_tools

    # ── Tool invocation ────────────────────────────────────────────────────

    def invoke(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a tool on the connected server by name.

        Raises KeyError if the tool doesn't exist.
        """
        if not self._connected:
            self.connect()
        return self.server.call_tool(tool_name, *args, **kwargs)

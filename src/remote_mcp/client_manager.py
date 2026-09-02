"""MCP Client Manager — Unified pool manager for remote and in-process MCP servers.

Manages connection lifecycle, server lookup, tool discovery, and clean shutdown.
Supports both remote protocol mode (stdio subprocesses / SSE) and backward-compatible
in-process mode for local development and fast test execution.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from remote_mcp.remote_client import RemoteMCPClient
from mcp_tools.real_mcp_server import RealMCPServer
from services.config import Config

logger = logging.getLogger("letsgo.remote_mcp.client_manager")

# Server name to script path mapping for stdio remote execution
SERVER_SCRIPT_MAP: Dict[str, str] = {
    "weather": "src/mcp_tools/weather_tools.py",
    "weather-server": "src/mcp_tools/weather_tools.py",
    "commute": "src/mcp_tools/commute_tools.py",
    "commute-server": "src/mcp_tools/commute_tools.py",
    "recipe": "src/mcp_tools/recipe_tools.py",
    "recipe-server": "src/mcp_tools/recipe_tools.py",
    "news": "src/mcp_tools/news_tools.py",
    "news-server": "src/mcp_tools/news_tools.py",
    "itinerary": "src/mcp_tools/itinerary_tools.py",
    "itinerary-server": "src/mcp_tools/itinerary_tools.py",
    "gmail": "src/mcp_tools/email_tools.py",
    "gmail-server": "src/mcp_tools/email_tools.py",
}


class MCPClientManager:
    """Manages MCP server client connections (Remote stdio/SSE or In-Process)."""

    def __init__(self, mcp_mode: Optional[str] = None) -> None:
        self.mcp_mode = (mcp_mode or Config.get_mcp_mode()).lower()
        self._remote_clients: Dict[str, RemoteMCPClient] = {}
        self._in_process_servers: Dict[str, RealMCPServer] = {}

    def _get_or_create_in_process_server(self, name: str) -> RealMCPServer:
        norm_name = name.removesuffix("-server")
        if norm_name in self._in_process_servers:
            return self._in_process_servers[norm_name]

        server = RealMCPServer(f"{norm_name}-server")
        if norm_name == "weather":
            from mcp_tools.weather_tools import WeatherTool
            tool = WeatherTool()
            server.register_tool("get_weather", tool.get_weather)
        elif norm_name == "news":
            from mcp_tools.news_tools import get_headlines
            server.register_tool("get_headlines", get_headlines)
        elif norm_name == "recipe":
            from mcp_tools.recipe_tools import RecipeTool
            tool = RecipeTool()
            server.register_tool("get_recipe", tool.get_recipe)
            server.register_tool("get_meal_recipe", tool.get_meal_recipe)
        elif norm_name == "commute":
            from mcp_tools.commute_tools import CommuteTool
            tool = CommuteTool()
            server.register_tool("get_commute_route", tool.get_commute_route)
            server.register_tool("get_commute_advice", tool.get_commute_advice)
        elif norm_name == "itinerary":
            from mcp_tools.itinerary_tools import get_itinerary
            server.register_tool("get_itinerary", get_itinerary)
        elif norm_name in ("gmail", "email"):
            from mcp_tools.email_tools import send_email_briefing, send_itinerary_email
            server.register_tool("send_email_briefing", send_email_briefing)
            server.register_tool("send_itinerary_email", send_itinerary_email)

        self._in_process_servers[norm_name] = server
        return server

    def get_client(self, server_name: str) -> Union[RemoteMCPClient, RealMCPServer]:
        """Return connected client or server object for the requested server name."""
        norm_name = server_name.removesuffix("-server")

        if self.mcp_mode == "remote":
            if norm_name in self._remote_clients:
                return self._remote_clients[norm_name]

            script_path = SERVER_SCRIPT_MAP.get(server_name) or SERVER_SCRIPT_MAP.get(norm_name)
            if not script_path:
                raise ValueError(f"Unknown remote MCP server name: '{server_name}'")

            client = RemoteMCPClient(name=f"{norm_name}-server", script_path=script_path)
            client.connect()
            self._remote_clients[norm_name] = client
            return client
        else:
            return self._get_or_create_in_process_server(norm_name)

    def list_servers(self) -> List[str]:
        return ["weather", "news", "recipe", "commute", "itinerary", "gmail"]

    def list_tools(self, server_name: str) -> List[str]:
        client = self.get_client(server_name)
        if isinstance(client, RemoteMCPClient):
            return client.list_tools()
        return client.list_tools()

    def call_tool(self, server_name: str, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        client = self.get_client(server_name)
        if isinstance(client, RemoteMCPClient):
            return client.invoke(tool_name, *args, **kwargs)
        return client.call_tool(tool_name, *args, **kwargs)

    def close_all(self) -> None:
        """Cleanly shutdown all remote MCP client transports."""
        for name, client in self._remote_clients.items():
            try:
                client.close()
            except Exception as exc:
                logger.warning("Error closing remote MCP client %s: %s", name, exc)
        self._remote_clients.clear()

    def __enter__(self) -> MCPClientManager:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close_all()

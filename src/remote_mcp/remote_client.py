"""Remote MCP Client — Standards-compliant remote MCP transport client wrapper.

Wraps the official FastMCP/MCP SDK client transports (stdio & SSE) to provide:
- Connection initialization & capability negotiation handshake
- Dynamic protocol tool discovery (`list_tools`)
- Dynamic tool invocation with argument validation and result parsing
- Structured MCP error handling
- Clean lifecycle management and connection shutdown
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport, SSETransport

logger = logging.getLogger("letsgo.remote_mcp.remote_client")


class RemoteMCPClient:
    """Standards-compliant remote MCP client for stdio / SSE server connections."""

    def __init__(
        self,
        name: str,
        script_path: str,
        transport_type: str = "stdio",
        sse_url: Optional[str] = None,
        timeout: float = 25.0,
    ) -> None:
        self.name = name
        self.script_path = script_path
        self.transport_type = transport_type.lower()
        self.sse_url = sse_url
        self.timeout = timeout

        self._client: Optional[Client] = None
        self._connected: bool = False
        self._tools_cache: List[str] = []

    def _build_transport(self) -> Any:
        if self.transport_type == "sse" and self.sse_url:
            return SSETransport(url=self.sse_url)

        # Default stdio subprocess transport
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        src_path = os.path.join(project_root, "src")

        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else src_path
        env["PYTHONUNBUFFERED"] = "1"

        target_script = self.script_path
        if not os.path.isabs(target_script):
            target_script = os.path.join(project_root, target_script)

        return StdioTransport(
            command=sys.executable,
            args=[target_script],
            env=env,
        )

    def _ensure_event_loop(self) -> asyncio.AbstractEventLoop:
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    def _run_async(self, coro: Any) -> Any:
        loop = self._ensure_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(lambda: asyncio.run(coro)).result(timeout=self.timeout)
        return loop.run_until_complete(coro)

    # ── Protocol Lifecycle ───────────────────────────────────────────────────

    def connect(self) -> Dict[str, Any]:
        """Establish transport connection and run initialization handshake."""
        if self._connected and self._client:
            return self.health_check()

        try:
            transport = self._build_transport()
            self._client = Client(transport=transport)
            
            async def _init_session():
                await self._client.__aenter__()
                tools = await self._client.list_tools()
                self._tools_cache = [t.name for t in tools]

            self._run_async(_init_session())
            self._connected = True
            logger.info("Successfully established remote MCP connection to %s", self.name)
            return self.health_check()
        except Exception as exc:
            logger.error("Remote MCP connection failed for %s: %s", self.name, exc)
            self._connected = False
            self._client = None
            raise ConnectionError(f"Failed to connect to remote MCP server '{self.name}': {exc}") from exc

    @property
    def is_connected(self) -> bool:
        return self._connected

    def health_check(self) -> Dict[str, Any]:
        return {
            "server": self.name,
            "transport": self.transport_type,
            "tool_count": len(self._tools_cache),
            "status": "ok" if self._connected else "disconnected",
        }

    # ── Tool Discovery ───────────────────────────────────────────────────────

    def list_tools(self) -> List[str]:
        """Discover tools exposed by remote MCP server via protocol list_tools."""
        if not self._connected or not self._client:
            self.connect()
        return list(self._tools_cache)

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.list_tools()

    # ── Tool Invocation ──────────────────────────────────────────────────────

    def invoke(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Call a remote tool over protocol transport with structured args."""
        if not self._connected or not self._client:
            self.connect()

        kwargs_to_pass = dict(kwargs)
        if args and isinstance(args[0], dict):
            kwargs_to_pass.update(args[0])

        async def _call():
            raw_res = await self._client.call_tool(tool_name, kwargs_to_pass)
            if hasattr(raw_res, "structured_content") and raw_res.structured_content:
                return raw_res.structured_content
            if hasattr(raw_res, "data") and raw_res.data:
                return raw_res.data
            if hasattr(raw_res, "content") and raw_res.content:
                for item in raw_res.content:
                    text_val = getattr(item, "text", "")
                    if text_val:
                        try:
                            return json.loads(text_val)
                        except Exception:
                            return text_val
            return raw_res

        try:
            return self._run_async(_call())
        except Exception as exc:
            logger.error("Remote tool invocation error on %s.%s: %s", self.name, tool_name, exc)
            raise RuntimeError(f"Remote MCP tool invocation '{tool_name}' failed: {exc}") from exc

    # ── Shutdown ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Cleanly close remote client session and transport process."""
        if self._client and self._connected:
            try:
                async def _close():
                    await self._client.__aexit__(None, None, None)
                self._run_async(_close())
            except Exception as exc:
                logger.warning("Error during remote MCP client close for %s: %s", self.name, exc)
            finally:
                self._connected = False
                self._client = None
                self._tools_cache = []

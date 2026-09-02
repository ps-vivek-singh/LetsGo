"""Unit & Integration Tests for Remote MCP Protocol Implementation.

Tests:
1. Protocol initialization and handshake over stdio transport.
2. Dynamic protocol tool listing & discovery.
3. Dynamic protocol tool invocation with structured args & results.
4. Invalid tool & argument error handling.
5. Remote connection failure & cleanup behavior.
6. Clean disconnect & shutdown.
7. AgenticLoop execution over remote MCP clients.
8. MCPClientManager mode switching (remote vs in_process).
"""
from __future__ import annotations

import os
import sys
import unittest

# Ensure src/ is on sys.path
sys.path.insert(0, str(os.path.abspath("src")))

from remote_mcp.remote_client import RemoteMCPClient
from remote_mcp.client_manager import MCPClientManager
from agents.mcp_agent import MCPAgent
from agents.agentic_loop import AgenticLoop
from agents.orchestrator import OrchestratorAgent


class TestRemoteMCPProtocol(unittest.TestCase):
    """Test suite for standards-compliant remote MCP protocol execution."""

    def setUp(self) -> None:
        self.weather_script = "src/mcp_tools/weather_tools.py"
        self.commute_script = "src/mcp_tools/commute_tools.py"

    def test_remote_client_handshake_and_discovery(self) -> None:
        """1. Verify initialization handshake and tool discovery over stdio transport."""
        client = RemoteMCPClient(name="weather-server", script_path=self.weather_script)
        try:
            health = client.connect()
            self.assertTrue(client.is_connected)
            self.assertEqual(health["server"], "weather-server")
            self.assertEqual(health["status"], "ok")

            tools = client.list_tools()
            self.assertIn("get_weather", tools)
            self.assertTrue(client.has_tool("get_weather"))
        finally:
            client.close()
            self.assertFalse(client.is_connected)

    def test_remote_tool_invocation_structured(self) -> None:
        """2. Verify dynamic tool invocation and structured result parsing over stdio."""
        client = RemoteMCPClient(name="weather-server", script_path=self.weather_script)
        try:
            client.connect()
            result = client.invoke("get_weather", location="Chicago")
            self.assertIsInstance(result, dict)
            self.assertIn("temperature", result)
            self.assertIn("source", result)
        finally:
            client.close()

    def test_remote_tool_invalid_name(self) -> None:
        """3. Verify error handling when calling invalid/non-existent tool over stdio."""
        client = RemoteMCPClient(name="weather-server", script_path=self.weather_script)
        try:
            client.connect()
            with self.assertRaises(RuntimeError):
                client.invoke("non_existent_tool_name")
        finally:
            client.close()

    def test_remote_connection_failure(self) -> None:
        """4. Verify connection failure handling when target script does not exist."""
        client = RemoteMCPClient(name="invalid-server", script_path="src/mcp_tools/non_existent_file.py")
        with self.assertRaises(ConnectionError):
            client.connect()

    def test_mcp_agent_remote_wrapper(self) -> None:
        """5. Verify MCPAgent wrapping RemoteMCPClient correctly."""
        client = RemoteMCPClient(name="weather-server", script_path=self.weather_script)
        agent = MCPAgent("weather", client)
        try:
            handshake = agent.connect()
            self.assertTrue(agent.is_connected)
            self.assertIn("get_weather", agent.list_tools())
            
            res = agent.invoke("get_weather", location="London")
            self.assertIsInstance(res, dict)
            self.assertIn("temperature", res)
        finally:
            agent.close()

    def test_mcp_client_manager_remote_mode(self) -> None:
        """6. Verify MCPClientManager pools and dispatches remote stdio clients."""
        manager = MCPClientManager(mcp_mode="remote")
        try:
            client = manager.get_client("weather")
            self.assertIsInstance(client, RemoteMCPClient)
            
            tools = manager.list_tools("weather")
            self.assertIn("get_weather", tools)

            res = manager.call_tool("weather", "get_weather", location="Paris")
            self.assertIsInstance(res, dict)
            self.assertIn("temperature", res)
        finally:
            manager.close_all()

    def test_mcp_client_manager_in_process_mode(self) -> None:
        """7. Verify MCPClientManager backwards compatibility in in_process mode."""
        manager = MCPClientManager(mcp_mode="in_process")
        tools = manager.list_tools("weather")
        self.assertIn("get_weather", tools)

        res = manager.call_tool("weather", "get_weather", location="Tokyo")
        self.assertIsInstance(res, dict)
        self.assertIn("temperature", res)

    def test_agentic_loop_remote_mode(self) -> None:
        """8. Verify full AgenticLoop execution over remote stdio MCP protocol clients."""
        manager = MCPClientManager(mcp_mode="remote")
        loop = AgenticLoop(server_registry=manager)
        try:
            result = loop.run("Weather in Berlin")
            self.assertIn("weather", result.sections)
            self.assertEqual(result.sections["weather"]["status"], "success")
            self.assertIn("Berlin", result.summary)
        finally:
            manager.close_all()

    def test_orchestrator_agent_close_lifecycle(self) -> None:
        """9. Verify OrchestratorAgent closes client manager cleanly."""
        orchestrator = OrchestratorAgent()
        try:
            res = orchestrator.run("Weather in Rome")
            self.assertIn("Rome", res)
        finally:
            orchestrator.close()


if __name__ == "__main__":
    unittest.main()

from typing import Dict, List

from mcp_tools.real_mcp_server import RealMCPServer


class ServerRegistry:
    def __init__(self) -> None:
        self.servers: Dict[str, RealMCPServer] = {}

    def register(self, name: str, server: RealMCPServer) -> None:
        self.servers[name] = server

    def list_servers(self) -> List[str]:
        return list(self.servers.keys())

    def get_server(self, name: str) -> RealMCPServer:
        return self.servers[name]

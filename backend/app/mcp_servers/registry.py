"""MCP Server Registry — manages all registered MCP servers."""

from typing import Dict, Optional, Any
from app.mcp_servers.base import MCPServer, MCPRequest, MCPResponse
from app.mcp_servers.slack_server import create_slack_server
from app.mcp_servers.github_server import create_github_server
from app.mcp_servers.sap_server import create_sap_server


class MCPRegistry:
    def __init__(self):
        self._servers: Dict[str, MCPServer] = {}

    def register(self, server: MCPServer):
        self._servers[server.name] = server

    def get(self, name: str) -> Optional[MCPServer]:
        return self._servers.get(name)

    def list(self) -> list[dict]:
        return [
            {"name": s.name, "version": s.version, "tools": list(s.tools.keys())}
            for s in self._servers.values()
        ]

    async def handle(self, server_name: str, request: MCPRequest) -> MCPResponse:
        server = self._servers.get(server_name)
        if not server:
            return MCPResponse(success=False, error=f"Server not found: {server_name}")
        return await server.handle(request)


mcp_registry = MCPRegistry()
mcp_registry.register(create_slack_server())
mcp_registry.register(create_github_server())
mcp_registry.register(create_sap_server())

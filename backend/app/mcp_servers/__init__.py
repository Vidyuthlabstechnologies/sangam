"""MCP (Model Context Protocol) server starters for enterprise integration.

Each MCP server follows the stateless 2026 spec:
- Plain HTTP, no WebSocket requirement
- Scale horizontally
- Single responsibility per server
"""

from app.mcp_servers.base import MCPServer, MCPTool, MCPRequest, MCPResponse

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import json


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable


@dataclass
class MCPRequest:
    tool: str
    params: Dict[str, Any]


@dataclass
class MCPResponse:
    success: bool
    data: Any = None
    error: Optional[str] = None


class MCPServer:
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.tools: Dict[str, MCPTool] = {}

    def register(self, tool: MCPTool):
        self.tools[tool.name] = tool

    async def handle(self, request: MCPRequest) -> MCPResponse:
        tool = self.tools.get(request.tool)
        if not tool:
            return MCPResponse(success=False, error=f"Unknown tool: {request.tool}")
        try:
            result = await tool.handler(**request.params)
            return MCPResponse(success=True, data=result)
        except Exception as e:
            return MCPResponse(success=False, error=str(e))

    def manifest(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "protocol": "mcp-2026",
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in self.tools.values()
            ],
        }

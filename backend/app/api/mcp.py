from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.models.actor import Actor
from app.mcp_servers.registry import mcp_registry
from app.mcp_servers.base import MCPRequest
from app.api.dependencies import get_current_actor

router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPExecuteRequest(BaseModel):
    server: str
    tool: str
    params: dict = {}


class MCPResponseModel(BaseModel):
    success: bool
    data: dict | None = None
    error: str | None = None


@router.get("/servers", response_model=list[dict])
async def list_servers(
    current_actor: Actor = Depends(get_current_actor),
):
    return mcp_registry.list()


@router.get("/servers/{server_name}/manifest", response_model=dict)
async def get_manifest(
    server_name: str,
    current_actor: Actor = Depends(get_current_actor),
):
    server = mcp_registry.get(server_name)
    if not server:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found")
    return server.manifest()


@router.post("/execute", response_model=MCPResponseModel)
async def execute_tool(
    req: MCPExecuteRequest,
    current_actor: Actor = Depends(get_current_actor),
):
    mcp_req = MCPRequest(tool=req.tool, params=req.params)
    response = await mcp_registry.handle(req.server, mcp_req)
    return MCPResponseModel(
        success=response.success,
        data=response.data if response.success else None,
        error=response.error,
    )

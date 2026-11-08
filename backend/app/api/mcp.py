from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.models.actor import Actor, Permission
from app.mcp_servers.registry import mcp_registry
from app.mcp_servers.base import MCPRequest
from app.api.dependencies import get_current_actor
from app.core.access import is_admin, permission_values

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
    allowed = permission_values(current_actor)
    if not is_admin(current_actor) and Permission.EXECUTE.value not in allowed and Permission.CONFIGURE_INTEGRATIONS.value not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP execute requires the execute or configure:integrations permission",
        )
    params = dict(req.params or {})
    # Platform tools are global integrations. Never let the body aim them at another tenant.
    if "tenant_id" in params and str(params["tenant_id"]) != str(current_actor.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot execute MCP for another tenant")
    params["actor_id"] = str(current_actor.id)
    mcp_req = MCPRequest(tool=req.tool, params=params)
    response = await mcp_registry.handle(req.server, mcp_req)
    return MCPResponseModel(
        success=response.success,
        data=response.data if response.success else None,
        error=response.error,
    )

"""MCP Server: Slack Integration

Connects Sangam workflows to Slack channels for notifications, approvals, and updates.
"""

from typing import Any, Optional
import httpx

from app.mcp_servers.base import MCPServer, MCPTool


def create_slack_server(webhook_url: Optional[str] = None) -> MCPServer:
    server = MCPServer(name="slack", version="1.0.0")

    async def send_message(channel: str, text: str, blocks: Optional[list] = None):
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                webhook_url or "https://slack.com/api/chat.postMessage",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    async def notify_approval(approval_id: str, workflow_name: str, channel: str):
        return await send_message(
            channel=channel,
            text=f"*Approval Required*: {workflow_name}",
            blocks=[
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": f"*Approval Required*\nWorkflow: *{workflow_name}*"}},
                {"type": "actions", "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Approve"},
                     "style": "primary", "value": f"approve:{approval_id}"},
                    {"type": "button", "text": {"type": "plain_text", "text": "Reject"},
                     "style": "danger", "value": f"reject:{approval_id}"},
                ]},
            ],
        )

    server.register(MCPTool(
        name="send_message",
        description="Send a message to a Slack channel",
        input_schema={
            "type": "object",
            "properties": {
                "channel": {"type": "string"},
                "text": {"type": "string"},
                "blocks": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["channel", "text"],
        },
        handler=send_message,
    ))

    server.register(MCPTool(
        name="notify_approval",
        description="Send an approval notification with Approve/Reject buttons",
        input_schema={
            "type": "object",
            "properties": {
                "approval_id": {"type": "string"},
                "workflow_name": {"type": "string"},
                "channel": {"type": "string"},
            },
            "required": ["approval_id", "workflow_name", "channel"],
        },
        handler=notify_approval,
    ))

    return server

"""MCP Server: GitHub Integration

Connects Sangam workflows to GitHub for issue tracking, PR reviews, and CI checks.
"""

from typing import Optional
import httpx
import os

from app.mcp_servers.base import MCPServer, MCPTool


def create_github_server(token: Optional[str] = None) -> MCPServer:
    server = MCPServer(name="github", version="1.0.0")
    gh_token = token or os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async def create_issue(repo: str, title: str, body: str, labels: Optional[list] = None):
        async with httpx.AsyncClient(headers=headers) as client:
            payload = {"title": title, "body": body}
            if labels:
                payload["labels"] = labels
            resp = await client.post(
                f"https://api.github.com/repos/{repo}/issues", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return {"issue_number": data["number"], "html_url": data["html_url"]}

    async def create_pr(repo: str, title: str, head: str, base: str, body: Optional[str] = None):
        async with httpx.AsyncClient(headers=headers) as client:
            payload = {"title": title, "head": head, "base": base}
            if body:
                payload["body"] = body
            resp = await client.post(
                f"https://api.github.com/repos/{repo}/pulls", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return {"pr_number": data["number"], "html_url": data["html_url"]}

    async def list_open_prs(repo: str):
        async with httpx.AsyncClient(headers=headers) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/pulls?state=open"
            )
            resp.raise_for_status()
            prs = resp.json()
            return [
                {"number": p["number"], "title": p["title"], "html_url": p["html_url"]}
                for p in prs
            ]

    server.register(MCPTool(
        name="create_issue",
        description="Create a GitHub issue in a repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo format"},
                "title": {"type": "string"},
                "body": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["repo", "title", "body"],
        },
        handler=create_issue,
    ))

    server.register(MCPTool(
        name="create_pr",
        description="Create a pull request on GitHub",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "title": {"type": "string"},
                "head": {"type": "string"},
                "base": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["repo", "title", "head", "base"],
        },
        handler=create_pr,
    ))

    server.register(MCPTool(
        name="list_open_prs",
        description="List all open pull requests for a repository",
        input_schema={
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
            },
            "required": ["repo"],
        },
        handler=list_open_prs,
    ))

    return server

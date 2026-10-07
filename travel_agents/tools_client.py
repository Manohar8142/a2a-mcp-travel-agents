"""Clients agents use to call MCP tools.

* ``InProcessMCPClient`` calls the FastMCP server object directly (same MCP tool layer:
  schema validation, serialization) without a subprocess. Default for demos and tests.
* ``StdioMCPClient`` launches the server as a subprocess and talks real MCP over stdio
  using ``mcp.ClientSession``.
"""
from __future__ import annotations

import json
import sys
from contextlib import AsyncExitStack
from typing import Any, Protocol


class ToolClient(Protocol):
    async def call(self, name: str, arguments: dict[str, Any]) -> dict: ...
    async def list_tools(self) -> list[str]: ...


def _content_to_dict(content: Any) -> dict:
    if isinstance(content, tuple):  # newer SDKs return (content_blocks, structured)
        structured = content[1]
        if isinstance(structured, dict):
            return structured.get("result", structured) if set(structured) == {"result"} else structured
        content = content[0]
    if isinstance(content, dict):
        return content
    text = "".join(getattr(block, "text", "") for block in content)
    return json.loads(text) if text else {}


class InProcessMCPClient:
    def __init__(self) -> None:
        from .mcp_server import mcp

        self._server = mcp

    async def call(self, name: str, arguments: dict[str, Any]) -> dict:
        return _content_to_dict(await self._server.call_tool(name, arguments))

    async def list_tools(self) -> list[str]:
        return [t.name for t in await self._server.list_tools()]


class StdioMCPClient:
    """Use as ``async with StdioMCPClient() as client: ...``."""

    def __init__(self, command: str = sys.executable, args: list[str] | None = None) -> None:
        self.command = command
        self.args = args or ["-m", "travel_agents.mcp_server"]
        self._stack: AsyncExitStack | None = None
        self.session = None

    async def __aenter__(self) -> "StdioMCPClient":
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._stack = AsyncExitStack()
        params = StdioServerParameters(command=self.command, args=self.args)
        read, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._stack:
            await self._stack.aclose()

    async def call(self, name: str, arguments: dict[str, Any]) -> dict:
        result = await self.session.call_tool(name, arguments)
        if getattr(result, "structuredContent", None):
            sc = result.structuredContent
            return sc.get("result", sc) if set(sc) == {"result"} else sc
        return _content_to_dict(result.content)

    async def list_tools(self) -> list[str]:
        return [t.name for t in (await self.session.list_tools()).tools]

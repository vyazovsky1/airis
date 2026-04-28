"""MCP server connection manager — discovers tools and routes calls."""

import json
import logging
import os
from contextlib import AsyncExitStack
from typing import Any
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages one or more MCP server connections and exposes their tools."""

    def __init__(self, servers_config: dict):
        self._config = servers_config
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        # openai_tool_name -> (server_name, original_mcp_name)
        self._tool_map: dict[str, tuple[str, str]] = {}
        self.openai_tools: list[dict] = []

    async def __aenter__(self) -> "MCPManager":
        await self._exit_stack.__aenter__()
        for name, cfg in self._config.get("mcpServers", {}).items():
            if name.startswith("_"):
                continue
            await self._connect(name, cfg)
        return self

    async def __aexit__(self, *exc) -> None:
        await self._exit_stack.__aexit__(*exc)

    async def _connect(self, name: str, cfg: dict) -> None:
        try:
            env = {**os.environ, **cfg.get("env", {})}
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=env,
            )
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(params, errlog=sys.stderr)
            )
            session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self._sessions[name] = session
            logger.info("Connected to MCP server '%s'", name)
            await self._register_tools(name, session)
        except Exception as exc:
            logger.warning("Could not connect to MCP server '%s': %s", name, exc)

    async def _register_tools(self, server_name: str, session: ClientSession) -> None:
        result = await session.list_tools()
        for tool in result.tools:
            # OpenAI tool names: max 64 chars, pattern ^[a-zA-Z0-9_-]+$
            safe_name = f"{server_name}__{tool.name}".replace("-", "_")[:64]
            self._tool_map[safe_name] = (server_name, tool.name)
            self.openai_tools.append({
                "type": "function",
                "function": {
                    "name": safe_name,
                    "description": (tool.description or "").strip(),
                    "parameters": tool.inputSchema or {
                        "type": "object",
                        "properties": {},
                    },
                },
            })
        logger.info(
            "Registered %d tool(s) from '%s'", len(result.tools), server_name
        )

    async def call_tool(self, openai_name: str, arguments: dict[str, Any]) -> str:
        if openai_name not in self._tool_map:
            return f"Error: unknown tool '{openai_name}'"

        server_name, mcp_name = self._tool_map[openai_name]
        session = self._sessions.get(server_name)
        if session is None:
            return f"Error: server '{server_name}' is not connected"

        try:
            logger.debug("Calling %s/%s with %s", server_name, mcp_name, arguments)
            result = await session.call_tool(mcp_name, arguments=arguments)
            parts: list[str] = []
            for item in result.content:
                if hasattr(item, "text"):
                    parts.append(item.text)
                elif hasattr(item, "data"):
                    parts.append(f"[binary data, {len(item.data)} bytes]")
                else:
                    parts.append(str(item))
            return "\n".join(parts) if parts else "(empty response)"
        except Exception as exc:
            logger.error("Tool '%s' raised: %s", openai_name, exc)
            return f"Tool error: {exc}"

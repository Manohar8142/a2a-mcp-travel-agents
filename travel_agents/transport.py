"""How agents reach each other: in-process (default) or over HTTP."""
from __future__ import annotations

from typing import Protocol

import httpx

from .protocol import AgentCard, Task, jsonrpc_request


class Transport(Protocol):
    async def send(self, card: AgentCard, task: Task) -> Task: ...


class InProcessTransport:
    """Routes JSON-RPC envelopes to local agent objects.

    Every task is serialised to JSON and parsed back, so agents only ever share the
    wire protocol, exactly as they would across processes.
    """

    def __init__(self) -> None:
        self._agents: dict[str, object] = {}

    def register(self, agent) -> None:
        self._agents[agent.card.url] = agent

    async def send(self, card: AgentCard, task: Task) -> Task:
        request = jsonrpc_request(task)
        agent = self._agents[card.url]
        response = await agent.handle_jsonrpc(request)
        if "error" in response:
            raise RuntimeError(response["error"]["message"])
        return Task.model_validate(response["result"])


class HttpTransport:
    """POSTs JSON-RPC ``tasks/send`` to the agent's card URL (see ``travel_agents.server``)."""

    def __init__(self, timeout: float = 60.0) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)

    async def send(self, card: AgentCard, task: Task) -> Task:
        resp = await self._client.post(card.url, json=jsonrpc_request(task))
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(body["error"]["message"])
        return Task.model_validate(body["result"])

    @staticmethod
    async def discover(base_url: str) -> AgentCard:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base_url.rstrip('/')}/.well-known/agent.json")
            r.raise_for_status()
            return AgentCard.model_validate(r.json())

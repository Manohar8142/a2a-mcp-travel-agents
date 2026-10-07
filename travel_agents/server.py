"""Serve every agent over HTTP as an A2A endpoint.

    uvicorn travel_agents.server:app --port 8080

    GET  /agents/{name}/.well-known/agent.json   agent card
    POST /agents/{name}                          JSON-RPC tasks/send
    POST /plan  {"text": "..."}                  convenience entry to the orchestrator
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .agents import BookingAgent, FlightAgent, HotelAgent, Orchestrator
from .llm import get_llm
from .tools_client import InProcessMCPClient
from .transport import HttpTransport

BASE = os.getenv("A2A_BASE_URL", "http://localhost:8080")


class PlanIn(BaseModel):
    text: str


def create_app() -> FastAPI:
    tools = InProcessMCPClient()
    specialists = [
        FlightAgent(tools, f"{BASE}/agents/flight-agent"),
        HotelAgent(tools, f"{BASE}/agents/hotel-agent"),
        BookingAgent(tools, f"{BASE}/agents/booking-agent"),
    ]
    orchestrator = Orchestrator(get_llm(), HttpTransport(), [a.card for a in specialists], f"{BASE}/agents/travel-orchestrator")
    agents = {a.card.name: a for a in [*specialists, orchestrator]}
    app = FastAPI(title="A2A + MCP travel agents")

    def get(name: str):
        if name not in agents:
            raise HTTPException(404, f"unknown agent {name}")
        return agents[name]

    @app.get("/agents")
    def directory() -> list[dict]:
        return [a.card.model_dump() for a in agents.values()]

    @app.get("/agents/{name}/.well-known/agent.json")
    def card(name: str) -> dict:
        return get(name).card.model_dump()

    @app.post("/agents/{name}")
    async def rpc(name: str, request: Request) -> dict:
        return await get(name).handle_jsonrpc(await request.json())

    @app.post("/plan")
    async def plan(body: PlanIn) -> dict:
        p = await orchestrator.plan(body.text)
        return {"summary": p.summary, "needs_input": p.needs_input, "flight": p.flight, "hotel": p.hotel, "booking": p.booking, "trace": p.trace}

    return app


app = create_app()

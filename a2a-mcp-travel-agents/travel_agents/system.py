"""Wire the agents together."""
from __future__ import annotations

from .agents import BookingAgent, FlightAgent, HotelAgent, Orchestrator
from .llm import LLM, get_llm
from .tools_client import InProcessMCPClient, ToolClient
from .transport import InProcessTransport


def build_system(llm: LLM | None = None, tools: ToolClient | None = None) -> Orchestrator:
    tools = tools or InProcessMCPClient()
    transport = InProcessTransport()
    specialists = [FlightAgent(tools), HotelAgent(tools), BookingAgent(tools)]
    for agent in specialists:
        transport.register(agent)
    return Orchestrator(llm or get_llm(), transport, [a.card for a in specialists])

import asyncio

from fastapi.testclient import TestClient

from travel_agents.llm import MockLLM
from travel_agents.protocol import Message, Part, Task, TaskState, jsonrpc_request
from travel_agents.system import build_system
from travel_agents.tools_client import InProcessMCPClient, StdioMCPClient

REQ = "Plan a trip from Hyderabad to Goa on 2026-11-20 for 3 nights, 2 travelers, hotel under 100. My name is Asha Rao. Book it."


def test_mcp_tools_registered():
    tools = asyncio.run(InProcessMCPClient().list_tools())
    assert {"search_flights", "search_hotels", "create_booking", "get_booking"} <= set(tools)


def test_end_to_end_plan_and_book():
    plan = asyncio.run(build_system(MockLLM()).plan(REQ))
    assert plan.flight["origin"] == "HYD" and plan.flight["destination"] == "GOI"
    assert plan.hotel["price_per_night_usd"] <= 100
    assert plan.booking["status"] == "confirmed" and plan.booking["traveler_name"] == "Asha Rao"
    assert any("booking-agent" in t for t in plan.trace)
    assert plan.booking["booking_id"] in plan.summary


def test_booking_without_name_requires_input():
    plan = asyncio.run(build_system(MockLLM()).plan("from Delhi to Mumbai on 2026-12-01, 1 night, book it"))
    assert plan.booking is None and "traveler_name" in plan.needs_input


def test_jsonrpc_roundtrip_and_errors():
    orch = build_system(MockLLM())
    flight_card = orch.find("flight-search")
    agent = orch.transport._agents[flight_card.url]
    task = Task(skill="flight-search", history=[Message(role="user", parts=[Part.of_data({"origin": "chennai", "destination": "kochi", "depart_date": "2026-11-02"})])])
    resp = asyncio.run(agent.handle_jsonrpc(jsonrpc_request(task)))
    assert Task.model_validate(resp["result"]).state == TaskState.completed
    bad = asyncio.run(agent.handle_jsonrpc({"jsonrpc": "2.0", "id": "1", "method": "tasks/cancel", "params": {}}))
    assert bad["error"]["code"] == -32601


def test_http_server_cards():
    from travel_agents.server import app

    client = TestClient(app)
    card = client.get("/agents/hotel-agent/.well-known/agent.json").json()
    assert card["skills"][0]["id"] == "hotel-search"


def test_real_mcp_stdio_transport():
    async def go():
        async with StdioMCPClient() as tools:
            res = await tools.call("search_hotels", {"city": "goa", "nights": 2})
            return res

    res = asyncio.run(go())
    assert res["options"] and res["options"][0]["city"] == "GOI"

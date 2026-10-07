from __future__ import annotations

from ..protocol import AgentCard, AgentSkill, Task, TaskState
from ..tools_client import ToolClient
from .base import BaseAgent


class FlightAgent(BaseAgent):
    def __init__(self, tools: ToolClient, url: str = "local://flight-agent") -> None:
        self.tools = tools
        self.card = AgentCard(
            name="flight-agent",
            description="Finds one-way flights between Indian cities via the travel MCP server.",
            url=url,
            skills=[AgentSkill(id="flight-search", name="Flight search", description="Search flights by route, date and party size", tags=["flights"])],
        )

    async def run(self, task: Task) -> None:
        q = self.request_data(task)
        missing = [k for k in ("origin", "destination", "depart_date") if not q.get(k)]
        if missing:
            task.state, task.error = TaskState.input_required, f"missing: {', '.join(missing)}"
            return
        result = await self.tools.call(
            "search_flights",
            {"origin": q["origin"], "destination": q["destination"], "date": q["depart_date"], "travelers": q.get("travelers", 1)},
        )
        options = result.get("options", [])
        if not options:
            task.state, task.error = TaskState.failed, f"no flights {q['origin']} -> {q['destination']}"
            return
        self.reply(task, "flight-options", {"options": options, "recommended": options[0]},
                   f"{len(options)} flights found; cheapest {options[0]['airline']} at ${options[0]['price_usd']}.")

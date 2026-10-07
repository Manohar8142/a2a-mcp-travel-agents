from __future__ import annotations

from ..protocol import AgentCard, AgentSkill, Task, TaskState
from ..tools_client import ToolClient
from .base import BaseAgent


class HotelAgent(BaseAgent):
    def __init__(self, tools: ToolClient, url: str = "local://hotel-agent") -> None:
        self.tools = tools
        self.card = AgentCard(
            name="hotel-agent",
            description="Finds hotels by city, nights, guests and nightly budget via the travel MCP server.",
            url=url,
            skills=[AgentSkill(id="hotel-search", name="Hotel search", description="Search hotels, best rated within budget", tags=["hotels"])],
        )

    async def run(self, task: Task) -> None:
        q = self.request_data(task)
        if not q.get("destination"):
            task.state, task.error = TaskState.input_required, "missing: destination"
            return
        args = {"city": q["destination"], "nights": q.get("nights", 1), "guests": q.get("travelers", 1)}
        if q.get("max_hotel_price"):
            args["max_price_per_night"] = q["max_hotel_price"]
        options = (await self.tools.call("search_hotels", args)).get("options", [])
        if not options:
            task.state, task.error = TaskState.failed, f"no hotels in {q['destination']} within budget"
            return
        best = options[0]
        self.reply(task, "hotel-options", {"options": options, "recommended": best},
                   f"{len(options)} hotels found; recommending {best['name']} ({best['rating']}*, ${best['price_per_night_usd']}/night).")

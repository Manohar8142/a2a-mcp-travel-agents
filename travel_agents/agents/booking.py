from __future__ import annotations

from ..protocol import AgentCard, AgentSkill, Task, TaskState
from ..tools_client import ToolClient
from .base import BaseAgent


class BookingAgent(BaseAgent):
    def __init__(self, tools: ToolClient, url: str = "local://booking-agent") -> None:
        self.tools = tools
        self.card = AgentCard(
            name="booking-agent",
            description="Books a selected flight and hotel together and returns a confirmation.",
            url=url,
            skills=[AgentSkill(id="booking", name="Trip booking", description="Create a combined flight + hotel booking", tags=["booking"])],
        )

    async def run(self, task: Task) -> None:
        q = self.request_data(task)
        if not q.get("traveler_name"):
            task.state, task.error = TaskState.input_required, "traveler_name is required to book"
            return
        result = await self.tools.call(
            "create_booking",
            {"traveler_name": q["traveler_name"], "flight_id": q["flight_id"], "hotel_id": q["hotel_id"],
             "nights": q.get("nights", 1), "travelers": q.get("travelers", 1)},
        )
        if not result.get("ok"):
            task.state, task.error = TaskState.failed, result.get("error", "booking failed")
            return
        self.reply(task, "booking-confirmation", result, f"Booked {result['booking_id']} for ${result['total_usd']}.")

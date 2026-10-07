"""The orchestrator: understands the request, discovers specialists by skill, delegates, composes."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ..llm import LLM
from ..protocol import AgentCard, AgentSkill, Message, Part, Task, TaskState
from ..transport import Transport
from .base import BaseAgent


@dataclass
class TripPlan:
    request: dict[str, Any]
    flight: dict | None = None
    hotel: dict | None = None
    booking: dict | None = None
    summary: str = ""
    trace: list[str] = field(default_factory=list)
    needs_input: str | None = None


class Orchestrator(BaseAgent):
    def __init__(self, llm: LLM, transport: Transport, directory: list[AgentCard], url: str = "local://orchestrator") -> None:
        self.llm = llm
        self.transport = transport
        self.directory = directory
        self.card = AgentCard(
            name="travel-orchestrator",
            description="Plans and books trips by delegating to flight, hotel and booking agents.",
            url=url,
            skills=[AgentSkill(id="plan-trip", name="Plan trip", description="Plan (and optionally book) a trip from natural language")],
        )

    def find(self, skill_id: str) -> AgentCard:
        for card in self.directory:
            if any(s.id == skill_id for s in card.skills):
                return card
        raise LookupError(f"no agent offers skill {skill_id!r}")

    async def delegate(self, skill_id: str, data: dict[str, Any], plan: TripPlan) -> Task:
        card = self.find(skill_id)
        task = Task(skill=skill_id, history=[Message(role="user", parts=[Part.of_data(data)])])
        plan.trace.append(f"orchestrator -> {card.name} [{skill_id}]")
        done = await self.transport.send(card, task)
        note = done.history[-1].text() if done.history and done.history[-1].role == "agent" else (done.error or "")
        plan.trace.append(f"{card.name} -> orchestrator [{done.state.value}] {note}")
        return done

    async def plan(self, text: str) -> TripPlan:
        req = self.llm.extract(text)
        plan = TripPlan(request=req)
        if not req.get("origin") or not req.get("destination"):
            plan.needs_input = "Where are you flying from and to? e.g. 'from Hyderabad to Goa'."
            return plan

        flights_task, hotels_task = await asyncio.gather(
            self.delegate("flight-search", req, plan), self.delegate("hotel-search", req, plan)
        )
        for t in (flights_task, hotels_task):
            if t.state != TaskState.completed:
                plan.needs_input = t.error
                return plan
        plan.flight = flights_task.artifact_data("flight-options")["recommended"]
        plan.hotel = hotels_task.artifact_data("hotel-options")["recommended"]

        if req.get("book"):
            booking_task = await self.delegate(
                "booking",
                {**req, "flight_id": plan.flight["flight_id"], "hotel_id": plan.hotel["hotel_id"]},
                plan,
            )
            if booking_task.state == TaskState.completed:
                plan.booking = booking_task.artifact_data("booking-confirmation")
            else:
                plan.needs_input = booking_task.error

        plan.summary = self.llm.write(self._summary_prompt(plan))
        return plan

    @staticmethod
    def _summary_prompt(plan: TripPlan) -> str:
        r, f, h = plan.request, plan.flight, plan.hotel
        lines = [
            f"Trip: {r['origin'].title()} -> {r['destination'].title()}, {r['depart_date']}, {r['nights']} night(s), {r['travelers']} traveller(s).",
            f"Flight: {f['airline']} {f['flight_id'].split('-')[0]} departs {f['departure']}, {f['duration_min']} min, ${f['price_usd']} per person.",
            f"Hotel: {h['name']} ({h['rating']}*), ${h['price_per_night_usd']}/night, ${h['total_usd']} total.",
        ]
        if plan.booking:
            lines.append(f"Booked: {plan.booking['booking_id']} for {plan.booking['traveler_name']}, total ${plan.booking['total_usd']}.")
        elif plan.needs_input:
            lines.append(f"Not booked yet: {plan.needs_input}.")
        else:
            lines.append("Say 'book it' with the traveller's name to confirm.")
        draft = "\n".join(lines)
        return f"Rewrite this trip plan as a short friendly summary. Keep every number exact.\nDRAFT:\n{draft}"

    # Exposed over A2A too, so another orchestrator could call this one.
    async def run(self, task: Task) -> None:
        plan = await self.plan(task.history[-1].text())
        data = {"request": plan.request, "flight": plan.flight, "hotel": plan.hotel, "booking": plan.booking, "trace": plan.trace}
        self.reply(task, "trip-plan", data, plan.summary or plan.needs_input or "")
        if plan.needs_input and not plan.booking and not plan.flight:
            task.state = TaskState.input_required

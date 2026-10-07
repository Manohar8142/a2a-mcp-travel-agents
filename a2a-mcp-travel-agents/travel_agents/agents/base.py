"""Common A2A server behaviour for every agent."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from ..protocol import AgentCard, Artifact, Message, Part, Task, TaskState, jsonrpc_error, jsonrpc_result

log = logging.getLogger("travel_agents")


class BaseAgent(ABC):
    card: AgentCard

    async def handle_jsonrpc(self, request: dict[str, Any]) -> dict[str, Any]:
        rid = request.get("id")
        if request.get("method") != "tasks/send":
            return jsonrpc_error(rid, -32601, f"Method not found: {request.get('method')}")
        try:
            task = Task.model_validate(request["params"])
        except Exception as exc:  # malformed params
            return jsonrpc_error(rid, -32602, f"Invalid params: {exc}")
        return jsonrpc_result(rid, await self.handle_task(task))

    async def handle_task(self, task: Task) -> Task:
        task.state = TaskState.working
        log.info("%s <- task %s skill=%s", self.card.name, task.id[:8], task.skill)
        try:
            await self.run(task)
            if task.state == TaskState.working:
                task.state = TaskState.completed
        except Exception as exc:
            task.state, task.error = TaskState.failed, str(exc)
        log.info("%s -> task %s %s", self.card.name, task.id[:8], task.state.value)
        return task

    @abstractmethod
    async def run(self, task: Task) -> None: ...

    @staticmethod
    def request_data(task: Task) -> dict[str, Any]:
        return task.history[-1].data() if task.history else {}

    def reply(self, task: Task, name: str, data: dict[str, Any], text: str) -> None:
        task.artifacts.append(Artifact(name=name, parts=[Part.of_data(data)]))
        task.history.append(Message(role="agent", parts=[Part.of_text(text)]))

"""A2A-style protocol objects (modelled on Google's Agent2Agent spec, simplified).

* ``AgentCard`` describes an agent and its skills, published at ``/.well-known/agent.json``.
* ``Task`` is the unit of delegated work, with a lifecycle state, message history and artifacts.
* Messages are made of ``parts``: ``{"type": "text", "text": ...}`` or ``{"type": "data", "data": {...}}``.
* Requests travel as JSON-RPC 2.0 ``tasks/send`` calls.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    submitted = "submitted"
    working = "working"
    input_required = "input-required"
    completed = "completed"
    failed = "failed"


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = []


class AgentCard(BaseModel):
    name: str
    description: str
    url: str
    version: str = "0.1.0"
    capabilities: dict[str, bool] = {"streaming": False, "pushNotifications": False}
    defaultInputModes: list[str] = ["text", "data"]
    defaultOutputModes: list[str] = ["text", "data"]
    skills: list[AgentSkill]


class Part(BaseModel):
    type: Literal["text", "data"]
    text: str | None = None
    data: dict[str, Any] | None = None

    @classmethod
    def of_text(cls, text: str) -> "Part":
        return cls(type="text", text=text)

    @classmethod
    def of_data(cls, data: dict[str, Any]) -> "Part":
        return cls(type="data", data=data)


class Message(BaseModel):
    role: Literal["user", "agent"]
    parts: list[Part]

    def data(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for p in self.parts:
            if p.type == "data" and p.data:
                merged.update(p.data)
        return merged

    def text(self) -> str:
        return "\n".join(p.text for p in self.parts if p.type == "text" and p.text)


class Artifact(BaseModel):
    name: str
    parts: list[Part]


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    skill: str | None = None
    state: TaskState = TaskState.submitted
    history: list[Message] = []
    artifacts: list[Artifact] = []
    error: str | None = None

    def artifact_data(self, name: str | None = None) -> dict[str, Any]:
        for a in self.artifacts:
            if name is None or a.name == name:
                for p in a.parts:
                    if p.type == "data" and p.data is not None:
                        return p.data
        return {}


def jsonrpc_request(task: Task) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "tasks/send", "params": task.model_dump(mode="json")}


def jsonrpc_result(request_id: str, task: Task) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": task.model_dump(mode="json")}


def jsonrpc_error(request_id: str | None, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

"""Model client abstraction. Provider-agnostic tool-use interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from coding_tool.types import ToolCall, ToolResult, TurnUsage


@dataclass
class AssistantMessage:
    """A message produced by the model in one turn."""

    text: str  # free-form text (may be empty)
    tool_calls: list[ToolCall]
    usage: TurnUsage
    raw: Any = None  # provider-native representation for replay


@dataclass
class Transcript:
    """Provider-agnostic message log. Stored alongside provider-native messages."""

    system: str
    entries: list[dict[str, Any]] = field(default_factory=list)

    def add_user_text(self, text: str) -> None:
        self.entries.append({"role": "user", "content": text})

    def add_tool_results(self, results: list[ToolResult]) -> None:
        self.entries.append(
            {
                "role": "tool",
                "results": [
                    {"call_id": r.call_id, "status": r.status, "content": r.content}
                    for r in results
                ],
            }
        )

    def add_assistant(self, msg: AssistantMessage) -> None:
        self.entries.append(
            {
                "role": "assistant",
                "text": msg.text,
                "tool_calls": [
                    {"name": c.name, "arguments": c.arguments, "call_id": c.call_id}
                    for c in msg.tool_calls
                ],
                "usage": msg.usage.__dict__,
            }
        )


class ModelClient(ABC):
    """Provider-specific client.

    The client owns the provider-native message history (so it can pass it back
    in tool-use loops); the runner only manipulates a provider-agnostic
    Transcript for logging.
    """

    name: str  # short id used in run records (e.g. "claude-opus-4-7")

    @abstractmethod
    def reset(self, system: str) -> None:
        """Start a fresh conversation with the given system prompt."""

    @abstractmethod
    def add_user_text(self, text: str) -> None:
        """Append a user-role message."""

    @abstractmethod
    def add_tool_results(self, results: list[ToolResult]) -> None:
        """Append a batch of tool results (one user-role turn)."""

    @abstractmethod
    def step(self, tools: list[dict[str, Any]]) -> AssistantMessage:
        """Run one assistant turn with the given tool schemas."""


MODEL_REGISTRY: dict[str, type[ModelClient]] = {}


def register_model(cls: type[ModelClient]) -> type[ModelClient]:
    MODEL_REGISTRY[cls.name] = cls
    return cls

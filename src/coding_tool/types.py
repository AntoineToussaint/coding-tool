"""Shared dataclasses used across formats, models, and the bench runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


ToolCallStatus = Literal["ok", "error"]


@dataclass
class ToolCall:
    """A single tool invocation emitted by a model."""

    name: str
    arguments: dict[str, Any]
    call_id: str


@dataclass
class ToolResult:
    """Result of applying a single tool call against the working directory."""

    call_id: str
    status: ToolCallStatus
    content: str  # human/model-readable payload returned to the model
    diff: str | None = None  # optional unified diff of what changed on disk


@dataclass
class TurnUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


@dataclass
class RunRecord:
    """Outcome of running a single (task, model, format) trial."""

    task_id: str
    model: str
    edit_format: str
    passed: bool
    turns: int
    tool_calls: int
    invalid_tool_calls: int
    usage: TurnUsage
    latency_seconds: float
    oracle_stdout: str = ""
    oracle_stderr: str = ""
    error: str | None = None
    transcript_path: str | None = None


@dataclass
class TaskSpec:
    """A benchmark task fixture."""

    task_id: str
    language: Literal["python", "typescript"]
    category: str  # e.g. "rename", "move", "extract_method", "polyglot"
    fixture_dir: Path  # directory containing the starter files
    instructions: str
    oracle_cmd: list[str]  # command to run inside the workdir to verify
    files_in_context: list[str] = field(default_factory=list)  # file paths to show the model up-front

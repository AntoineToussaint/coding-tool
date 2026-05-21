"""Aggregate RunRecords into CSV and a markdown summary."""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

from coding_tool.types import RunRecord


CSV_COLUMNS = [
    "task_id",
    "model",
    "edit_format",
    "passed",
    "turns",
    "tool_calls",
    "invalid_tool_calls",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "latency_seconds",
    "error",
]


def write_csv(records: list[RunRecord], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in records:
            w.writerow(
                {
                    "task_id": r.task_id,
                    "model": r.model,
                    "edit_format": r.edit_format,
                    "passed": int(r.passed),
                    "turns": r.turns,
                    "tool_calls": r.tool_calls,
                    "invalid_tool_calls": r.invalid_tool_calls,
                    "input_tokens": r.usage.input_tokens,
                    "output_tokens": r.usage.output_tokens,
                    "cache_read_tokens": r.usage.cache_read_tokens,
                    "cache_creation_tokens": r.usage.cache_creation_tokens,
                    "latency_seconds": f"{r.latency_seconds:.3f}",
                    "error": r.error or "",
                }
            )


def summarize_markdown(records: list[RunRecord]) -> str:
    """Return a markdown table grouped by (model, format) showing pass-rate, mean tokens, invalid rate."""

    # group by (model, format)
    groups: dict[tuple[str, str], list[RunRecord]] = defaultdict(list)
    for r in records:
        groups[(r.model, r.edit_format)].append(r)

    lines = [
        "| model | format | n | pass@1 | invalid_tool/turn | mean_tokens | mean_latency (s) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for (model, fmt), rs in sorted(groups.items()):
        n = len(rs)
        pass_rate = sum(r.passed for r in rs) / n
        invalid_rate = (
            sum(r.invalid_tool_calls for r in rs) / max(sum(r.tool_calls for r in rs), 1)
        )
        mean_tokens = statistics.mean(
            r.usage.input_tokens + r.usage.output_tokens for r in rs
        )
        mean_latency = statistics.mean(r.latency_seconds for r in rs)
        lines.append(
            f"| {model} | {fmt} | {n} | {pass_rate:.1%} | {invalid_rate:.1%} | "
            f"{mean_tokens:,.0f} | {mean_latency:.1f} |"
        )

    # also per-task pass matrix
    tasks = sorted({r.task_id for r in records})
    fmts = sorted({r.edit_format for r in records})
    models = sorted({r.model for r in records})

    lines.append("\n## Pass matrix\n")
    lines.append("Each cell: pass-rate across formats for that (task, model).\n")
    head = "| task | " + " | ".join(models) + " |"
    sep = "|---|" + "|".join(["---:"] * len(models)) + "|"
    lines.append(head)
    lines.append(sep)
    for task in tasks:
        row = [task]
        for model in models:
            entries = [r for r in records if r.task_id == task and r.model == model]
            if not entries:
                row.append("—")
            else:
                pr = sum(e.passed for e in entries) / len(entries)
                row.append(f"{pr:.0%}")
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def write_markdown(records: list[RunRecord], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(summarize_markdown(records), encoding="utf-8")

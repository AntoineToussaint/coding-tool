# The single-shot tool-use ceiling

## TL;DR

For batched code-edit tasks, **the provider tool-use API forces a "~1 call per response" ceiling on the model**, even when the model knows it needs to emit N operations. Reframing the same operations as a **structured text document** (JSON, SEARCH/REPLACE blocks, patch envelopes) lifts the ceiling — the model writes a complete document containing all N operations in one shot.

This is a property of the *protocol*, not the model.

## The pattern

When asked to do a multi-step edit in single-shot tool-use mode, frontier models reliably:

1. Write an assistant-text plan listing all N edits.
2. Emit one `tool_use` block (for edit #1).
3. Stop — apparently waiting for a `tool_result` that will never come.

Example (Sonnet 4.6, task: add a refund feature touching `orders.py` AND `app.py`):

```
Assistant text:
  ## Plan
  1. Add refund_order to orders.py
  2. Add route_refund to app.py
  3. Update the import in app.py

Tool calls emitted: 1   (str_replace on orders.py only)
Result: oracle FAIL  (app.py untouched)
```

The model's plan is correct. The execution is truncated.

## Evidence

Same task (`c08_add_feature__medium`), same model, three protocols:

| Mode | Format | Tool calls emitted | Result |
|---|---|---:|---|
| `single` (tool_use) | search_replace | 1 | FAIL |
| `single` (tool_use) | semantic | 1–2 | FAIL |
| **`structured` (JSON text)** | semantic | **3** | **PASS** |

Same task, Haiku, semantic format:

| Mode | Tool calls | Result |
|---|---:|---|
| `single` (tool_use) | 1–4 | FAIL |
| `structured` (JSON text) | 3 | PASS |

Across the medium-task suite (n=14), `single`-mode `search_replace` averages **1.0 calls per response** regardless of how many edits the task needs.

## Why this happens

Tool-use is trained on a **multi-turn action-feedback loop**:

```
model → tool_use → harness → tool_result → model → tool_use → ...
```

In that loop, "emit one call, await result" is the rational pattern. The training reinforces it. Even when we tell the model "you have only one response, emit everything", the trained reflex wins.

Structured text output has no such reflex. The model is *writing a document*, and a complete document includes everything. JSON arrays with three entries are as natural as JSON arrays with one entry.

## When tool_use is right

- Multi-turn agents where the result of action N genuinely informs action N+1 (search → read → edit → run tests)
- Single discrete actions (look up a value, send a message, query an API)
- Schema-validated inputs where the provider's JSON-schema enforcement matters
- Prompt caching wins on Anthropic (tool definitions cache well)

## When tool_use is wrong

- **Batched code edits where the plan is fixed up front** — pre-known multi-file refactors, codemods, "fix this set of issues"
- Any case where the per-call "result" is just OK/error and provides no information that affects the next call
- Single-shot evaluations of model-edit quality (you're measuring the protocol's ceiling, not the model's capability)

## Recommended pattern: structured text output

For batched edits, frame the operations as a **document the model writes**:

```json
{
  "plan": "<brief description per planned edit>",
  "changes": [
    {"op": "rename", "paths": [...], "old_name": "...", "new_name": "..."},
    {"op": "str_replace", "path": "...", "old_str": "...", "new_str": "..."},
    {"op": "add", "path": "...", "new_source": "..."}
  ]
}
```

Then parse and apply server-side. The model writes one coherent JSON object with N changes — no "wait for result" reflex.

This is also Aider's pattern (SEARCH/REPLACE blocks in text), Cursor's pattern (code blocks with `// ... existing code ...` markers + a separate apply model), and OpenAI Codex CLI's pattern (`*** Begin Patch` envelopes). All three independently converged on "edit-as-document" instead of "edit-as-tool-call."

## Caveats

- This is empirical, from our own runs. Anthropic's tool-use training may change. We've seen it consistently across Haiku 4.5 and Sonnet 4.6.
- Structured output loses the provider's automatic schema validation. You'll get malformed JSON occasionally and need a parser that's tolerant (multiple code blocks, partial recovery).
- Provider prompt-cache wins still favor tool_use in many real systems. The tradeoff: cache hit rate vs single-shot batch quality.
- For *single-action* edits, tool_use is fine and more ergonomic.

## Test for your own use case

If your task involves emitting **3+ coordinated operations in one shot**, run both protocols head-to-head and compare:

- Number of operations the model actually emits per response
- Pass rate on completion of the full task
- Token cost per successful task

We measured a clear protocol gap on our 14-task medium suite. Run it on yours.

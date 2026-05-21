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

## Quantified: 48-trial single vs structured comparison

We took the four medium tasks that consistently failed in single-shot tool_use mode across every format and every model (c04 signature_change, c05 api_migration, c08 add_feature, c09 remove_sweep) and ran them under both protocols, three formats (`search_replace`, `semantic`, `search_plus`), two models (Haiku 4.5, Sonnet 4.6). Same task contents, same model temperature (0), same applier code.

Headline:

| | `single` (tool_use) | `structured` (JSON text) |
|---|---:|---:|
| **Pass rate (n=24 cells)** | 8% | **79%** |
| **Calls per response** | ~1 (always 1 for sr/sr_plus) | 2–12 |

Per-task pass matrix (format×mode columns; ✓ pass / ✗ fail / N = number of operations emitted):

| Task | model | sr/single | sr/struct | sem/single | sem/struct | sp/single | sp/struct |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| c04 sig_change | Haiku | ✗ 1 | **✓ 2** | ✓ 3 | ✗ 2 | ✗ 1 | **✓ 2** |
| c04 sig_change | Sonnet | ✗ 1 | **✓ 2** | ✗ 1 | **✓ 2** | ✓ 1 | ✓ 2 |
| c05 api_migration | Haiku | ✗ 1 | **✓ 4** | ✗ 5 | **✓ 5** | ✗ 1 | **✓ 4** |
| c05 api_migration | Sonnet | ✗ 1 | **✓ 4** | ✗ 2 | **✓ 5** | ✗ 1 | **✓ 4** |
| c08 add_feature | Haiku | ✗ 1 | **✓ 3** | ✗ 3 | **✓ 3** | ✗ 1 | **✓ 3** |
| c08 add_feature | Sonnet | ✗ 1 | **✓ 3** | ✗ 1 | **✓ 5** | ✗ 1 | **✓ 3** |
| c09 remove_sweep | Haiku | ✗ 1 | ✗ 9 | ✗ 5 | ✗ 10 | ✗ 1 | ✗ 9 |
| c09 remove_sweep | Sonnet | ✗ 1 | **✓ 2** | ✗ 2 | ✗ 12 | ✗ 1 | **✓ 2** |

### What this tells us

**1. Protocol dominates format.** Whether the model uses text-edit (`sr`) or semantic ops (`semantic`) matters far less than whether it's writing tool_use blocks or a JSON document. The pass-rate gap (8% → 79%) is entirely a protocol effect.

**2. The format is no longer suppressed by the protocol.** In `single` mode, format choice barely mattered — the model emitted ~1 call regardless, packing as much change as the format allowed. In `structured` mode, each format gets to do what it was designed for:
  - `sr` issues 3–4 surgical replacements
  - `semantic` issues 5+ atomic refactor ops
  - `sr_plus` mixes both

**3. Call counts scale with task complexity in structured mode.** c04 needs ~2 edits → models emit 2. c05/c08 need ~3–5 → models emit 3–5. c09 needs ~6 → models emit 9–12 (trying hard but sometimes missing edges). In `single` mode all of these compressed to ~1 call.

**4. c09 isolates the residual difficulty.** Even with 10–12 structured calls and 5+ minutes of model compute, semantic on c09 still fails — the task ("remove `apply_shipping` and *every* reference including in 2 dependent functions, 2 constants, and the test imports") is genuinely hard for one-shot reasoning. Sonnet sr/sr_plus solve it cleanly with 2 calls by packing the function-and-callers into one big `str_replace` chunk. This is a real format insight that only shows up once protocol stops being the bottleneck.

**5. The breakthrough is reproducible across models.** Same uplift on Haiku 4.5 and Sonnet 4.6. Sonnet under `single` was actually *worse* at multi-call emission than Haiku (1 call vs 3–5 in semantic mode); under `structured` they converge to similar batch sizes. Suggests the tool-use single-call bias is *stronger in more capable models*, not weaker.

## Opus 4.7 on the residual failure (c09)

c09 (`remove_sweep`: delete `apply_shipping` and every reference — touches 2 functions, 2 constants, the importer in tests, and a test file) was the only task semantic-structured couldn't solve on Sonnet or Haiku. Re-ran on Opus 4.7:

| format | mode | pass | calls | tokens |
|---|---|:---:|:---:|---:|
| search_replace | single | ✗ | 2 | 8.2k |
| search_replace | structured | ✓ | 3 | 8.2k |
| semantic | single | ✗ | 1 | 6.0k |
| **semantic** | **structured** | **✗** | **6** | 8.9k |
| search_plus | single | ✓ | 3 | 9.8k |
| search_plus | structured | ✓ | 3 | 8.4k |

Three observations:

**Opus pushes back against the single-call reflex more than Sonnet.** Opus single-mode `search_plus` emits 3 tool calls and passes. Sonnet always emits 1. Suggests the bias varies by model and Opus is partially trained out of it.

**`search_plus` single-shot is the first cell to pass c09 in non-structured mode** across any model. The hybrid (text-replace + `rename`/`move`/`change_value_of`) gave Opus enough text-edit breadth to pack the multi-edit chunks while still expressing the renames atomically.

**Semantic structured still fails on c09 even with Opus emitting 6 ops.** This isolates a real format-level finding: **destructive multi-edit tasks decompose poorly into atomic semantic ops.** Each of the 6 things needed (`remove function`, `remove constant` × 2, `replace function body` × 2, `update test imports`) is a distinct atomic op. The model has to enumerate every one without missing any. `search_replace` and `search_plus` solved the same task with 3 calls because one big `str_replace` packs multiple chunk-level changes in pricing.py simultaneously.

The asymmetry:

- **Additive multi-edit** tasks (`add this function, add this route, update this import`): both atomic semantic ops and text-chunk replacements work in structured mode, because each edit has a clean local target.
- **Destructive multi-edit** tasks (`remove this and every reference`): text-chunk replacement is materially better, because chunking lets the model rewrite multiple co-located edits at once without enumerating each.

Atomic ops are like Lisp's "do one thing" primitives. Chunk replacement is like sed across a region. For pure refactors over named entities (rename, move) atomic wins. For tear-out edits, chunked text wins.

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

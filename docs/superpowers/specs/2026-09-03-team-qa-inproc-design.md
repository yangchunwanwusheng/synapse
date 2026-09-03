# Issue #17 a: Four-Agent QA In-Process Design

## Scope

Implement the in-process half of Issue #17 for HotpotQA and CoQA. The new path must execute all four existing CodeAgent roles and report QA quality plus per-agent activity. Existing solo QA behavior and result fields remain unchanged.

The multiprocess half is out of scope until Issue #148748 segment two provides the process runtime and shared state-plane contracts. No in-process result may be labelled as multiprocess evidence.

## Public Interface

- Keep the existing `hotpot` and `coqa` commands in solo mode by default.
- Add an explicit `--topology` option with `solo` and `team-inproc` values.
- Record the selected topology in the config snapshot and result payload.
- Keep current solo aggregate and per-item fields stable so existing scripts and claims continue to work.

## Components

### QA team runner

Add a focused QA team adapter under `synapse/qa/`. It owns the QA-specific four-role flow while reusing `build_team`, `Scheduler`, `MemoryStore`, `HybridRetriever`, `CAS`, and the existing QA prompts/scoring helpers.

For each QA item or turn:

1. Planner receives the question and emits a retrieval plan.
2. Retriever consumes the plan and selected corpus context, then produces evidence.
3. Executor runs CodeAct against that evidence and returns a structured result.
4. Summarizer receives recovered evidence plus the executor result and emits the final short answer.
5. The final answer is scored with the existing multi-reference EM/F1 implementation.

Each role must call its real `CodeAgent.run` method. Merely creating capabilities or recording synthetic messages is not sufficient.

### Shared QA utilities

Move only genuinely shared operations out of the solo pipeline: dataset-shaped context preparation, retrieval selection, scoring/result assembly, and model token snapshots. Do not force the synthetic `Task` abstraction onto QA because it lacks reference answers and corpus structure.

### Metrics

Extend metrics with a serializable per-agent breakdown keyed by stable agent id. For every sender, record:

- messages sent;
- logical header, text, and non-text bytes;
- serialized transport bytes;
- LLM input/output tokens;
- CodeAgent steps.

Global counters remain the source of existing aggregate fields. Per-agent counters must sum to their corresponding global counters where ownership is defined.

Replace the current QA `nontext_bytes = encoded handle lengths + 8` proxy with the byte length of the actual non-text payload representation used by the team message. Handle text remains part of serialized transport/header metadata and must not be double-counted as embedding or residual payload.

### Manifest and result schema

The team result adds `topology`, `agent_metrics`, and per-item team trace summaries. The manifest continues to be written through the existing `write_run` path. Schema validation must reject malformed per-agent counters and verify aggregate conservation without requiring team fields on legacy solo runs.

## Error Handling

- Unknown topology values fail during config/CLI validation.
- A missing team role or missing final answer fails the team item explicitly; it is not converted into a zero-quality successful run.
- Agent execution exceptions propagate to the existing CLI controlled failure path.
- Metrics are emitted only for completed sends and completed agent calls.
- Dataset and scoring errors use the existing fail-fast behavior.

## Compatibility

- Default CLI behavior remains solo.
- Existing `run_text`, `run_synapse`, `run_text_hotpot`, and `run_synapse_hotpot` callers retain their return shapes.
- Existing claim numbers must not be recomputed from team runs until a separately reviewed real-API experiment is available.
- No multiprocess flag, process claim, or #148748 placeholder implementation is introduced in this segment.

## Verification

Tests are written before production changes and cover:

- all four roles execute for HotpotQA and CoQA;
- team predictions receive multi-reference EM/F1;
- per-agent message, byte, token, and step counters are present and conserve aggregate totals;
- non-text byte accounting uses actual payload bytes rather than handle-string length;
- solo return shapes and existing QA metrics remain unchanged;
- manifest accepts valid team results and rejects malformed agent breakdowns;
- CLI defaults to solo and selects `team-inproc` only explicitly;
- the full lint, pytest, smoke, and build gate passes in the project environment.

## Deferred Segment

After Issue #148748 segment two lands, a separate design and implementation pass will map the same logical roles to processes, replace object references with shared-state handles, define cross-process metric ownership and correlation ids, extend manifest process metadata, and produce the required real-API N=3 probe. That work is required before Issue #17 can be closed in full.

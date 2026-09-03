# Four-Agent QA In-Process Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicitly selected in-process four-CodeAgent execution path for HotpotQA and CoQA with honest per-agent metrics, while preserving the existing solo QA path.

**Architecture:** A new `qa/team_pipeline.py` adapts dataset records to the existing Planner, Retriever, Executor, and Summarizer runtime. `Metrics` owns sender-based message accounting and agent-run accounting, while the QA harness and CLI expose a separate `team-inproc` result shape so solo and team evidence cannot be mixed.

**Tech Stack:** Python 3.11+, smolagents 1.26, dataclasses, pytest, existing SYNAPSE protocol/stateplane/eval modules.

---

### Task 1: Per-Agent Metrics Contract

**Files:**
- Modify: `源代码及readme文档/src/synapse/eval/metrics.py`
- Modify: `源代码及readme文档/src/synapse/eval/schema.py`
- Test: `源代码及readme文档/tests/test_manifest.py`

- [x] **Step 1: Write failing tests**

Add tests that record messages from two senders and agent executions, then assert that each `agent_metrics` bucket contains `messages`, `header_bytes`, `text_bytes`, `nontext_bytes`, `transport_bytes`, `llm_input_tokens`, `llm_output_tokens`, and `steps`. Assert each field sums to the global counter. Add schema tests that accept a conserved team metrics object and reject a modified per-agent counter.

- [x] **Step 2: Verify RED**

Run `python -m pytest tests/test_manifest.py -k "agent_metrics or team_metrics" -q` and confirm failure because `Metrics` has no per-agent API/schema validation.

- [x] **Step 3: Implement metrics accounting**

Add an `agent_metrics` dictionary to `Metrics`, populate sender byte/message counters inside `record_message`, add `record_agent_run(agent_id, input_tokens, output_tokens, steps)`, merge buckets in `absorb`, and emit them through `summary`. Validate optional `agent_metrics` maps in `schema.py`, including non-negative integer fields and aggregate conservation.

- [x] **Step 4: Verify GREEN**

Run the focused tests and then `python -m pytest tests/test_manifest.py -q`; both must pass.

### Task 2: Four-Role QA Runner

**Files:**
- Create: `源代码及readme文档/src/synapse/qa/team_pipeline.py`
- Modify: `源代码及readme文档/src/synapse/qa/pipeline.py`
- Test: `源代码及readme文档/tests/test_team_qa.py`

- [x] **Step 1: Write failing Hotpot and CoQA tests**

Call the wished-for `run_team_hotpot` and `run_team_coqa` APIs with small fixtures and the real offline mock team. Assert all four stable agent ids have positive step/token activity, each role sends a protocol message, final predictions have EM/F1 fields, metrics conserve, and the result topology is exactly `team-inproc`.

- [x] **Step 2: Verify RED**

Run `python -m pytest tests/test_team_qa.py -q` and confirm import failure for the missing team runner.

- [x] **Step 3: Implement the team adapter**

Build one existing `Team`, bind each QA question, invoke every role with `return_full_result=True`, fail unless each run reaches `state == "success"` with non-empty output, and record token deltas plus action-step counts. Use the existing deterministic paragraph/sentence retrieval to provide corpus evidence, store retriever evidence in CAS, route only its handle between roles, recover it before executor/summarizer consumption, and score the summarizer output with existing multi-reference `score`.

- [x] **Step 4: Make non-text accounting honest**

Set `nontext_bytes` to the actual attached non-text payload length. For current handle-only in-process messages this is zero; handle serialization remains included in `transport_bytes` and headers. Retain `payload_kind` and handles so #148748 can later attach shared-state payload accounting without changing QA semantics.

- [x] **Step 5: Verify GREEN**

Run `python -m pytest tests/test_team_qa.py tests/test_qa.py -q` and confirm both new team behavior and solo regression coverage pass.

### Task 3: Harness, CLI, and Manifest Integration

**Files:**
- Modify: `源代码及readme文档/src/synapse/config.py`
- Modify: `源代码及readme文档/src/synapse/qa/harness.py`
- Modify: `源代码及readme文档/src/synapse/cli.py`
- Modify: `源代码及readme文档/src/synapse/eval/schema.py`
- Test: `源代码及readme文档/tests/test_team_qa.py`
- Test: `源代码及readme文档/tests/test_manifest.py`

- [x] **Step 1: Write failing selection/result tests**

Assert `Config(qa_topology="bad")` fails; CLI parsing defaults Hotpot/CoQA to `solo` and accepts only `team-inproc` explicitly; team harness payloads use `team_total`, `topology`, and per-item team predictions without `text`/`synapse` solo aggregate keys; and `write_run` validates the team result.

- [x] **Step 2: Verify RED**

Run focused tests and confirm failure because topology and team harness branches do not exist.

- [x] **Step 3: Implement explicit selection**

Add `qa_topology` to config and its enum validation. Add `--topology {solo,team-inproc}` to `hotpot` and `coqa`, include it in the manifest command description, and branch to dedicated harness functions. Keep default solo functions and return shapes byte-for-byte compatible. Use separate run tags `hotpot_team_inproc` and `coqa_team_inproc`.

- [x] **Step 4: Implement team result output**

Return and print `topology`, dataset counts, `team_total`, aggregate EM/F1, and per-agent counters. Do not compute or print solo-vs-team savings from these runs.

- [x] **Step 5: Verify GREEN**

Run focused CLI/schema/harness tests and ensure all pass.

### Task 4: Solo Proxy Correction and Full Verification

**Files:**
- Modify: `源代码及readme文档/src/synapse/qa/pipeline.py`
- Modify: `源代码及readme文档/tests/test_qa.py`
- Modify: `源代码及readme文档/README.md`

- [x] **Step 1: Write failing regression tests**

Assert existing handle-only solo Synapse QA messages report `nontext_bytes == 0`, `transport_bytes > 0`, and do not count a non-text transfer without an attached state payload. Preserve all existing answer, token, retrieval, and per-item assertions.

- [x] **Step 2: Verify RED**

Run `python -m pytest tests/test_qa.py -k "nontext" -q` and confirm the old handle-length proxy violates the new expectation.

- [x] **Step 3: Remove the proxy and document the command**

Replace both `sum(len(handle.encode())) + 8` values with zero and explain that serialized handles are already covered by transport/header bytes. Add concise README commands showing explicit `--topology team-inproc` and label multiprocess QA as pending #148748 segment two.

- [x] **Step 4: Run complete verification**

Inside the project environment run `python -m pytest -q`, `python -m synapse.cli smoke`, and `uv build`; all must exit successfully without altering existing user-owned changes. Run Ruff on all new/core changed modules and record the full-repository baseline separately: this execution has 147 pre-existing Ruff findings outside the new Issue #17 implementation.

- [x] **Step 5: Review the diff**

Run `git diff --check` and inspect `git diff --stat` plus the final status. Confirm only Issue #17 a files and the two approved design/plan documents are part of this work.

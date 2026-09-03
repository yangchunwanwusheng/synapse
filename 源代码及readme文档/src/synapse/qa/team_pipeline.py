"""Four-CodeAgent in-process execution path for real QA datasets (Issue #17 a)."""

from __future__ import annotations

import time

from ..eval.metrics import Metrics, embedder_stats
from ..memory.retrieval import HybridRetriever
from ..memory.store import MemoryStore
from ..protocol.handshake import CNR
from ..protocol.messages import ActionType, Message
from ..protocol.scheduler import Scheduler
from ..runtime.team import _make_verify_check_fn, build_team
from ..stateplane.cas import CAS
from ..stateplane.embedding import make_embedder
from .dataset import Conversation, HotpotItem
from .pipeline import _retrieve_paras, _split_sentences
from .scoring import score

TOPOLOGY = "team-inproc"
_AGENT_IDS = ("planner-1", "retriever-1", "executor-1", "summarizer-1")


def _plan_prompt(question: str) -> str:
    return (
        "You have no tools. Produce exactly three short steps for answering this reading-comprehension "
        "question, then call final_answer(steps) where steps is a Python list. "
        f"Question: {question}"
    )


def _retrieve_prompt(question: str, context: str, plan) -> str:
    return (
        "Use only the candidate context below. Select and combine the facts needed to answer the question. "
        "Call final_answer(evidence) where evidence is one concise string; use no other tool.\n"
        f"Plan: {plan}\nQuestion: {question}\nCandidate context:\n{context}"
    )


def _execute_prompt() -> str:
    return (
        "A string variable `evidence` is available. Use CodeAct to inspect it and call "
        "final_answer({'word_count': len(evidence.split())}). Use no other tool."
    )


def _summarize_prompt(question: str) -> str:
    return (
        "Variables `evidence` and `metric` are available. Answer the reading-comprehension question with "
        "the shortest exact phrase supported by evidence. Then call final_answer(answer) as your only tool. "
        f"Question: {question}"
    )


def _action_steps(result) -> int:
    return sum(
        1
        for step in getattr(result, "steps", ())
        if isinstance(step, dict) and isinstance(step.get("step_number"), int)
    )


def _run_agent(agent, prompt: str, metrics: Metrics, additional_args: dict | None = None):
    before_input = int(getattr(agent.model, "input_tokens", 0) or 0)
    before_output = int(getattr(agent.model, "output_tokens", 0) or 0)
    result = agent.run(
        prompt,
        reset=True,
        additional_args=additional_args,
        return_full_result=True,
    )
    if getattr(result, "state", None) != "success":
        raise RuntimeError(f"{agent.agent_id} QA execution failed: state={getattr(result, 'state', None)!r}")
    output = getattr(result, "output", None)
    if output is None or (isinstance(output, str) and not output.strip()):
        raise RuntimeError(f"{agent.agent_id} QA execution returned no output")
    input_tokens = int(getattr(agent.model, "input_tokens", 0) or 0) - before_input
    output_tokens = int(getattr(agent.model, "output_tokens", 0) or 0) - before_output
    metrics.record_agent_run(agent.agent_id, input_tokens, output_tokens, _action_steps(result))
    return output


def _step_snapshot(metrics: Metrics) -> dict[str, int]:
    return {
        agent_id: metrics.agent_metrics.get(agent_id, {}).get("steps", 0) for agent_id in _AGENT_IDS
    }


def _run_team_item(team, scheduler: Scheduler, metrics: Metrics, cas: CAS, qid: str, question: str, context: str):
    team.bind_topic(question)
    before_steps = _step_snapshot(metrics)

    plan = _run_agent(team.planner, _plan_prompt(question), metrics)
    scheduler.send(
        Message(
            scheduler.next_msg_id(),
            team.planner.agent_id,
            team.retriever.agent_id,
            ActionType.PLAN.value,
            params={"qid": qid, "steps": plan},
        )
    )

    evidence = str(_run_agent(team.retriever, _retrieve_prompt(question, context, plan), metrics))
    evidence_handle = cas.put(evidence.encode("utf-8"))
    for receiver in (team.executor.agent_id, team.summarizer.agent_id):
        scheduler.send(
            Message(
                scheduler.next_msg_id(),
                team.retriever.agent_id,
                receiver,
                ActionType.TELL.value,
                params={"qid": qid},
                handles=(evidence_handle,),
                payload_kind="embedding",
                meta={"nontext_bytes": 0},
            )
        )

    received = cas.get(evidence_handle)
    if received is None:
        raise RuntimeError(f"QA evidence handle disappeared before consumption: {qid}")
    received_evidence = received.decode("utf-8")
    metric = _run_agent(
        team.executor,
        _execute_prompt(),
        metrics,
        additional_args={"evidence": received_evidence},
    )
    scheduler.send(
        Message(
            scheduler.next_msg_id(),
            team.executor.agent_id,
            team.summarizer.agent_id,
            ActionType.EXECUTE.value,
            params={"qid": qid},
            result={"metric": metric},
        )
    )

    answer = str(
        _run_agent(
            team.summarizer,
            _summarize_prompt(question),
            metrics,
            additional_args={"evidence": received_evidence, "metric": metric},
        )
    ).strip()
    scheduler.send(
        Message(
            scheduler.next_msg_id(),
            team.summarizer.agent_id,
            "qa-output",
            ActionType.SUMMARIZE.value,
            params={"qid": qid},
            payload_kind="text",
            text=answer,
        )
    )
    after_steps = _step_snapshot(metrics)
    return answer, {
        "agent_steps": {agent_id: after_steps[agent_id] - before_steps[agent_id] for agent_id in _AGENT_IDS}
    }


def _runtime(cfg, team=None):
    team = team or build_team(cfg)
    metrics = Metrics(mode=TOPOLOGY)
    scheduler = Scheduler(
        team.agents(),
        cnr=CNR(check_fn=_make_verify_check_fn(cfg)),
        metrics=metrics,
    )
    return team, metrics, scheduler


def run_team_hotpot(items: list[HotpotItem], cfg, team=None, embedder=None) -> dict:
    """Run HotpotQA/MuSiQue items through all four CodeAgents in one process."""
    team, metrics, scheduler = _runtime(cfg, team)
    embedder = embedder or make_embedder(cfg)
    er0, eh0, et0 = embedder_stats(embedder)
    per_item: list[dict] = []
    recalls: list[float] = []
    started = time.perf_counter()
    for item in items:
        store = MemoryStore(embedder)
        cas = CAS()
        for paragraph in item.paragraphs:
            store.write(
                source_agent="corpus",
                task_topic=item.qid,
                summary=paragraph.title,
                content=paragraph.text,
                kind="evidence",
                tags=("para",),
            )
        retriever = HybridRetriever(store, embedder, cfg)
        hits = _retrieve_paras(retriever, store, item.q, max(1, cfg.qa_para_k), cfg.qa_retrieval)
        titles = {unit.summary for unit in hits}
        recall = (
            sum(title in titles for title in item.gold_titles) / len(item.gold_titles)
            if item.gold_titles
            else 0.0
        )
        recalls.append(recall)
        metrics.record_query(recall > 0)
        context = "\n\n".join(f"[{unit.summary}] {unit.content}" for unit in hits)
        answer, trace = _run_team_item(team, scheduler, metrics, cas, item.qid, item.q, context)
        scored = score(answer, item.answers)
        per_item.append(
            {
                "qid": item.qid,
                "question": item.q,
                "gold": item.answer,
                "golds": list(item.answers),
                "pred": answer,
                "f1": scored["f1"],
                "em": scored["em"],
                "retrieved_titles": sorted(titles),
                "gold_titles": list(item.gold_titles),
                "gold_hit": recall,
                "trace": trace,
            }
        )
        metrics.cas_writes += cas.writes
        metrics.cas_write_bytes += cas.write_bytes
    metrics.latency_s = time.perf_counter() - started
    metrics.llm_tokens = metrics.llm_output_tokens
    metrics.quality = round(sum(record["f1"] for record in per_item) / len(per_item), 4) if per_item else 0.0
    er, eh, et = embedder_stats(embedder)
    metrics.embed_requests, metrics.embed_cache_hits, metrics.embed_input_tokens = er - er0, eh - eh0, et - et0
    return {
        "topology": TOPOLOGY,
        "metrics": metrics,
        "per_item": per_item,
        "f1_per_item": [record["f1"] for record in per_item],
        "em_per_item": [record["em"] for record in per_item],
        "gold_recall": round(sum(recalls) / len(recalls), 3) if recalls else 0.0,
    }


def run_team_coqa(conv: Conversation, cfg, team=None, embedder=None) -> dict:
    """Run every turn of one CoQA conversation through all four CodeAgents in one process."""
    team, metrics, scheduler = _runtime(cfg, team)
    embedder = embedder or make_embedder(cfg)
    er0, eh0, et0 = embedder_stats(embedder)
    store = MemoryStore(embedder)
    cas = CAS()
    for index, sentence in enumerate(_split_sentences(conv.story)):
        store.write(
            source_agent="story",
            task_topic=conv.conv_id,
            summary=f"story-sent-{index}",
            content=sentence,
            kind="evidence",
            tags=("story",),
            task_id=conv.conv_id,
        )
    retriever = HybridRetriever(store, embedder, cfg)
    per_item: list[dict] = []
    history: list[tuple[str, str]] = []
    started = time.perf_counter()
    for turn in conv.turns:
        hits = [
            unit
            for unit, _ in retriever.search(
                turn.q,
                tags=("story",),
                k=max(1, cfg.qa_sentences_k),
                consume_k=max(1, cfg.qa_sentences_k),
            )
        ]
        metrics.record_query(bool(hits))
        context = "\n".join(unit.content for unit in hits)
        recent = history[-max(1, cfg.qa_history_k) :]
        if recent:
            context += "\nPrior QA:\n" + "\n".join(f"Q: {q}\nA: {a}" for q, a in recent)
        qid = f"{conv.conv_id}:{turn.idx}"
        answer, trace = _run_team_item(team, scheduler, metrics, cas, qid, turn.q, context)
        scored = score(answer, turn.answers)
        history.append((turn.q, answer))
        per_item.append(
            {
                "qid": qid,
                "question": turn.q,
                "gold": turn.gold,
                "golds": list(turn.answers),
                "pred": answer,
                "f1": scored["f1"],
                "em": scored["em"],
                "trace": trace,
            }
        )
    metrics.latency_s = time.perf_counter() - started
    metrics.llm_tokens = metrics.llm_output_tokens
    metrics.quality = round(sum(record["f1"] for record in per_item) / len(per_item), 4) if per_item else 0.0
    metrics.cas_writes, metrics.cas_write_bytes = cas.writes, cas.write_bytes
    er, eh, et = embedder_stats(embedder)
    metrics.embed_requests, metrics.embed_cache_hits, metrics.embed_input_tokens = er - er0, eh - eh0, et - et0
    return {
        "topology": TOPOLOGY,
        "metrics": metrics,
        "per_item": per_item,
        "f1_per_turn": [record["f1"] for record in per_item],
        "em_per_turn": [record["em"] for record in per_item],
    }

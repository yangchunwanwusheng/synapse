"""Issue #17 a: four-Agent in-process QA execution and accounting."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from synapse.config import Config, ConfigError
from synapse.eval.manifest import write_run
from synapse.eval.schema import validate_run_result
from synapse.qa.dataset import Conversation, HotpotItem, Paragraph, Turn
from synapse.qa.harness import run_coqa_team, run_hotpot_team
from synapse.qa.team_pipeline import run_team_coqa, run_team_hotpot

AGENT_IDS = {"planner-1", "retriever-1", "executor-1", "summarizer-1"}


def _hotpot_items() -> list[HotpotItem]:
    return [
        HotpotItem(
            qid="q1",
            q="Who founded Alpha City?",
            answer="Ada",
            answer_aliases=("Ada Smith",),
            paragraphs=[
                Paragraph("Alpha City", "Alpha City was founded by Ada Smith in 1901."),
                Paragraph("Ada Smith", "Ada was an engineer and civic leader."),
                Paragraph("Noise", "An unrelated paragraph about ocean currents."),
            ],
            gold_titles=("Alpha City", "Ada Smith"),
            level="bridge",
        )
    ]


def _assert_real_four_role_trace(result: dict, expected_items: int) -> None:
    assert result["topology"] == "team-inproc"
    metrics = result["metrics"]
    summary = metrics.summary()
    assert set(summary["agent_metrics"]) == AGENT_IDS
    for agent_id in AGENT_IDS:
        counters = summary["agent_metrics"][agent_id]
        assert counters["steps"] > 0, f"{agent_id} did not execute a CodeAgent action step"
        assert counters["llm_input_tokens"] > 0 and counters["llm_output_tokens"] > 0
        assert counters["messages"] > 0, f"{agent_id} did not send a protocol message"
    for field in (
        "messages",
        "header_bytes",
        "text_bytes",
        "nontext_bytes",
        "transport_bytes",
        "llm_input_tokens",
        "llm_output_tokens",
        "steps",
    ):
        assert sum(v[field] for v in summary["agent_metrics"].values()) == summary[field]
    assert metrics.transport_bytes > 0
    assert metrics.nontext_bytes == 0  # handle-only inproc frames carry no vector/residual payload
    assert len(result["per_item"]) == expected_items
    for record in result["per_item"]:
        assert {"qid", "question", "gold", "golds", "pred", "f1", "em", "trace"} <= set(record)
        assert set(record["trace"]["agent_steps"]) == AGENT_IDS
        assert all(steps > 0 for steps in record["trace"]["agent_steps"].values())


def test_hotpot_team_inproc_executes_all_four_roles_and_scores_answer():
    result = run_team_hotpot(_hotpot_items(), Config())
    _assert_real_four_role_trace(result, expected_items=1)
    record = result["per_item"][0]
    assert 0.0 <= record["f1"] <= 1.0
    assert 0.0 <= record["em"] <= 1.0
    assert 0.0 <= result["gold_recall"] <= 1.0
    assert record["gold_hit"] == result["gold_recall"]


def test_coqa_team_inproc_executes_all_four_roles_per_turn_and_scores_answer():
    conv = Conversation(
        conv_id="c1",
        source="fixture",
        story="Ada founded Alpha City. Bob later became its mayor. The river crosses the city.",
        turns=[
            Turn(0, "Who founded Alpha City?", "Ada", ("Ada Smith",)),
            Turn(1, "Who became mayor?", "Bob"),
        ],
    )
    result = run_team_coqa(conv, Config())
    _assert_real_four_role_trace(result, expected_items=2)
    assert [record["qid"] for record in result["per_item"]] == ["c1:0", "c1:1"]
    assert len(result["f1_per_turn"]) == len(result["em_per_turn"]) == 2


def test_qa_topology_config_rejects_unknown_value():
    assert Config().qa_topology == "solo"
    assert Config(qa_topology="team-inproc").qa_topology == "team-inproc"
    try:
        Config(qa_topology="multiproc")
        raise AssertionError("unimplemented multiproc topology must fail explicitly")
    except ConfigError:
        pass


def test_cli_qa_topology_defaults_to_solo_and_accepts_team_inproc(monkeypatch):
    from synapse import cli

    seen: list[tuple[str, str]] = []

    def capture_hotpot(args):
        seen.append(("hotpot", args.topology))
        return 0

    def capture_coqa(args):
        seen.append(("coqa", args.topology))
        return 0

    monkeypatch.setattr(cli, "cmd_hotpot", capture_hotpot)
    monkeypatch.setattr(cli, "cmd_coqa", capture_coqa)
    assert cli.main(["hotpot"]) == 0
    assert cli.main(["hotpot", "--topology", "team-inproc"]) == 0
    assert cli.main(["coqa", "--topology", "team-inproc"]) == 0
    assert seen == [("hotpot", "solo"), ("hotpot", "team-inproc"), ("coqa", "team-inproc")]


def test_team_harness_results_are_separate_from_solo_and_manifest_valid(tmp_path):
    hotpot_path = tmp_path / "hotpot.json"
    hotpot_path.write_text(
        json.dumps(
            [
                {
                    "id": "q1",
                    "question": "Who founded Alpha City?",
                    "answer": "Ada",
                    "paragraphs": [
                        {"title": "Alpha", "text": "Ada founded Alpha City."},
                        {"title": "Noise", "text": "Unrelated text."},
                    ],
                    "gold_titles": ["Alpha"],
                    "level": "bridge",
                }
            ]
        ),
        encoding="utf-8",
    )
    cfg = Config(qa_topology="team-inproc", qa_para_k=2)
    result = run_hotpot_team(cfg, n_items=1, path=str(hotpot_path))
    assert result["topology"] == "team-inproc"
    assert "team_total" in result and "text" not in result and "synapse" not in result
    assert set(result["team_total"]["agent_metrics"]) == AGENT_IDS

    out_dir = write_run(
        "hotpot_team_inproc",
        cfg,
        result,
        command="hotpot --topology team-inproc --n 1",
        dataset={"path": str(hotpot_path), "sha256": "x" * 64, "n_items": 1},
        per_item=result["per_item"],
        root=str(tmp_path / "runs"),
    )
    doc = json.loads((tmp_path / "runs" / os.path.basename(out_dir) / "result.json").read_text("utf-8"))
    assert validate_run_result(doc) == []


def test_coqa_team_harness_aggregates_conversations_without_solo_keys(tmp_path):
    coqa_path = tmp_path / "coqa.json"
    coqa_path.write_text(
        json.dumps(
            [
                {
                    "id": "c1",
                    "source": "fixture",
                    "story": "Ada founded Alpha City. Bob became mayor.",
                    "turns": [{"q": "Who founded it?", "a": "Ada"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    result = run_coqa_team(Config(qa_topology="team-inproc"), n_conv=1, path=str(coqa_path))
    assert result["topology"] == "team-inproc"
    assert result["n_conversations"] == 1
    assert "team_total" in result and "text_total" not in result and "synapse_total" not in result
    assert len(result["per_item"]) == 1

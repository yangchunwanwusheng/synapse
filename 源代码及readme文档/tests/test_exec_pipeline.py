"""execute 受控多行管线测试（Issue #149013）。

覆盖：execute_prompt 受控多行契约（任务目标注入/整数契约/白名单不变）、
summarize_prompt 降级措辞（禁止 metric=None 当 0）、run_executor_with_retry 的
重试预算与显式降级、ExecOutcome envelope、normalize_codeact 多行恢复（散文前缀
+合法多行代码不再丢变量赋值）、text_mode 端到端 execution_status 传播。
"""

from __future__ import annotations

import pytest

smolagents_local = pytest.importorskip("smolagents.local_python_executor")

from synapse.config import Config  # noqa: E402
from synapse.prompts import execute_prompt, summarize_prompt  # noqa: E402
from synapse.runtime.exec_pipeline import (  # noqa: E402
    EXEC_RETRY_BUDGET,
    ExecOutcome,
    run_executor_with_retry,
)
from synapse.tasks import Task  # noqa: E402


def _task():
    return Task("g1-0", "alpha", "deep dive alpha hop 0")


# ---------------- execute_prompt 受控多行契约 ----------------


def test_execute_prompt_injects_task_context_and_multiline_contract():
    p = execute_prompt(_task())
    assert "topic: alpha" in p and "question: deep dive alpha hop 0" in p
    assert "multi-line" in p  # 多行许可
    assert "non-negative int" in p  # 返回契约：非负整数
    assert "Do NOT import" in p  # 白名单不变：不新开 import 自由度
    assert "final_answer" in p


def test_execute_prompt_task_is_required():
    with pytest.raises(TypeError):
        execute_prompt()  # 复审 P1：必填，防遗漏调用静默退回旧行为


def test_summarize_prompt_contract_sync():
    ok_p = summarize_prompt(_task())
    assert "integer statistic" in ok_p  # 不再绑死 "word count"
    assert "word count" not in ok_p
    deg_p = summarize_prompt(_task(), execution_status="degraded")
    assert "FAILED" in deg_p and "NOT" in deg_p and "unavailable" in deg_p


# ---------------- run_executor_with_retry：重试 + 显式降级 ----------------


class _FakeExecu:
    def __init__(self, script):
        self.script = list(script)  # 每次run()弹出；'@raise' 抛异常
        self.calls = 0

    def run(self, prompt, reset=True, additional_args=None):
        self.calls += 1
        item = self.script.pop(0) if self.script else "@raise"
        if item == "@raise":
            raise RuntimeError("boom")
        return item


def test_retry_success_first_attempt_no_retry():
    ex, summary = run_executor_with_retry(_FakeExecu([5]), _task(), "a b c")
    assert ex.status == "ok" and ex.metric == 5 and ex.retries == 0 and summary == ""


def test_retry_success_after_exception():
    ex, _ = run_executor_with_retry(_FakeExecu(["@raise", 7]), _task(), "a b")
    assert ex.status == "ok" and ex.metric == 7 and ex.retries == 1  # 预算 ≥1：第二次成功


def test_retry_exhausted_degrades_explicitly_not_zero():
    ex, summary = run_executor_with_retry(_FakeExecu(["@raise", "@raise"]), _task(), "a")
    # "0 静默"禁令：降级 metric=None（非 0 哨兵），status/failure_kind 显式
    assert ex.status == "degraded" and ex.metric is None and ex.failure_kind == "exception"
    assert ex.retries == EXEC_RETRY_BUDGET
    assert "attempt0" in summary and "attempt1" in summary


def test_type_contract_rejects_bool_float_negative():
    for bad in (True, 5.0, -5):
        # 纯契约失败：两次尝试都返回同型坏值 → failure_kind=type_contract
        ex, _ = run_executor_with_retry(_FakeExecu([bad, bad]), _task(), "a b c")
        assert ex.status == "degraded", f"{bad!r} 不得静默转成契约成功"
        assert ex.metric is None
        assert ex.failure_kind == "type_contract"
        # 混合失败（坏值后假 agent 抛异常）→ 如实标 mixed，不冒充单一类型
        ex2, _ = run_executor_with_retry(_FakeExecu([bad]), _task(), "a b c")
        assert ex2.failure_kind == "mixed"


def test_str_final_answer_single_out_as_non_int_final_answer():
    # 复审 P2-1：str 通常是超时/步数耗尽后 provide_final_answer 的文本兜底，
    # 单列口径，不与 bool/float 的类型契约违反混标
    ex, _ = run_executor_with_retry(_FakeExecu(["oops", "again"]), _task(), "a b c")
    assert ex.status == "degraded" and ex.metric is None
    assert ex.failure_kind == "non_int_final_answer"
    ex2, _ = run_executor_with_retry(_FakeExecu([42]), _task(), "a b c")
    assert ex2.status == "ok"  # int 正常成功不受影响


def test_type_contract_failure_then_int_success():
    ex, _ = run_executor_with_retry(_FakeExecu(["42", 3]), _task(), "a b c")
    assert ex.status == "ok" and ex.metric == 3 and ex.retries == 1


def test_outcome_as_dict_envelope():
    d = ExecOutcome(metric=4, status="ok", retries=0, failure_kind=None).as_dict()
    assert d == {"metric": 4, "status": "ok", "retries": 0, "failure_kind": None}


# ---------------- normalize_codeact 多行恢复 ----------------


def test_normalize_recovers_multiline_with_assignment():
    from synapse.runtime.model import normalize_codeact

    raw = "Thought: I will compute it.\nresult = len(evidence.split())\nfinal_answer(result)</code>"
    fixed = normalize_codeact(raw)
    assert "result = len(evidence.split())" in fixed  # 旧逻辑只截调用会丢赋值
    assert fixed.startswith("<code>") and fixed.endswith("</code>")


def test_normalize_multiline_bare_code_without_tags():
    from synapse.runtime.model import normalize_codeact

    raw = "count = 0\nfor w in evidence.split():\n    count += 1\nfinal_answer(count)"
    fixed = normalize_codeact(raw)
    assert fixed.startswith("<code>") and "for w in evidence.split():" in fixed


def test_normalize_unrecoverable_prose_returns_original():
    from synapse.runtime.model import normalize_codeact

    prose = "I think final_answer( is the way but cannot parse this"
    assert normalize_codeact(prose) == prose  # 不可恢复 → 显式失败交给重试，不产出缺变量片段


def test_normalize_single_line_legacy_paths_unchanged():
    from smolagents.utils import parse_code_blobs

    from synapse.runtime.model import normalize_codeact

    tags = ("<code>", "</code>")
    assert (
        parse_code_blobs(normalize_codeact("final_answer(len(evidence.split()))</code>"), tags).strip()
        == "final_answer(len(evidence.split()))"
    )
    assert normalize_codeact("Shirley Temple") == "Shirley Temple"  # 纯文本不动
    fenced = "<code>\nfinal_answer(1)\n</code>"
    assert normalize_codeact(fenced) == fenced  # 已 fenced 不动


# ---------------- text_mode 端到端（mock 离线） ----------------


def test_run_text_mock_returns_ok_execution_status():
    from synapse.modes.text_mode import run_text
    from synapse.runtime.team import build_team

    cfg = Config()
    task = _task()
    res = run_text(task, cfg, team=build_team(cfg))
    assert res["execution_status"] == "ok"
    m = res["metrics"]
    assert m.exec_retries == 0 and m.exec_degradations == 0
    # mock executor CodeAct：result = len(evidence.split()) → n_facts*2+... 由 mock 文本长度决定，恒为 int
    assert isinstance(res["conclusion"], str) and res["conclusion"]

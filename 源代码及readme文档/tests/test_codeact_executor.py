"""CodeAct 执行边界测试（V3-08 / Issue #148750）。

覆盖：进程级隔离执行器（SubprocessExecutor）的核心承诺——final_answer 语义与进程内
一致、state 跨步保持、import 白名单拦截、超时强杀（无泄漏线程）、子进程失败不炸父进程、
非 final_answer 工具注入显式拒绝；CNR check_fn 真实探针（local/subprocess 两档）；
Config 枚举校验；以及 CodeAgent(executor=SubprocessExecutor) 端到端真跑一段 CodeAct。
"""

from __future__ import annotations

import threading
import time

import pytest

smolagents_local = pytest.importorskip("smolagents.local_python_executor")

from synapse.config import Config, ConfigError  # noqa: E402
from synapse.runtime.subprocess_executor import SubprocessExecutor  # noqa: E402


def _fa():
    # final_answer 占位与 smolagents 本地路径同构：LocalPythonExecutor 会把它包成
    # FinalAnswerException(value) → evaluate 捕获后返回 (value, is_final=True)
    return {"final_answer": lambda *a: a[0] if len(a) == 1 else (a or None)}


def test_subprocess_executor_final_answer_roundtrip():
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    out = ex("x = 40 + 2\nfinal_answer(x)")
    assert out.is_final_answer is True
    assert out.output == 42


def test_subprocess_executor_state_persists_across_steps():
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    ex.send_variables({"evidence": "alpha beta gamma"})
    out = ex("n = len(evidence.split())\nfinal_answer(n)")
    assert out.output == 3
    # 第一步写入的变量第二步仍可见（send_variables → 子进程 state → 回传）
    out2 = ex("final_answer(n * 10)")
    assert out2.output == 30


def test_subprocess_executor_blocks_unauthorized_imports():
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    # 匹配须钉住白名单拦截语义（复审 P2：过宽的 "failed" 会掩盖子进程任意崩溃）
    with pytest.raises(Exception, match=r"(?i)not (?:allowed|authorized)|authorized import"):
        ex("import subprocess")


def test_subprocess_executor_timeout_kills_without_thread_leak():
    threads_before = threading.active_count()
    ex = SubprocessExecutor(timeout_seconds=3)
    ex.send_tools(_fa())
    t0 = time.monotonic()
    with pytest.raises(Exception, match="(?i)maximum execution time|subprocess killed"):
        ex("while True:\n    pass")
    wall = time.monotonic() - t0
    assert wall < 15, f"超时强杀应在 wall-clock 附近完成，实际 {wall:.1f}s"
    # 进程级强杀：父进程不得因之残留工作线程（对照 local 档线程池超时线程不可强杀）
    assert threading.active_count() <= threads_before + 1
    # 强杀后执行器仍可服务下一步（一次性进程，无状态损坏）
    out = ex("final_answer('recovered')")
    assert out.output == "recovered"


def test_subprocess_executor_child_failure_contained():
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    with pytest.raises(Exception, match="(?i)ZeroDivision|failed"):
        ex("final_answer(1 / 0)")
    out = ex("final_answer('parent alive')")
    assert out.output == "parent alive"


def test_subprocess_executor_rejects_extra_tools():
    ex = SubprocessExecutor()
    with pytest.raises(NotImplementedError, match="web_search"):
        ex.send_tools({"final_answer": lambda *a: a, "web_search": lambda *a: a})


def test_check_fn_real_probe_local_mode():
    from synapse.protocol.messages import Capability
    from synapse.runtime.team import _make_verify_check_fn

    check = _make_verify_check_fn(Config())
    cap = Capability(
        agent_id="executor-1",
        role="executor",
        actions=("EXECUTE",),
        encodings=("text",),
        model_family="m",
        probe=("codeact_sandbox",),
    )
    assert check(cap) == {"codeact_sandbox"}  # 真探针 final_answer(2**10) 通过 → 验证生效


def test_check_fn_real_probe_subprocess_mode():
    from synapse.protocol.messages import Capability
    from synapse.runtime.team import _make_verify_check_fn

    check = _make_verify_check_fn(Config(codeact_executor="subprocess", codeact_timeout_s=30))
    cap = Capability(
        agent_id="executor-1",
        role="executor",
        actions=("EXECUTE",),
        encodings=("text",),
        model_family="m",
        probe=("codeact_sandbox",),
    )
    assert check(cap) == {"codeact_sandbox"}


def test_check_fn_unrelated_probe_untouched():
    from synapse.protocol.messages import Capability
    from synapse.runtime.team import _make_verify_check_fn

    check = _make_verify_check_fn(Config())
    cap = Capability(
        agent_id="x-1",
        role="executor",
        actions=(),
        encodings=("text",),
        model_family="m",
        probe=("something_else",),
    )
    assert check(cap) == set()  # 非本探针职责的声明项不得被"顺带验证"


def test_build_team_wires_subprocess_executor():
    from synapse.runtime.team import build_team

    team = build_team(Config(codeact_executor="subprocess", codeact_timeout_s=30))
    execs = [ag.python_executor for ag in team.agents()]
    for ex in execs:
        assert isinstance(ex, SubprocessExecutor)
        assert ex.timeout_seconds == 30
    # 复审 P1-1：4 个 Agent 必须各持独立 executor 实例（共享会跨 Agent 串扰 state）
    assert len({id(ex) for ex in execs}) == 4
    # 默认档保持 smolagents 进程内执行器（历史口径零回归）
    team_local = build_team(Config())
    assert not isinstance(team_local.agents()[0].python_executor, SubprocessExecutor)


def test_subprocess_executor_state_isolated_between_instances():
    """复审 P1-1 隔离语义：一个执行器实例写入的变量对另一实例不可见。"""
    ex1 = SubprocessExecutor(timeout_seconds=30)
    ex1.send_tools(_fa())
    ex1("secret_marker = 'agent-1-only'")
    ex2 = SubprocessExecutor(timeout_seconds=30)
    ex2.send_tools(_fa())
    with pytest.raises(Exception, match="(?i)not defined|failed"):
        ex2("final_answer(secret_marker)")


def test_config_enum_rejects_typo():
    with pytest.raises(ConfigError, match="codeact_executor"):
        Config(codeact_executor="subproces")  # 拼写错误构造即失败，不静默落 local


@pytest.mark.parametrize("field", ["codeact_timeout_s", "codeact_memory_mb", "codeact_cpu_s"])
def test_config_rejects_non_positive_resource_params(field):
    with pytest.raises(ConfigError, match=field):
        Config(**{field: 0})  # 复审：资源参数非正值会让超时形同虚设/rlimit 换算失真


def test_subprocess_executor_state_per_key_pickle_filter():
    """复审 P1-2：父侧 state 含个别不可 pickle 值时只丢该键，不拖垮整个 state。"""
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    ex.send_variables({"evidence": "alpha beta", "cb": lambda: 1})  # lambda 不可 pickle
    out = ex("n = len(evidence.split())\nfinal_answer(n)")
    assert out.output == 2  # evidence（"alpha beta"）仍可见：逐 key 过滤，而非整体丢失


def test_subprocess_executor_unpicklable_final_answer_fails_explicitly():
    """复审：不可 pickle 的 final answer 显式 SerializationError，不静默 repr 降级。"""
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    with pytest.raises(Exception, match="(?i)SerializationError.*not picklable"):
        ex("class P:\n    pass\nfinal_answer(P())")


def test_subprocess_executor_unpicklable_intermediate_output_repr_fallback():
    """非 final 中间结果不可 pickle → repr 降级且打标（观察面，非业务承诺）。"""
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    out = ex("class P:\n    pass\nx = P()\nlen(str(x))")
    assert isinstance(out.output, (str, int))  # repr 文本或长度值，不炸、不静默改 final 语义
    assert out.is_final_answer is False


def test_codeagent_end_to_end_with_subprocess_executor():
    """端到端：MockChatModel 驱动 CodeAgent，CodeAct 在隔离子进程内真执行。"""
    from smolagents import CodeAgent

    from synapse.runtime.model import MockChatModel

    agent = CodeAgent(
        tools=[],
        model=MockChatModel(role="executor", n_facts=4),
        name="executor_1",
        max_steps=3,
        verbosity_level=0,
        add_base_tools=False,
        executor=SubprocessExecutor(timeout_seconds=30),
    )
    result = agent.run("count words", additional_args={"evidence": "w1 w2 w3 w4"})
    # executor 角色 CodeAct：result = len(evidence.split()) → 4（来自隔离子进程的真实求值）
    assert int(result) == 4

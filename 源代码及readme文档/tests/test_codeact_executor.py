"""CodeAct 执行边界测试（V3-08 / Issue #148750；#149013 local 档超时回收）。

覆盖：进程级隔离执行器（SubprocessExecutor）的核心承诺——final_answer 语义与进程内
一致、state 跨步保持、import 白名单拦截、超时强杀（无泄漏线程）、子进程失败不炸父进程、
非 final_answer 工具注入显式拒绝；CNR check_fn 真实探针（local/subprocess 两档）；
Config 枚举校验；CodeAgent(executor=SubprocessExecutor) 端到端真跑一段 CodeAct；
TimeoutLocalExecutor（#149013）——调用方 deadline 返回（wall≈timeout）、超时 state
隔离与重建、draining 拒绝、并发拒绝、cleanup 语义。
"""

from __future__ import annotations

import threading
import time

import pytest

smolagents_local = pytest.importorskip("smolagents.local_python_executor")

from synapse.config import Config, ConfigError  # noqa: E402
from synapse.runtime.local_executor import (  # noqa: E402
    ExecutionTimeoutError,
    ExecutorDrainingError,
    TimeoutLocalExecutor,
)
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
    # 载荷必须是无界高开销循环：纯空转 `while True: pass` 约 2.5s 即耗尽 smolagents
    # 解释器的 1M 次迭代守卫（消息不含本断言的任一关键词），快机器上守卫先于 3s
    # wall-clock 超时触发——被测的强杀路径根本不执行且断言失败（本机实测竞态临界
    # 3/3 翻车）。每迭代分配 10MB 使 1M 次迭代需 ~10^3s 量级，任何平台均远超 3s，
    # 父进程强杀成为唯一出口；载荷增量峰值内存 20MB（重绑即释放，无累积），
    # 远低于默认 RLIMIT_AS 2048MB
    with pytest.raises(Exception, match="(?i)maximum execution time|subprocess killed"):
        ex("while True:\n    s = 'x' * 10000000")
    wall = time.monotonic() - t0
    assert wall >= ex.timeout_seconds, (
        f"强杀不得早于 wall-clock 超时点发生，实际 {wall:.2f}s < {ex.timeout_seconds}s"
    )
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


def test_subprocess_executor_del_semantics_matches_local():
    """评审 P3：代码内 del 的键跨步不可见（整体重建语义，与 local 档一致）。"""
    ex = SubprocessExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    ex("x = 1")
    out = ex("del x\nfinal_answer('deleted')")
    assert out.output == "deleted"
    with pytest.raises(Exception, match="(?i)not defined|failed"):
        ex("final_answer(x)")  # 原合并语义会残留父侧旧值 1 并送回


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


# ---------------- TimeoutLocalExecutor（Issue #149013：local 档调用方 deadline 超时） ----------------


def test_timeout_local_executor_final_answer_roundtrip():
    ex = TimeoutLocalExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    out = ex("x = 40 + 2\nfinal_answer(x)")
    assert out.is_final_answer is True
    assert out.output == 42


def test_timeout_local_executor_state_persists_across_steps():
    """与 subprocess 档同语义：step 间 state 保持（正常路径复用同一 inner）。"""
    ex = TimeoutLocalExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    ex.send_variables({"evidence": "alpha beta gamma"})
    out = ex("n = len(evidence.split())\nfinal_answer(n)")
    assert out.output == 3
    out2 = ex("final_answer(n * 10)")
    assert out2.output == 30


def test_timeout_local_executor_blocks_unauthorized_imports():
    ex = TimeoutLocalExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    with pytest.raises(Exception, match=r"(?i)not (?:allowed|authorized)|authorized import"):
        ex("import subprocess")


def test_timeout_local_executor_wall_approximates_timeout():
    """T1 修复核心断言：调用方 wall≈timeout（旧 bug：join 至代码自然结束 wall≈sleep）。"""
    ex = TimeoutLocalExecutor(timeout_seconds=2)
    ex.send_tools(_fa())
    t0 = time.monotonic()
    with pytest.raises(ExecutionTimeoutError, match="maximum execution time"):
        ex("import time as _t\n_t.sleep(6)\nfinal_answer('slept')")
    wall = time.monotonic() - t0
    assert wall >= 2 - 0.3, f"不得早于 deadline 返回，实际 {wall:.2f}s"
    # 上界 5s 能区分修复前（wall≈6s，sleep 自然结束）与修复后（wall≈2s）；
    # Windows 调度抖动余量 3s 实测充足
    assert wall < 5, f"调用方应在 deadline 附近返回，实际 {wall:.2f}s（旧 bug ≈6s）"


def test_timeout_local_executor_poisons_state_and_rejects_while_draining():
    """复审 P0：超时 inner 作废——旧线程存活期间拒绝新执行，不得复用被污染 state。"""
    ex = TimeoutLocalExecutor(timeout_seconds=2)
    ex.send_tools(_fa())
    with pytest.raises(ExecutionTimeoutError):
        ex("import time as _t\n_t.sleep(6)\nfinal_answer('slept')")
    # 旧线程（sleep 6s）仍存活：新调用显式拒绝（ExecutorDrainingError），而非静默并发
    with pytest.raises(ExecutorDrainingError, match="still running"):
        ex("final_answer('should be rejected')")
    # 旧线程自然结束后：丢弃旧 state 重建干净 inner，缓存 tools replay，恢复服务
    if ex.stale_thread is not None:
        ex.stale_thread.join(timeout=15)
    out = ex("final_answer('recovered')")
    assert out.output == "recovered"
    # 旧代码的迟到赋值（marker='stale'）不得泄漏进新 inner（state 隔离）
    with pytest.raises(Exception, match="(?i)not defined"):
        ex("final_answer(marker)")


def test_timeout_local_executor_delayed_write_does_not_pollute_new_inner():
    """复审 P0 延迟污染场景：旧代码迟到写入不得进入重建后的 inner。"""
    ex = TimeoutLocalExecutor(timeout_seconds=2)
    ex.send_tools(_fa())
    with pytest.raises(ExecutionTimeoutError):
        ex("import time as _t\n_t.sleep(4)\nmarker = 'stale'\nfinal_answer(marker)")
    if ex.stale_thread is not None:
        ex.stale_thread.join(timeout=15)
    # 若旧线程迟到赋值污染了新 inner，marker='stale' 可达 → final_answer 成功 → 本断言失败
    with pytest.raises(Exception, match="(?i)not defined"):
        ex("final_answer(marker)")
    # 重建后的实例重新可超时（状态机可循环，线程数有界：每次至多 1 个残留）
    with pytest.raises(ExecutionTimeoutError):
        ex("import time as _t\n_t.sleep(4)\nfinal_answer('again')")


def test_timeout_local_executor_rejects_concurrent_calls():
    ex = TimeoutLocalExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    holder = {}

    def _occupy():
        try:
            ex("import time as _t\n_t.sleep(1)\nfinal_answer('occupied')")
        except Exception as e:  # noqa: BLE001
            holder["err"] = e

    occupier = threading.Thread(target=_occupy)
    occupier.start()
    time.sleep(0.3)  # 等 occupier 进入执行
    # 并行 __call__ 显式拒绝（实例不支持并发；正常流水线为顺序调用）
    with pytest.raises(ExecutorDrainingError, match="concurrent"):
        ex("final_answer('parallel')")
    occupier.join(timeout=15)
    assert holder.get("err") is None  # 占用者正常完成


def test_timeout_local_executor_cleanup_blocks_further_calls():
    ex = TimeoutLocalExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    ex.cleanup()  # CodeAgent.cleanup() 探测该方法；不强杀线程，只阻断后续调用
    with pytest.raises(ExecutorDrainingError, match="closed"):
        ex("final_answer('after cleanup')")


def test_timeout_local_executor_state_property_diagnostic():
    ex = TimeoutLocalExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    ex("x = 1")
    assert "_print_outputs" in ex.state  # CodeAgent 异常诊断路径依赖该键（agents.py:1735）


def test_timeout_local_executor_worker_base_exception_fails_readably():
    """复审 P3：worker 被 BaseException（SystemExit 等）终止时主线程显式失败，不 KeyError。"""
    ex = TimeoutLocalExecutor(timeout_seconds=30)
    ex.send_tools(_fa())
    # worker 有意不转抛 BaseException（SystemExit 属进程控制流）——线程默认 excepthook
    # 会打日志，测试中临时静默
    orig_hook = threading.excepthook
    threading.excepthook = lambda args: None
    try:
        with pytest.raises(RuntimeError, match="without a result"):
            ex("raise SystemExit(3)")
    finally:
        threading.excepthook = orig_hook


def test_build_team_wires_timeout_local_executor_by_default():
    """#149013：local 档默认注入 TimeoutLocalExecutor（4 角色全部，独立实例）。"""
    from synapse.runtime.team import build_team

    team = build_team(Config())
    execs = [ag.python_executor for ag in team.agents()]
    assert all(isinstance(ex, TimeoutLocalExecutor) for ex in execs)
    assert len({id(ex) for ex in execs}) == 4  # 复审 P1-1：跨 Agent 不得共享
    assert all(ex.timeout_seconds == Config().codeact_timeout_s for ex in execs)


def test_codeagent_end_to_end_with_timeout_local_executor():
    """端到端：默认 local 档执行路径（TimeoutLocalExecutor）真跑 mock CodeAct。"""
    from smolagents import CodeAgent

    from synapse.runtime.model import MockChatModel

    agent = CodeAgent(
        tools=[],
        model=MockChatModel(role="executor", n_facts=4),
        name="executor_1",
        max_steps=3,
        verbosity_level=0,
        add_base_tools=False,
        executor=TimeoutLocalExecutor(timeout_seconds=30),
    )
    result = agent.run("count words", additional_args={"evidence": "w1 w2 w3 w4"})
    assert int(result) == 4

"""execute 角色生成失败重试 + 显式降级（Issue #149013 checklist 3）。

"0 静默"禁令（复审 P0）：降级时 metric=None（不是 0 哨兵——0 是完全合法的计算
结果，summarizer 只看 metric 会把失败当成有效计算）。outcome 经 EXECUTE 消息
result、summarizer additional_args/提示、顶层返回 dict、metrics 计数四处显式可见。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from ..prompts import execute_prompt

EXEC_RETRY_BUDGET = 1  # 生成/契约失败后的额外尝试次数（checklist：重试预算 ≥1）


@dataclass
class ExecOutcome:
    """execute 步骤的结构化结果（checklist 2/3：契约同步 + 显式降级）。"""

    metric: int | None  # None=计算不可用（降级）；严格非 0 哨兵
    status: str  # "ok" | "degraded"
    retries: int  # 外层额外尝试次数（首次成功=0；不含 smolagents agent 内部 step 重试）
    failure_kind: str | None  # "exception" | "type_contract" | "non_int_final_answer" | "mixed" | None

    def as_dict(self) -> dict:
        return asdict(self)


def _as_contract_int(value) -> int | None:
    """严格返回契约：非负 int（type(value) is int，排除 bool/float/str/负值）。

    静默转换（"42"→42、5.0→5）会掩盖模型违反 final_answer 整数契约的事实，
    使契约测试名义通过而模型行为未修正——按契约失败计，触发重试/降级。
    """
    return value if type(value) is int and value >= 0 else None


def run_executor_with_retry(execu, task, evidence) -> tuple[ExecOutcome, str]:
    """运行 execute 角色 CodeAgent；失败按预算重试；预算耗尽显式降级。

    返回 (ExecOutcome, failure_summary)。failure_summary 供 EXECUTE 消息 meta
    如实记录失败原因（异常类型/契约违反），不进 result envelope（spill 语义保持
    计算结果本身）。

    注意（口径如实声明）：本函数的 retries 只计**应用层**的 execu.run() 额外尝试；
    smolagents CodeAgent 内部 max_steps 的 step 级重试不在此计数。单次 executor
    调用方的 deadline 由执行器档位保证（#149013），不承诺整个任务 wall≤timeout。
    """
    failures: list[str] = []
    kinds: list[str] = []  # 保序去重：混合失败（如契约错后又异常）如实标 "mixed"
    for attempt in range(1 + EXEC_RETRY_BUDGET):
        try:
            res = execu.run(execute_prompt(task), reset=True, additional_args={"evidence": evidence})
        except Exception as e:  # noqa: BLE001 — 生成失败面（InterpreterError/超时等）统一计一次尝试
            failures.append(f"attempt{attempt}: {type(e).__name__}: {e}")
            if "exception" not in kinds:
                kinds.append("exception")
            continue
        metric = _as_contract_int(res)
        if metric is None:
            # 复审 P2-1：str 通常是超时/步数耗尽后 smolagents provide_final_answer 的文本
            # 兜底（agents.py:628-640），单列口径，不与真正的类型契约违反混标
            kind = "non_int_final_answer" if isinstance(res, str) else "type_contract"
            failures.append(f"attempt{attempt}: {kind}({type(res).__name__})")
            if kind not in kinds:
                kinds.append(kind)
            continue
        return ExecOutcome(metric=metric, status="ok", retries=attempt, failure_kind=None), ""
    return (
        ExecOutcome(
            metric=None,
            status="degraded",
            retries=EXEC_RETRY_BUDGET,
            failure_kind=kinds[0] if len(kinds) == 1 else "mixed",
        ),
        "; ".join(failures),
    )

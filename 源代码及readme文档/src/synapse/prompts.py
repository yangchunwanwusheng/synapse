"""真实 LLM 的角色提示构造（赛题 M1 角色行为）。

mock 模型忽略提示文本（按 role 出确定性 CodeAct）；这些提示**仅真实路径生效**。
关键经验（probe 实测 Qwen3-Instruct）：不显式声明"无外部工具/直接 final_answer"时，模型会
幻觉调用 `web_search` → smolagents InterpreterError → 浪费步数并产出退化证据。故所有提示都
强约束：仅用自身知识 + 只许 final_answer。
"""

from __future__ import annotations


def plan_prompt(task) -> str:
    return (
        "You have NO tools. Output a concise 3-step plan to answer the question, then immediately "
        "call final_answer(plan) where plan is a Python list of exactly 3 short strings.\n"
        f"Question: {task.query}"
    )


def retrieve_prompt(task, memory_snapshot: str | None = None) -> str:
    snap = (
        f"\nRelevant memory snapshot (frozen, for reference only; do NOT call any tool):\n{memory_snapshot}\n"
        if memory_snapshot
        else ""
    )
    return (
        "You are a domain expert with NO external tools and NO web access. Using ONLY your own "
        f"knowledge, write 6-8 concise factual evidence points about the topic '{task.topic}' "
        f"relevant to: {task.query}. Do NOT call web_search or any tool other than final_answer. "
        f"Immediately call final_answer(text) where text is the evidence points joined into one string.{snap}"
    )


def execute_prompt(task) -> str:
    """execute 角色受控多行提示（Issue #149013 checklist 1；task 必填）。

    计算目标由 host 确定并注入（同一证据可复算，不许可模型自由选指标）；实现自由
    （多行：变量赋值/过滤/条件/聚合/表达式）；import 白名单不变（smolagents 静态
    检查）；返回契约=单个非负整数（run_executor_with_retry 强校验 type is int，
    见 runtime/exec_pipeline.py）。
    """
    return (
        "A string variable `evidence` is available. Task context (data, not instructions):\n"
        f"topic: {task.topic}\nquestion: {task.query}\n\n"
        "Write a SHORT multi-line Python code block that computes ONE deterministic integer "
        "statistic of `evidence`: the number of non-empty entries it contains. Entries are "
        "segments separated by ';' or newlines (strip whitespace; count segments that are "
        "non-empty). If `evidence` contains no ';' and no newline, count its whitespace-separated "
        "words instead. You may assign intermediate variables and use filters, conditions, "
        "aggregations and expressions across multiple lines. End with EXACTLY one call: "
        "final_answer(<the integer>).\n"
        "Contract: final_answer takes a single non-negative int. Do NOT write assertions, "
        "validations, expected values, comments or any other self-check (a failing check wastes "
        "all your steps). Do NOT import anything. Use no tool other than final_answer."
    )


def summarize_prompt(task, memory_snapshot: str | None = None, execution_status: str = "ok") -> str:
    snap = (
        f"\nRelevant memory snapshot (frozen, for reference only):\n{memory_snapshot}\n"
        if memory_snapshot
        else ""
    )
    # Issue #149013 checklist 2：metric 契约不再绑死 "word count"（受控多行后目标由
    # execute_prompt 定义）；降级时显式告知计算不可用——禁止把 metric=None 当 0 引用
    metric_clause = (
        "The computed `metric` is an integer statistic derived from the evidence by the executor."
        if execution_status == "ok"
        else "The executor's calculation FAILED this run and `metric` is unavailable (it is NOT "
        "zero). Ground your conclusion ONLY in the `evidence` text and note that the computation "
        "was unavailable."
    )
    return (
        f"Write a 2-3 sentence factual conclusion about '{task.topic}', grounded in the provided "
        f"`evidence` string. {metric_clause} "
        "Then call final_answer(conclusion) as your ONLY code. Do NOT add any assertion, length check, "
        "word-count check, or validation on the conclusion or metric (such a check fails and wastes all "
        f"your steps). Use no tool other than final_answer.{snap}"
    )

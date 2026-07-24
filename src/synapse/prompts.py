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


def execute_prompt() -> str:
    return (
        "A string variable `evidence` (text) is available. Write EXACTLY one line of code and nothing "
        "else: final_answer(len(evidence.split())). Do NOT write assertions, validations, expected "
        "values, comments, or any other statement (a self-check that fails wastes all your steps). "
        "Use no tool other than final_answer."
    )


def summarize_prompt(task, memory_snapshot: str | None = None) -> str:
    snap = (
        f"\nRelevant memory snapshot (frozen, for reference only):\n{memory_snapshot}\n"
        if memory_snapshot
        else ""
    )
    return (
        f"Write a 2-3 sentence factual conclusion about '{task.topic}', grounded in the provided "
        "`evidence` string and the computed `metric` (an integer word count). "
        "Then call final_answer(conclusion) as your ONLY code. Do NOT add any assertion, length check, "
        "word-count check, or validation on the conclusion or metric (such a check fails and wastes all "
        f"your steps). Use no tool other than final_answer.{snap}"
    )

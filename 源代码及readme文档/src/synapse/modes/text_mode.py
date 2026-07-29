"""纯文本协作模式（赛题 M3 基线）= smolagents 原生文本介质。

4 个 smolagents CodeAgent 协作，中间证据以**全量自然语言文本**跨 agent 透传、无共享记忆、
无非文本残差——这是受管 agent 的默认行为，作为公认基线与 synapse 模式对照（同拓扑，差异仅介质）。
"""

from __future__ import annotations

import time

from ..runtime.team import build_team
from ..protocol.messages import Message, ActionType
from ..protocol.handshake import CNR
from ..protocol.scheduler import Scheduler
from ..eval.metrics import Metrics
from ..prompts import plan_prompt, retrieve_prompt, execute_prompt, summarize_prompt


def run_text(task, cfg, team=None) -> dict:
    team = team or build_team(cfg)  # 无状态：默认每任务新建团队
    team.bind_topic(task.topic)
    m = Metrics(mode="text")
    sched = Scheduler(team.agents(), cnr=CNR(), metrics=m)
    planner = sched.agent("planner")
    retr = sched.agent("retriever")
    execu = sched.agent("executor")
    summ = sched.agent("summarizer")

    tok0 = team.llm_tokens()
    ti0, to0 = team.token_io()  # 新口径（M8 真实通信成本）
    t0 = time.perf_counter()

    # 计划（结构化 + 文本透传）
    plan = planner.run(plan_prompt(task), reset=True)
    plan_list = plan if isinstance(plan, (list, tuple)) else [str(plan)]  # 真实 LLM 可能返回字符串
    sched.send(
        Message(
            sched.next_msg_id(),
            planner.agent_id,
            retr.agent_id,
            ActionType.PLAN.value,
            params={"n_steps": len(plan_list)},
            payload_kind="text",
            text="; ".join(str(s) for s in plan_list),
        )
    )

    # 检索证据 → 执行器同源消费（真·CodeAct）→ 结果回传
    evidence = retr.run(retrieve_prompt(task), reset=True)
    exec_res = execu.run(execute_prompt(), reset=True, additional_args={"evidence": evidence})
    sched.send(
        Message(
            sched.next_msg_id(),
            execu.agent_id,
            summ.agent_id,
            ActionType.EXECUTE.value,
            result={"metric": exec_res},
            payload_kind="text",
            text=f"exec_result={exec_res}",
        )
    )
    # 证据全量文本透传给总结器（基线冗余来源；synapse 模式此处改走残差）
    sched.send(
        Message(
            sched.next_msg_id(),
            retr.agent_id,
            summ.agent_id,
            ActionType.TELL.value,
            payload_kind="text",
            text=evidence,
        )
    )
    # 使用环：text 基线下证据以全量文本透传到总结器（线缆冗余来源），总结器据此 + metric 出结论
    conclusion = summ.run(
        summarize_prompt(task), reset=True, additional_args={"evidence": evidence, "metric": exec_res}
    )

    m.latency_s = time.perf_counter() - t0
    m.llm_tokens = team.llm_tokens() - tok0
    ti, to = team.token_io()
    m.llm_input_tokens = ti - ti0
    m.llm_output_tokens = to - to0
    m.quality = 1.0 if conclusion else 0.0
    return {"metrics": m, "conclusion": conclusion}

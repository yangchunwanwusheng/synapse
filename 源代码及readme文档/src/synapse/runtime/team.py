"""smolagents 多 Agent 团队（赛题 M1；替换原 runtime/roles.py）。

4 角色 = 4 个 smolagents CodeAgent（真·CodeAct → M11）：Planner / Retriever / Executor / Summarizer。
每个 agent 附 role / agent_id / cap（Capability），使既有 protocol.Scheduler + CNR 无改动复用。
Agent 间通信、非文本状态传递、共享记忆由 protocol+stateplane+memory 平面负责（我们的创新面）。
"""

from __future__ import annotations

from dataclasses import dataclass

from smolagents import CodeAgent

from .model import MockChatModel, make_model
from ..protocol.messages import Capability

# role, agent_id, actions, description
_ROLES = (
    ("planner", "planner-1", ("PLAN",), "把任务拆成检索/计算/总结步骤"),
    ("retriever", "retriever-1", ("RETRIEVE", "TELL", "ASK"), "检索并返回主题证据"),
    ("executor", "executor-1", ("EXECUTE",), "在受限解释器中对证据做计算 (CodeAct)"),
    ("summarizer", "summarizer-1", ("SUMMARIZE", "WRITE"), "综合证据与计算结果给出结论"),
)


def _cap(agent_id: str, role: str, actions: tuple[str, ...]) -> Capability:
    # §2.2 Executor 声明可被运行时探测的 codeact_sandbox 能力（CNR 握手时 check_fn 实测；
    # 标识符沿用协议名，语义=CodeAct 执行能力，不代表安全沙箱承诺）
    probe = ("codeact_sandbox",) if role == "executor" else ()
    return Capability(
        agent_id=agent_id,
        role=role,
        actions=actions,
        encodings=("text", "embedding", "residual"),
        model_family="mock-family",
        probe=probe,
    )


def _make_verify_check_fn(cfg=None):
    """§2.2 能力验证 check_fn：对 cap.probe 声明的 codeact_sandbox 做真实探针执行（握手期探测记录）。

    V3-08（Issue #148750）前为"声明即已验证"（直接返回声明集合）——彻查报告批评口径：
    能力发现应成为可验证承诺。现在首调即真跑一段最小 CodeAct（``final_answer(2 ** 10)``）
    并核对结果：local 档在进程内求值，subprocess 档拉起一次隔离子进程（与该档真实执行
    路径同构）。探针失败 → 返回空集（该能力诚实不通过验证）；探针异常不外泄（按未验证计）。

    边界如实声明（复审修正）：
    - 该探针只证明**最小 CodeAct 执行可用**，不验证超时强杀/RLIMIT/隔离属性，也不
      gate 后续 execu.run()（verified 结果当前仅作为 CNR 握手的验证记录，不改变执行路由）；
    - 记忆化生命周期=本闭包=本 run_task 的 Scheduler/CNR（synapse_mode 每任务重建），
      即**每个任务的 hello 周期探测一次**（TTL 300s 在单任务内不会过期）；subprocess 档
      每任务多一次子进程冷启动（实测约 1.6s，见 docs/工程化基线.md）。
    """
    memo: dict[str, set[str]] = {}

    def _probe_executor() -> bool:
        from smolagents.local_python_executor import LocalPythonExecutor

        if cfg is not None and getattr(cfg, "codeact_executor", "local") == "subprocess":
            from .subprocess_executor import SubprocessExecutor

            ex = SubprocessExecutor(timeout_seconds=max(10, getattr(cfg, "codeact_timeout_s", 30)))
        else:
            ex = LocalPythonExecutor(additional_authorized_imports=[])
        ex.send_tools({"final_answer": lambda *a: a[0] if len(a) == 1 else (a or None)})
        out = ex("final_answer(2 ** 10)")
        return bool(out.is_final_answer) and out.output == 1024

    def _check(cap: Capability) -> set[str]:
        if "codeact_sandbox" not in memo:
            try:
                memo["codeact_sandbox"] = {"codeact_sandbox"} if _probe_executor() else set()
            except Exception:  # noqa: BLE001 — 探针失败按未验证计，不炸握手
                memo["codeact_sandbox"] = set()
        return memo["codeact_sandbox"] & set(cap.probe)

    return _check


@dataclass
class Team:
    planner: CodeAgent
    retriever: CodeAgent
    executor: CodeAgent
    summarizer: CodeAgent
    caps: dict[str, Capability]

    def agents(self) -> list[CodeAgent]:
        return [self.planner, self.retriever, self.executor, self.summarizer]

    def bind_topic(self, topic: str) -> None:
        """每任务前注入 topic（仅 mock 模型用于确定性内容生成）。"""
        for ag in self.agents():
            if isinstance(ag.model, MockChatModel):
                ag.model.topic = topic

    def llm_tokens(self) -> int:
        """累计 LLM 输出 token（M8，向后兼容旧合成管线）。"""
        return self.token_io()[1]

    def token_io(self) -> tuple[int, int]:
        """累计 LLM (输入, 输出) token —— 真实通信成本口径（M8 通信效率）。

        mock 读 input_tokens/output_tokens；真实模型读累计计数器（CountingOpenAIServerModel）。
        模型对象跨 agent.run(reset=True) 持久，故计数正确（不读会被 reset 清零的 monitor）。
        """
        ti = to = 0
        for ag in self.agents():
            mdl = ag.model
            to += int(getattr(mdl, "output_tokens", 0) or 0)
            ti += int(getattr(mdl, "input_tokens", 0) or 0)
        return ti, to


def build_team(cfg) -> Team:
    """构造 4 角色 smolagents 团队（同配置后端）。

    V3-08：codeact_executor="subprocess" 时注入进程级隔离执行器（超时可强杀 + POSIX
    资源限制）；默认 "local" 保持进程内受限解释器（历史口径，零回归）。

    复审 P1-1 修正：**每 Agent 独立 executor 实例**（与 local 档每 CodeAgent 各自
    create_python_executor 的隔离语义对齐）——共享实例会让一个角色的 CodeAct 变量
    残留进其他角色的 state（跨 Agent 串扰，已实测复现并补隔离测试）。
    注意：注入自定义 executor 时 CodeAgent 的 additional_authorized_imports /
    max_print_outputs_length 参数不被消费（smolagents 仅在自建路径读取）；当前
    两档均取默认值（[]/None→50000），语义一致。
    """
    use_subprocess = getattr(cfg, "codeact_executor", "local") == "subprocess"
    agents: dict[str, CodeAgent] = {}
    caps: dict[str, Capability] = {}
    for role, agent_id, actions, desc in _ROLES:
        executor = None
        if use_subprocess:
            from .subprocess_executor import SubprocessExecutor

            executor = SubprocessExecutor(
                timeout_seconds=cfg.codeact_timeout_s,
                memory_limit_mb=cfg.codeact_memory_mb,
                cpu_seconds=cfg.codeact_cpu_s,
            )
        agent = CodeAgent(
            tools=[],
            model=make_model(cfg, role),
            name=agent_id.replace("-", "_"),
            description=desc,
            max_steps=3,
            verbosity_level=0,
            add_base_tools=False,
            executor=executor,
        )
        cap = _cap(agent_id, role, actions)
        # 附身份属性，复用既有 Scheduler/CNR（它们按 .role/.agent_id/.cap 寻址）
        agent.agent_id = agent_id
        agent.role = role
        agent.cap = cap
        agents[role] = agent
        caps[role] = cap
    return Team(agents["planner"], agents["retriever"], agents["executor"], agents["summarizer"], caps)

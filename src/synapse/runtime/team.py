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
    ("executor", "executor-1", ("EXECUTE",), "在代码沙箱中对证据做计算 (CodeAct)"),
    ("summarizer", "summarizer-1", ("SUMMARIZE", "WRITE"), "综合证据与计算结果给出结论"),
)


def _cap(agent_id: str, role: str, actions: tuple[str, ...]) -> Capability:
    return Capability(
        agent_id=agent_id,
        role=role,
        actions=actions,
        encodings=("text", "embedding", "residual"),
        model_family="mock-family",
    )


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
    """构造 4 角色 smolagents 团队（同配置后端）。"""
    agents: dict[str, CodeAgent] = {}
    caps: dict[str, Capability] = {}
    for role, agent_id, actions, desc in _ROLES:
        agent = CodeAgent(
            tools=[],
            model=make_model(cfg, role),
            name=agent_id.replace("-", "_"),
            description=desc,
            max_steps=3,
            verbosity_level=0,
            add_base_tools=False,
        )
        cap = _cap(agent_id, role, actions)
        # 附身份属性，复用既有 Scheduler/CNR（它们按 .role/.agent_id/.cap 寻址）
        agent.agent_id = agent_id
        agent.role = role
        agent.cap = cap
        agents[role] = agent
        caps[role] = cap
    return Team(agents["planner"], agents["retriever"], agents["executor"], agents["summarizer"], caps)

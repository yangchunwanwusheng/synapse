"""① 多 Agent 运行时（赛题 M1）—— 基座 = HuggingFace smolagents。

4 角色 = 4 个 smolagents CodeAgent（真·CodeAct=M11）：Planner / Retriever / Executor / Summarizer。
模型层 MockChatModel(离线) / OpenAIServerModel(SiliconFlow 真实路径)。见 docs/基座选型决策.md。
"""

from .model import MockChatModel, make_model
from .team import Team, build_team

__all__ = ["MockChatModel", "make_model", "Team", "build_team"]

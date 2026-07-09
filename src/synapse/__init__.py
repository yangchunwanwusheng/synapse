"""SYNAPSE — 面向多智能体协作的低开销通信、非文本状态传递与共享记忆原型系统。

五大模块（见 docs/系统设计文档.md）：
- runtime   : 多 Agent 运行时（基座 = HuggingFace smolagents；4 个 CodeAgent + 模型层抽象）
- protocol  : 结构化通信协议、CNR 握手/能力发现、调度
- stateplane: 状态交换数据平面（CAS / 预测残差编码 / 校验和）—— 非文本状态传递核心
- memory    : 共享记忆单元 + 混合检索 + 预测基 + 巩固器
- eval      : 双模式 A/B 评测与度量

基座 smolagents（轻依赖、CodeAct 原生=M11）；离线路径用 MockChatModel + HashEmbedder（确定性、零网络）可 CI；
真实实验路径（Paratera 算力平台 via OpenAIServerModel + sentence-embedding）为可选 extras。
"""

__version__ = "0.1.0"

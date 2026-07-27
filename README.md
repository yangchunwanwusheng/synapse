<div align="center">

# SYNAPSE

### 面向多智能体协作的低开销通信、非文本状态传递与共享记忆原型

**结构化通信 · 语义残差交换 · 跨任务记忆复用 · 可复现实验**

</div>

> 第三届中国研究生操作系统开源创新大赛社区赛题作品。SYNAPSE 将多 Agent 协作理解为一个“信息压缩与状态复用”问题：用结构化协议替代冗长文本透传，用非文本语义状态减少重复编码，并把可复用经验沉淀为共享记忆。

## 作品概览

传统多 Agent 系统常把中间状态反复转换为自然语言，再由下游 Agent 重新解析。上下文越长、轮次越多，重复传输与重复计算越明显。SYNAPSE 提供一条可运行、可对照、可度量的机制路径：

- **低开销通信**：统一 `Message` 协议承载动作、参数、结果和能力描述，提供 CNR 握手、能力发现与调度。
- **非文本状态传递**：把中间语义编码为向量，以预测残差、量化稀疏表示和 CAS 句柄完成传递；校验不通过时回退文本路径。
- **共享记忆复用**：统一 `MemoryUnit` 元数据，通过关键词、标签和语义相似度混合检索，支持跨 Agent、跨任务复用。
- **同条件 A/B 评测**：在相同任务上运行纯文本基线与 SYNAPSE 模式，记录消息数、token/字节、非文本载荷、时延、记忆命中率和答案质量。

## 系统架构

![SYNAPSE 多智能体低开销协作架构](assets/architecture.drawio.png)

一次协作的主路径如下：

1. 编排器将复杂任务分解给 Planner、Retriever、Executor 与 Summarizer。
2. Agent 通过 CNR 完成握手和能力发现，协作信息收敛为结构化 `Message`。
3. 中间语义状态被编码为 embedding；发送方基于预测状态计算残差，量化并稀疏化后写入 CAS，消息只传递内容句柄。
4. 接收方取回非文本载荷并重构语义状态，通过校验后继续使用；失败则回退到文本，保证正确性边界。
5. 证据、摘要、策略与结论写入共享记忆；后续关联任务通过混合检索直接复用。
6. 评测模块在同任务、同配置下对比纯文本模式和 SYNAPSE 模式。

## 核心模块

| 模块 | 主要职责 | 代码位置 |
|---|---|---|
| 多 Agent 运行时 | 四类角色、任务编排、CodeAct 执行与模型抽象 | `src/synapse/runtime/` |
| 协议解析与调度 | 结构化消息、CNR 握手、能力发现与调度 | `src/synapse/protocol/` |
| 非文本状态交换 | embedding、预测残差、稀疏量化、校验和 CAS | `src/synapse/stateplane/` |
| 共享记忆与检索 | 记忆单元、混合检索、跨任务巩固与演化 | `src/synapse/memory/` |
| 双模式与评测 | 纯文本/SYNAPSE 双模式、A/B 运行与指标聚合 | `src/synapse/modes/`、`src/synapse/eval/` |
| 真实数据集管线 | CoQA、HotpotQA、MuSiQue 数据加载、检索与评分 | `src/synapse/qa/` |

## 赛题要求对齐

| 赛题要求 | SYNAPSE 实现 | 可检查入口 |
|---|---|---|
| 不少于 3 个 Agent、覆盖不少于 3 类角色 | Planner / Retriever / Executor / Summarizer 四角色 | `src/synapse/runtime/team.py` |
| 动作、参数、结果、能力的结构化通信 | `Message{action, params, result, capability}` | `src/synapse/protocol/messages.py` |
| 握手、能力发现或协议映射 | CNR 握手与调度器 | `src/synapse/protocol/handshake.py`、`src/synapse/protocol/scheduler.py` |
| 纯文本与结构化模式同任务对比 | `text` / `synapse` 双模式，`ab` 命令统一运行 | `src/synapse/modes/`、`src/synapse/eval/harness.py` |
| 非文本中间状态直接交换 | embedding + 预测残差 + CAS 句柄 + 校验回退 | `src/synapse/stateplane/` |
| 统一共享记忆单元 | ID、来源 Agent、创建时间、任务主题、摘要等元数据 | `src/synapse/memory/store.py` |
| 关键词、标签、语义相似度检索 | 三路加权混合检索 | `src/synapse/memory/retrieval.py` |
| 两组关联连续任务 | G1 主题深挖、G2 关联演进并复用 G1 记忆 | `src/synapse/tasks.py`、`synapse m7` |
| 完整效率指标 | 消息、文本 token/字节、非文本次数/字节、时延、命中率、质量 | `src/synapse/eval/metrics.py` |
| 稳定执行不少于 10 轮 | `synapse ab --rounds 10` | `tests/`、CLI |
| openEuler 24.03-LTS 运行 | openEuler 基础镜像、非 root 用户、离线健康检查 | `Dockerfile` |
| CodeAct 执行机制 | 基于 smolagents `CodeAgent` 的 Executor | `src/synapse/runtime/team.py` |

## 快速开始

### 1. 本机离线自检

环境要求：Python 3.11+，推荐使用 [uv](https://docs.astral.sh/uv/)。离线模式使用 mock LLM 与确定性 `HashEmbedder`，不需要 API Key。Windows 若把仓库放在含中文字符的路径下，建议使用 Python 3.13+，以避免旧版本 Python 读取可编辑安装路径时受系统编码影响。

```bash
uv sync
uv run synapse smoke
```

成功时末行应为：

```text
SMOKE PASSED
```

### 2. 运行 10 轮双模式对比

```bash
uv run synapse ab --rounds 10 --config configs/default.yaml
```

该命令在同一组连续任务上分别运行纯文本模式和 SYNAPSE 模式，并输出两侧轨迹、汇总指标、通信节省比例与非文本字节收缩轨迹。

### 3. 运行测试

```bash
uv sync --extra dev
uv run pytest -q
```

测试覆盖残差编解码与回退、共享记忆写入/演化/检索、双模式执行、连续任务复用、三档协议统计以及三类真实数据集管线。

## openEuler / Docker 复现

镜像基于 `openeuler/openeuler:24.03-lts`，默认执行无需网络和密钥的离线自检。

项目环境验证分为两个阶段：项目初期在大赛指定 openEuler 环境对应的 Docker 容器中完成基础编译、运行与测试；项目后期迁移至安装 **openEuler 24.03-LTS-SP3** 的真实服务器，并在原生操作系统环境中重新完成编译、运行和测试。

```bash
docker build -t synapse:latest .
docker run --rm synapse:latest
```

也可使用 Compose：

```bash
docker compose run --rm synapse
```

容器以非 root 用户运行，并通过同一 `synapse smoke` 命令执行健康检查。

## 真实模型与数据集实验

真实路径支持 OpenAI 兼容接口。密钥只在运行时注入，禁止写入配置或提交到仓库。

```bash
cp .env.example .env
# 在 .env 中填写 VECTORENGINE_API_KEY

uv sync --extra api
uv run synapse probe --config configs/vectorengine.yaml
uv run synapse signal --config configs/vectorengine.yaml --rounds 5
uv run synapse m7 --config configs/vectorengine.yaml --g1 5 --g2 5
uv run synapse hotpot --config configs/vectorengine.yaml --n 10
uv run synapse musique --config configs/vectorengine.yaml --n 3 --retrieval twohop
uv run synapse coqa --config configs/vectorengine.yaml --convs 3
```

仓库中的 `data/` 是固定的小规模评测样本，便于评审直接复现；抓取脚本位于 `scripts/`。运行结果默认写入本地 `runs/`，该目录不纳入版本控制。

## 实验快照

以下结果来自固定配置的一次真实 API 小样本实验，主要用于验证机制链路，不作为大样本统计结论：

| 数据集 | 样本规模 | 检索设置 | LLM token 节省 | text F1 | SYNAPSE F1 | 金标召回/命中 |
|---|---:|---|---:|---:|---:|---:|
| HotpotQA | 10 | single, k=3 | 71.09% | 0.780 | 0.680 | 0.900 |
| MuSiQue | 3 | twohop, k=3 | 80.90% | 0.524 | 0.857 | 0.667 |
| CoQA | 3 段对话 | 句级检索 | 10.65% | 0.656 | 0.684 | 0.921 |

机制消融中，有共享记忆时非文本残差从 `2787 B` 收缩至 `960 B`；清空记忆后仅从 `2772 B` 变化至 `2727 B`。这说明在该实验配置下，残差收缩主要来自跨任务记忆复用，而不是简单减少工作步骤。

> 结果解读应同时关注效率与质量。HotpotQA 小样本中虽然 token 显著下降，但 F1 同时下降 0.10；因此本项目不会把“通信更省”表述为无条件的质量提升。完整复现实验应扩大样本量、固定随机种子，并报告均值、方差和配对置信区间。

## 目录结构

```text
synapse/
├── assets/                    # README 架构图（内嵌 draw.io 源数据）
├── configs/                   # 离线与真实后端配置
├── data/                      # 固定的小规模评测样本
├── scripts/                   # 数据抓取与参数扫描脚本
├── src/synapse/
│   ├── runtime/               # 多 Agent 运行时
│   ├── protocol/              # 协议、握手与调度
│   ├── stateplane/            # 非文本状态交换
│   ├── memory/                # 共享记忆与检索
│   ├── modes/                 # 纯文本 / SYNAPSE 双模式
│   ├── eval/                  # 指标与 A/B 评测
│   └── qa/                    # 真实数据集实验管线
├── tests/                     # 离线测试与 QA 管线测试
├── Dockerfile                 # openEuler 24.03-LTS 镜像
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

## 关键设计取舍

- **结构化控制面，非文本数据面**：小而稳定的协议字段负责协作控制，embedding 与残差载荷负责高密度状态交换。
- **预测残差而非全量向量**：接收方已有预测基时只传变化部分；任务经验越可复用，残差通常越小。
- **CAS 句柄而非重复载荷**：相同内容按摘要寻址，消息仅携带句柄，减少重复复制。
- **校验失败允许回退**：有损压缩不能牺牲正确性边界；重构未通过校验时退回文本路径并计入指标。
- **机制与模型解耦**：离线 mock 用于确定性验收，真实后端通过配置接入，避免把结果绑定到单一模型服务。

## 当前边界

- 当前 CAS 是进程内内容寻址存储，重点验证句柄化传递与去重语义；它不是分布式对象存储，也不声称实现跨主机共享内存。
- 离线 mock 用于验证控制流和指标管线，不能替代真实模型质量评估。
- README 中的小样本结果用于机制验证；正式统计结论需要更大的样本、重复实验和置信区间。

## 安全与复现约定

- `.env`、密钥、证书、个人信息与本地运行产物均不进入版本库。
- 真实实验建议固定 `temperature=0`、数据样本、检索参数和随机种子。
- 提交前可运行 `uv run pytest -q` 与 `git status --short`，确认测试通过且仓库中无运行产物。

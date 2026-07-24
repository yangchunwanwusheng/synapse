# SYNAPSE — 面向多智能体协作的低开销通信、非文本状态传递与共享记忆原型系统

> 社区赛题《一种面向多智能体协作的低开销通信、状态传递与共享记忆机制》参赛作品。
>
> 围绕赛题三大方向——**低开销通信、非文本状态传递、共享记忆复用**——设计并实现一套可运行的多 Agent 协作原型系统，在真实 LLM 后端上验证其相较纯文本协作在通信开销、任务时延和记忆复用方面的改进。

赛题原文见 [`竞赛赛题.md`](竞赛赛题.md)；系统设计见 [`docs/系统设计文档.md`](docs/系统设计文档.md)；部署见 [`docs/部署文档.md`](docs/部署文档.md)。

---

## 赛题要求对齐

| 要求 | 本系统实现 | 证据 |
|---|---|---|
| **M1** ≥3 Agent，覆盖规划/检索/执行/总结中 ≥3 类 | 4 角色 CodeAgent：Planner / Retriever / Executor / Summarizer | `src/synapse/runtime/team.py` |
| **M2** 结构化通信协议（动作/参数/结果/能力 + 握手/能力发现） | `Message{action,params,result,capability}` + CNR 握手 + `Capability` 能力发现 | `src/synapse/protocol/` |
| **M3** 纯文本模式 + 结构化协议模式，同任务可复现对比 | `text` / `synapse` 双模式，`ab` 命令同任务对照 | `src/synapse/modes/` |
| **M4** 非文本中间状态传递（embedding/语义向量/隐藏状态） | 句向量预测残差编码 + CAS 句柄零拷贝传递 + 校验回退 | `src/synapse/stateplane/` |
| **M5** 共享记忆单元（记忆 ID/来源 Agent/创建时间/任务主题/摘要） | `MemoryUnit` 五项元数据齐全 + 内容寻址去重 | `src/synapse/memory/store.py` |
| **M6** 关键词/标签/语义相似度检索 + 跨任务复用 | 三路混合检索（keyword + tag + semantic cosine） | `src/synapse/memory/retrieval.py` |
| **M7** ≥2 组关联性连续任务 | G1（主题深挖）+ G2（关联演进，复用 G1 记忆）+ 负例族 | `src/synapse/tasks.py` |
| **M8** 通信开销/时延/记忆命中率统计 | 消息次数、文本 token/字节、非文本字节、时延、命中率 | `src/synapse/eval/harness.py` |
| **M9** 五模块架构 + ≥10 轮连续任务 + 完整交付 | 运行时/协议/状态交换/记忆/评测五模块；smoke 跑 10 轮 | 见下方架构 |
| **M10** openEuler 24.03-LTS 可编译运行 | Dockerfile + docker-compose 实测通过 | `Dockerfile` |
| **M11** 鼓励 CodeAct 沙箱执行 | Executor 走 CodeAct 生成可执行 Python | `src/synapse/runtime/team.py` |

---

## 系统架构（五模块）

| 模块 | 目录 | 职责 |
|---|---|---|
| ① 多 Agent 运行时 | `src/synapse/runtime/` | 基座 **smolagents**：4 个 CodeAgent（Planner/Retriever/Executor·CodeAct/Summarizer）+ 模型层抽象 |
| ② 协议解析与调度 | `src/synapse/protocol/` | 结构化 `Message` + CNR 握手/能力发现 + 调度器 |
| ③ 状态交换·数据平面 | `src/synapse/stateplane/` | CAS 内容寻址存储 + 句向量预测残差编码 + 校验和（非文本传递核心） |
| ④ 共享记忆与检索 | `src/synapse/memory/` | 记忆单元 + 混合检索 + 预测基 + 跨任务巩固 |
| ⑤ 评测与度量 | `src/synapse/eval/` | 双模式 A/B + 字节/时延/命中率统计 |

**数据流**：发送方 Agent 产出中间结果 → 经 `protocol` 打包为结构化消息（非文本载荷写入 `stateplane` 的 CAS，消息只带句柄）→ 接收方 Agent 通过句柄取回非文本状态、用预测基重构完整表示 → `memory` 沉淀为可检索记忆单元供后续任务复用 → `eval` 全程统计通信开销。

---

## 快速开始

```bash
# 用 uv 安装依赖（推荐）
uv sync                                  # 装基座 smolagents
uv run synapse smoke                     # 离线自检（无需联网/API key），打印 PASS/FAIL
uv run synapse ab --rounds 10            # 双模式 A/B（10 轮连续任务）
uv run python tests/test_smoke.py        # 单元/smoke 测试（或 uv run --extra dev pytest）

# 国内加速（不改全局）：uv sync --default-index https://pypi.tuna.tsinghua.edu.cn/simple
```

`smoke` 在离线 mock 下验证五件事并打印 PASS/FAIL：
1. 双模式都产出结论
2. synapse 模式省线缆字节
3. 关联任务记忆命中
4. 末轮非文本字节 ≤ 首轮（随经验下降）
5. 负例族命中率 < 关联族（区分度）

---

## 双模式对比（赛题 M3）

| | text 模式（基线） | synapse 模式 |
|---|---|---|
| 通信媒介 | 全量自然语言透传 | 结构化消息 + 残差句柄 |
| 中间状态 | 内部态→文本→内部态 | 句向量预测残差直传 |
| 共享记忆 | 无 | 记忆单元 + 混合检索复用 |
| 正确性保证 | 文本无损 | 有损残差 + 校验回退 |

---

## 真实后端（VectorEngine 平台，OpenAI 兼容 API，无需 GPU）

骨架默认全离线 mock。真实路径走 **VectorEngine 平台**（OpenAI 兼容聚合 API；模型 `Qwen3-235B-A22B-Instruct-2507` + `text-embedding-3-small` 1536 维）。**平台切换零业务代码改动**——`make_model` 已通用化为"任何 OpenAI 兼容后端"，仅通过配置驱动（`configs/vectorengine.yaml`）：

```bash
cp .env.example .env        # 填 VECTORENGINE_API_KEY（仅放 .env，严禁提交；代码自动加载 .env）
uv sync --extra api         # 装 openai 客户端（smolagents.OpenAIServerModel）

uv run --extra api synapse probe   --config configs/vectorengine.yaml                # ① 鉴权 + CodeAct 可解析 + token 计数
uv run --extra api synapse signal  --config configs/vectorengine.yaml --rounds 5    # ② 三档协议演化 + 残差收缩 + 记忆命中
uv run --extra api synapse signal  --config configs/vectorengine.yaml --rounds 5 --no-memory  # ③ B3 ablation：无记忆对照（证归因）
uv run --extra api synapse hotpot  --config configs/vectorengine.yaml --n 10        # ④ HotpotQA 丢干扰段，真实 token + F1
uv run --extra api synapse musique --config configs/vectorengine.yaml --n 3 --retrieval twohop  # ⑤ MuSiQue 多跳链式检索
uv run --extra api synapse coqa    --config configs/vectorengine.yaml --convs 3     # ⑥ CoQA 对话式记忆复用
uv run --extra api synapse m7      --config configs/vectorengine.yaml --g1 5 --g2 5 # ⑦ 跨组记忆复用（G2 复用 G1）
```

各命令把字节/token/命中率/时延轨迹写入 `runs/<命令>_<时间戳>/result.json`。

---

## openEuler 部署（M10）

基座 smolagents 为纯 Python、轻依赖（无 torch/transformers/langchain），无平台特定依赖。**容器化已落地并实测**：

```bash
docker build -t synapse:latest . && docker run --rm synapse:latest          # 容器内离线自检 → SMOKE PASSED
docker run --rm --env-file .env synapse:latest signal --rounds 10            # 真实实验（密钥仅运行期注入）
```

镜像基于 `openeuler/openeuler:24.03-lts`，非 root 运行，内置 healthcheck。详见 [`docs/部署文档.md`](docs/部署文档.md)。裸机同样可：openEuler 24.03 上 `uv sync && uv run synapse smoke`。

---

## 实验结果（赛题 M8）

详细报告见 `docs/实验报告-2026-07-24-update.md`。关键结果（真实 API，VectorEngine 平台，`Qwen3-235B-A22B-Instruct-2507` + `text-embedding-3-small`，temp=0）：

### 通信效率 + 答案质量（三数据集 per-dataset 最优配置）

| 数据集 | N | 检索模式 | token 节省 | text F1 | synapse F1 | ΔF1 | 金标召回 |
|---|---|---|---|---|---|---|---|
| HotpotQA (bridge 型) | 10 | single k=3 | **71.09%** | 0.780 | 0.680 | −0.100 | **0.900** |
| MuSiQue (链式多跳) | 3 | twohop k=3 | **80.9%** | 0.524 | 0.857 | **+0.333** | 0.667 |
| CoQA (对话式 QA) | 3 conv | — | **10.65%** | 0.656 | 0.684 | **+0.027** | hit 0.921 |

> 多跳场景 SYNAPSE 省 71-81% token；CoQA 对话场景"越长越省"（per-turn 增长 text 1.19-1.31× vs synapse 1.06-1.12×，末轮 gap 达 282 tokens）。
> 检索模式需匹配任务结构：HotpotQA→single（bridge 并行），MuSiQue→twohop（链式依赖，ΔF1+0.333）。

### 机制验证：三档协议演化 + 记忆因果归因（97.6%）

| 条件 | 残差字节轨迹 | drop% | 记忆命中率 |
|---|---|---|---|
| B1-full（有记忆） | 2787→1812→1410→1374→960 | **65.6%** | **0.8** |
| B3-no-mem（记忆清空 ablation） | 2772→2802→2754→2778→2727 | **1.6%** | **0.0** |

> **三档协议演化**：首轮冷启动走 residual 档（零基 2787 字节），第 2 轮起记忆命中切 embedding 档，字节单调降至 960，全程 0 次 text 回退。
> 记忆清空后 drop 从 65.6%→1.6%，**残差收缩的 97.6% 因果源于记忆复用**（B3 ablation 归因）。

---

## 目录结构

```
synapse/
├── 竞赛赛题.md                      # 赛题原文留档（权威需求基准）
├── docs/系统设计文档.md              # 系统设计文档（可执行规格 + M1–M11 覆盖）
├── docs/部署文档.md                  # openEuler 部署文档
├── docs/实验报告-*.md               # 各场景实验报告
├── src/synapse/                     # 五模块源码
│   ├── runtime/  protocol/  stateplane/
│   ├── memory/   modes/     eval/
│   ├── qa/  (数据集对接)
│   └── cli.py  config.py  tasks.py  prompts.py
├── tests/test_smoke.py              # 离线 smoke/单元测试
├── scripts/                         # 数据集获取与图表脚本
├── configs/default.yaml             # 配置（无机密）
├── Dockerfile / docker-compose.yml  # openEuler 容器化部署
├── pyproject.toml                   # 依赖（uv 管理）
└── .env.example                     # 环境变量模板（.env 已 gitignore）
```

---

## 技术栈

- **LLM 后端**：VectorEngine 平台（OpenAI 兼容 API，`Qwen3-235B-A22B-Instruct-2507`，MoE 22B 激活；平台可切换，`make_model` 通用化）
- **Agent 框架**：[smolagents](https://github.com/huggingface/smolagents)（CodeAct 执行）
- **非文本状态**：句向量嵌入（`text-embedding-3-small` 1536 维，OpenAI 兼容；离线 `HashEmbedder` 兜底）+ 预测残差编码
- **包管理**：[uv](https://docs.astral.sh/uv/)
- **容器**：Docker（openEuler 24.03-LTS 基础镜像）

## 许可证

Apache-2.0

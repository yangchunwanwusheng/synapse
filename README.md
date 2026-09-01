![SYNAPSE — 协作即压缩](源代码及readme文档/assets/readme-hero.drawio.png)

<p align="center">
  <strong>第三届中国研究生操作系统开源创新大赛 · 社区赛题作品</strong>
  <br>
  <sub><em>Coordination as Compression — 让经验进入通信回路</em></sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/uv-package%20manager-de4f3f?style=flat-square" alt="uv" />
  <img src="https://img.shields.io/badge/openEuler-24.03--LTS--SP3-002B5B?style=flat-square" alt="openEuler" />
  <img src="https://img.shields.io/badge/smolagents-CodeAct-1C6EA4?style=flat-square" alt="smolagents" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/VLC-Verified%20Lossy-C2185B?style=flat-square" alt="VLC" />
  <img src="https://img.shields.io/badge/CNR-Protocol-8E44AD?style=flat-square" alt="CNR" />
  <img src="https://img.shields.io/badge/ToM-Predictor-9B59B6?style=flat-square" alt="ToM" />
  <img src="https://img.shields.io/badge/Shared_Memory-Evolution-E67E22?style=flat-square" alt="Shared Memory" />
</p>

---

> 源码位于 [源代码及readme文档](源代码及readme文档)。下文的安装、运行和测试命令均请先进入该目录执行。

## 开仓与证据导航

本仓库将“项目主张、实现与证据”分开维护：主张台账定义可公开的措辞，源码和测试证明
机制已实现，实验归档与聚合表用于复算数字。每一条完成态主张均应能沿不超过三跳找到
对应证据；尚未完成 V3-03 重跑的最终数字不在本节回填。

| 评审维度 | 当前入口 | 证据类型 |
| --- | --- | --- |
| 通信效率 | [`TOKEN-HOTPOT-71`](docs/claim-evidence.csv) | QA 管线、计量测试、待批准的 run 归档 |
| 状态传递 | [`RESID-2787-960`](docs/claim-evidence.csv) | 残差编解码、真通路测试、设计说明 |
| 记忆复用 | [`COQA-HIT-921`](docs/claim-evidence.csv) | 记忆模块、连续任务测试、逐项结果 |
| 系统完整性 | [`ARCH-FIVE-MODULE`](docs/claim-evidence.csv) | 五模块源码、离线 smoke、容器配置 |
| 实验验证 | [`ARCHIVE-77`](docs/claim-evidence.csv) | 结果 Schema、manifest、统计与聚合产物 |

三条可直接点验的溯源路径：

1. **结构化通信与能力协商**：README 的机制说明 → [`ARCH-FIVE-MODULE`](docs/claim-evidence.csv) → [`messages.py`](源代码及readme文档/src/synapse/protocol/messages.py) 与 [`test_smoke.py`](源代码及readme文档/tests/test_smoke.py)。
2. **非文本预测残差**：README 的状态传递说明 → [`RESID-2787-960`](docs/claim-evidence.csv) → [`residual.py`](源代码及readme文档/src/synapse/stateplane/residual.py) 与 [`test_true_path.py`](源代码及readme文档/tests/test_true_path.py)。
3. **计量可复算性**：README 的实验口径说明 → [`ARCHIVE-77`](docs/claim-evidence.csv) → [`run-result.schema.md`](docs/schema/run-result.schema.md) 与 [`test_manifest.py`](源代码及readme文档/tests/test_manifest.py)。

实验归档（`runs/`、`04-analysis/aggregated/`、`_state/`、`01-idea/`、`02-design/`）仅在
团队逐目录确认后分批入库。入库前运行以下只读预检；它不会复制、删除、暂存或提交文件：

```powershell
python scripts/archive_preflight.py `
  --root runs `
  --root 04-analysis/aggregated `
  --root _state `
  --root 01-idea `
  --root 02-design `
  --json docs/repo-preflight-current.json
```

Linux / openEuler（sh）:

```bash
python3 scripts/archive_preflight.py \
  --root runs \
  --root 04-analysis/aggregated \
  --root _state \
  --root 01-idea \
  --root 02-design \
  --json docs/repo-preflight-current.json
```

预检记录见 [`docs/repo-preflight-current.json`](docs/repo-preflight-current.json)；评审环境真实归档
的一轮复核见 [`docs/repo-preflight-archive-review.json`](docs/repo-preflight-archive-review.json)。
前者只反映当前工作区是否存在候选目录，后者记录外部归档的人工裁决状态；两者都不是实验结果，
也不替代 V3-03 的数字回填与统计复算。

## 🧭 从“文本接力”到“状态协同”

多智能体系统不应把人类语言当作唯一的通信总线。

当 Planner、Retriever、Executor 与 Summarizer 共同完成一项复杂任务时，传统方案往往让 Agent 反复传递长文本、重复解释上下文、重新推理已经解决过的问题。协作轮次越多，Token、时延与语义损耗便越明显——系统拥有更多经验，通信却没有因此变得更聪明。

**SYNAPSE 将这个问题重新定义为一项系统级的条件编码任务。** 接收方已经掌握的内容不必再次传输，发送方只需表达“预测之外的信息”。共享记忆不断积累，接收方的预测能力随之增强，真正需要传递的惊讶残差持续变小。

<table>
<tr><td width="6" bgcolor="#1F883D"></td>
<td bgcolor="#E6F4EA">

💡 **Memory ↑　→　Prediction ↑　→　Residual ↓　→　Communication ↓**
<br>经验越多，预测越准；预测越准，通信越省。

</td></tr>
</table>

这不是一次对提示词的局部优化，而是一套贯穿协议、状态、存储、校验与评测的完整协作机制：让多 Agent 从冗长的“文本接力”，升级为可积累、可验证、可演进的“状态协同”。

## 🔗 三重机制，构成同一条链

### 01　📡 结构化通信：先让 Agent 说同一种语言

SYNAPSE 以统一消息协议承载动作、参数、结果与能力描述，并通过 CNR（Capability Negotiation & Resolution）完成握手、能力发现、编码协商与任务路由，可与业界 A2A Agent Card 标准做协议映射。自然语言不再承担全部控制职责，Agent 之间交换的是边界清晰、可以调度、可以度量的协作意图。

**结果是：控制信息更短，协作关系更清楚，通信开销能够被真正计算。**

### 02　🧬 非文本状态：只传递预测失败的部分

系统把中间语义状态编码为句向量，利用共享记忆生成接收方预测，再计算残差 `Z = Y − Ŷ`——发送端不传完整向量，只对残差进行率失真编码、稀疏量化并写入内容寻址存储（CAS），在线缆上仅交换轻量句柄。该机制覆盖赛题要求的四个环节：

- **生成：** 发送方对当前证据调用句向量模型（`text-embedding-3-small`，1536 维，黑盒可得、无需访问 LLM 内部状态）得到状态 `Y`，并基于共享记忆中的 ToM 预测基 `B̂` 生成预测 `Ŷ`，残差 `Z = Y − Ŷ` 即接收方未知的语义增量。
- **传递：** 残差经率失真贪心编码（按分量绝对值降序选择，余弦相似度达阈值即停），写入 CAS 后**线缆上只走残差句柄 + 内容句柄 + 校验码**；索引字节宽随维度自适应（dim>256 自动切双字节，支持 1536/2048 维）。
- **接收：** 接收方按句柄从 CAS 取回残差，叠加本地预测基 `Ŷ` 恢复完整语义表示；不在线缆上透传正文。
- **使用：** 恢复的向量直接作为下游 Agent 的检索键与推理输入；并通过 VLC 校验（重嵌入比对余弦相似度，失配即回退全量文本）保证端到端正确性。

为了让“有损”不等于“不可靠”，SYNAPSE 设计了 **Verified Lossy Coordination（VLC）**：重构结果通过一致性校验后才进入下游；关键语义失配时自动提升精度或回退全文路径。系统既敢于压缩，也知道何时不能压缩。

### 03　🧠 共享记忆：让一次协作成为下一次的边信息

任务中的证据、摘要、策略与结论被沉淀为统一记忆单元（MemoryUnit），每条记忆至少记录**记忆 ID、来源 Agent、创建时间、任务主题与摘要描述**，并通过内容寻址生成唯一标识以支持去重。检索层同时支持赛题要求的三路召回——**关键词集合相似度、标签过滤、语义相似度（向量余弦）**，融合排序后选取最相关单元作为预测基；不同 Agent 在后续任务中可直接复用已有记忆，无需重复计算。

在记忆演化上，SYNAPSE 引入链接追踪与取代检测：新记忆写入时自动标记被覆盖的旧单元，检索时过滤过时信息并沿链接扩大有效召回——使记忆从无限堆积的追加日志，升级为可审计、可演化的活性记忆体。

在 SYNAPSE 中，Memory 不只是知识仓库，它同时承担四个角色：**经验资产、状态预测器、通信压缩器与新颖性传感器。** 系统不再每次从零开始，而是在持续协作中形成“越用越省、越用越聪明”的正反馈。

## 🔄 一条从协作到复用的闭环

![SYNAPSE 系统架构：结构化控制面、非文本状态面与共享记忆闭环](源代码及readme文档/assets/architecture.drawio.png)

四类 CodeAgent 共同覆盖任务规划、信息检索、工具执行与结果整合；结构化控制面负责协商和调度，非文本状态面负责预测、残差、CAS 句柄与校验，共享记忆则把本轮有效经验送回下一轮协作。

这条闭环的关键不在于把文本“压得更小”，而在于**减少需要表达的信息本身**：完整状态被改写为语义增量，历史经验被转化为解码端边信息，通信成本因此可以随协作深入而持续收缩。

## 📊 实验，让机制自己说话

![SYNAPSE 真实 API 与公开数据集实验结果](源代码及readme文档/assets/results.drawio.png)

SYNAPSE 在 HotpotQA、MuSiQue 与 CoQA 三类真实任务上完成纯文本模式与结构化模式的同条件 A/B 评测，并以配对检验、因果消融和受损注入验证通信效率、答案质量与可靠性。

实验设计包含**不少于 2 组关联性连续任务**：HotpotQA（bridge 型并行多跳）与 MuSiQue（链式 two-hop 多跳）构成第一组多跳结构对照，CoQA（38 轮长对话）与合成 G1→G2 演进序列构成第二组长程关联对照，覆盖赛题对关联任务验证的要求。

- **通信收缩：** HotpotQA 实测应答 LLM token 降低 **71.1%**（N=10 点估计，脚本一键复现，溯源 `runs/hotpot_20260724_214352/`；来源分解见消融实验）；MuSiQue 点估计 **80.9%**（N=3 探索性，溯源 `runs/musique_20260724_203011/`，扩样至 N≥100 进行中）。进程内共享 CAS 口径下，逻辑消息字节降低 HotpotQA **94.6%**、MuSiQue **96.5%**（真实跨进程传输字节将在数据平面实测）。全部主张可经 [docs/claim-evidence.csv](docs/claim-evidence.csv) 三跳对账（主张 → 文件 → run/测试）。
- **质量竞争力：** HotpotQA N=200 配对检验报告配对差值 **-0.038 [-0.098, +0.019]**（区间含 0，未检测到显著均值差，聚合见 `04-analysis/aggregated/summary.csv`）；非劣结论按预注册界限另行判定，MuSiQue 多参考重评结果见聚合表。
- **记忆因果性：** 有共享记忆时，残差估算载荷由 `2787 B` 收缩至 `960 B`（encoder-oracle 选基口径，理论上界）；无记忆对照几乎不收缩，**97.6%** 的收缩与记忆可用性相关（因果对照设计）。
- **可靠协作：** 受控注入下预测基失配检出 **16/16、0 漏报**并自动回退；传输完整性校验（checksum）与端到端消费通路按决赛路线图落地后复测。
- **意外发现：** 受控合成样本（8+8，单 seed，机制验证）下，残差信号对分布漂移的检测 AUC 达 **1.0**——通信成本本身，成为一个模型无关且无需额外开销的系统健康信号；真实任务泛化列为下一里程碑。

## 🛠️ 为真实系统而构建

SYNAPSE 不是概念图上的算法组合，而是一套可以编译、运行、对照和测量的多智能体协作原型。上述三重机制贯穿赛题要求的五个工程模块：**多 Agent 运行时（runtime）·协议解析与调度（protocol）·状态交换（stateplane）·共享记忆存储与检索（memory）·评测（eval）**，形成可独立验证、可组合演进的完整系统：

- **四类角色，长程稳定：** Planner / Retriever / Executor / Summarizer 覆盖赛题全部四类角色，稳定执行**不少于 10 轮**连续任务（CoQA 实测 38 轮长对话）。
- **双模式可复现对照：** text / synapse 在相同任务、模型、配置与随机种子下完成顺序隔离式 A/B，统一度量消息次数、Token / 字符开销、非文本传递规模、单任务耗时与记忆命中率。
- **系统技术落地：** Executor 经 **CodeAct** 执行模型生成代码；状态载荷通过进程内 CAS 内容句柄去重与按需恢复，记忆检索采用纯 Python 的关键词、标签与向量余弦融合；整体目标环境为 **openEuler 24.03-LTS-SP3**。当前 `master` 尚未提供跨进程共享内存、Socket、eBPF 或 faiss 后端，相关能力只在决赛工程路线图中推进，不作为已实现能力计分。
- **协议与状态自适应：** 发送方按预测基强度在 residual / embedding / text 三档间预判选档，随经验动态演化；大状态经 CAS 句柄与消息体分离，支持去重与按需恢复。

我们希望证明的并不只是“某一次实验更省”，而是一条更具普适性的系统规律：

<table>
<tr><td width="6" bgcolor="#8250DF"></td>
<td bgcolor="#F5E8FC">

📌 **当多个智能体共享不断增长的经验，它们之间的通信成本应当随协作深入而下降，而不是继续线性甚至平方级增长。**

</td></tr>
</table>

## 🎯 破局定位：与主流方案对比

当前多 Agent 协作的通信架构主要分三类。在黑盒 API 占据主流的现实约束下，SYNAPSE 重点同时满足“黑盒可部署、无需训练、传输量随经验递减、带校验回退”四个条件；该定位是本项目的设计目标，不作未经系统检索验证的“唯一”或“首个”声明。

| 维度 | **SYNAPSE** | 自然语言对话<br>（AutoGen / CrewAI） | 工作流编排<br>（LangGraph） | 潜空间通信<br>（C2C / LatentMAS） |
| --- | --- | --- | --- | --- |
| 通信载体 | **句向量预测残差** | 自由文本 | JSON / 函数调用 | 隐状态 / 全量嵌入 |
| 通信效率 | **高** 🟢（仅传预测外增量） | 低 🔴（每次重传全量上下文） | 中 🟡（局部结构化，主体仍文本） | 高 🟢（向量替代文本） |
| 需白盒访问 | **否** ✅（句向量黑盒可得） | 否 ✅ | 否 ✅ | **是** ❌（需访问内部状态） |
| 校验机制 | **有** ✅（语义一致性校验 + 自动回退；传输完整性校验见路线图） | 文本无损 ➖ | 文本无损 ➖ | 无 ❌（存在静默损坏风险） |
| 跨任务复用 | **有** ✅（共享记忆 + 演化链） | 无 ❌ | 无 ❌ | 无 ❌ |
| 传输量随经验 | **递减** 🟢（记忆→预测→残差稀疏） | 不变 ➖ | 不变 ➖ | 不变 ➖ |

**与三类最相关工作的事实划界**（每条一句"他们做什么 / 我们差异在哪"）：

1. **潜空间通信**（C2C、LatentMAS、ThoughtComm）——他们让 Agent 在模型隐状态或全量嵌入层直接互通，需要白盒访问模型内部；SYNAPSE 只用黑盒可得的句向量做预测残差，落在商用闭源 API 可部署的系统层。
2. **记忆系统**（MemGPT、A-MEM、Mem0、MemOS）——他们做 API 层的记忆管理框架，记忆服务于单个 Agent 的上下文组织；SYNAPSE 把记忆放进 OS 数据平面，作为通信压缩的预测基与字节计量对象。
3. **因果审计**（对 KV 中继收益的质疑工作）——他们指出潜空间传递的收益难以测量与归因；SYNAPSE 的 VLC 校验使每一次压缩都可被检出、回退与计量，收益可复算。

<table>
<tr><td width="6" bgcolor="#1F883D"></td>
<td bgcolor="#E6F4EA">

💡 句向量残差路线恰好填补了潜空间通信的空白区——不要求访问模型内部隐状态，又保留了非文本状态传递的效率优势。这是 latent 通信在商用闭源 API 时代的务实落地。

</td></tr>
</table>

## 📋 赛题维度对照

按大赛公布的五个评分维度逐项对照，每一维均有实现回应与实验数据支撑（详细数据见图表与《SYNAPSE 项目说明书》§4 / §6.4）。

| 维度（分值） | 实现回应 | 关键实验数据 |
| --- | --- | --- |
| **通信效率**（25） | CNR 结构化协议替代长文本透传 + 残差编码仅传语义增量 | HotpotQA 应答 token ↓ **71.1%**（N=10 点估计）、MuSiQue **80.9%**（N=3 探索性）；逻辑消息字节 ↓ **94.6%–96.5%**（进程内 CAS 口径）；N=200 配对差值与 CI 见聚合表 |
| **状态传递创新**（20） | 黑盒句向量预测残差 + VLC 校验回退 | 残差估算载荷 2787 → **960**（↓65.6%，encoder-oracle 口径）；受控注入失配检出 **16/16、0 漏报**；三档选档策略随经验演化 |
| **记忆复用效果**（20） | 三路混合检索（关键词集合相似度/标签/语义）+ ToM 预测 + 记忆演化链（取代检测） | CoQA 会话历史可复用覆盖率 **0.921**（top-k 检索命中口径，与质量收益分列见聚合表）；97.6% 收缩因果归因；G2 跨组复用命中率 ≥ G1 |
| **系统完整性**（20） | 五模块架构 + 四类 CodeAgent + CodeAct 执行 + 进程内 CAS | 离线 smoke **5 项 PASS**；pytest 覆盖编解码/检索/路由；openEuler 24.03-LTS-SP3 为指定验证环境 |
| **实验验证**（15） | 顺序隔离式 A/B（相同任务/模型/种子）+ 六类指标 + 77 次真实实验存档 | 三真实数据集 + 合成关联序列；漂移检测 **AUC=1.0**（受控合成样本，机制验证；通信成本作免费健康信号） |

## 🚀 运行与验证

项目初期在大赛指定 openEuler 环境对应的 Docker 容器中完成基础编译、运行与测试；项目后期迁移至安装 **openEuler 24.03-LTS-SP3** 的真实服务器，并在原生操作系统环境中重新完成编译、运行和测试。

### 环境与安装

需要 Python 3.11+ 与 [uv](https://docs.astral.sh/uv/)。

```bash
uv sync                                                       # 基础：仅离线 mock 自检所需
uv sync --extra api --extra embed --extra vector --extra config   # 真实 API 评测所需
uv sync --extra dev                                           # 测试与 lint（pytest / ruff）
```

可选依赖按用途拆分（见 `pyproject.toml`）：`api`（真实 LLM）、`embed`（真实句向量）、`vector`（向量检索）、`config`（YAML 覆盖）、`viz`（实验作图）、`dev`（开发）。

### ① 离线自检（零 API Key）

```bash
uv run synapse smoke
```

校验双模式跑通、残差节省、记忆复用命中与负例区分度——无网络、无密钥，验证机制本身成立。

### ② 接入真实 API

复制 `.env.example` 为 `.env` 并填入密钥（`.env` 已被 `.gitignore` 忽略，严禁提交）：

```
VECTORENGINE_API_KEY=<your-key>
```

默认走 **VectorEngine**（OpenAI 兼容聚合平台，见 `configs/vectorengine.yaml`）；切换其他 OpenAI 兼容平台只需改 YAML 的 `api_base / api_key_env / model`，无需改代码。接通后先用探针确认鉴权、输出形态（非 thinking）、CodeAct 可解析与真实 token 计数：

```bash
uv run synapse probe --config configs/vectorengine.yaml
```

<table>
<tr><td width="6" bgcolor="#0969DA"></td>
<td bgcolor="#E8F1FC">

ℹ️ 两份配置：`configs/default.yaml`（离线 mock，hash embedder）用于机制自检；`configs/vectorengine.yaml`（真实 LLM `qwen3-235b-a22b-instruct-2507` + 句向量 `text-embedding-3-small`）用于真实评测。所有命令均支持 `--config` 覆盖。

</td></tr>
</table>

### ③ 真实数据集评测

数据集**不随仓库分发**，需先抓取（经 HuggingFace datasets-server，无重依赖）：

```bash
uv run python scripts/fetch_hotpot.py 20     # → data/hotpot_sample.json   （10 段/题，2 金标 + 8 干扰）
uv run python scripts/fetch_musique.py 20    # → data/musique_sample.json  （20 段/题，干扰更密）
uv run python scripts/fetch_coqa.py 5        # → data/coqa_sample.json     （对话式，关联连续任务）
```

复现论文实验（对应“实验，让机制自己说话”一节的核心数字）：

| 命令 | 对应结果 |
| --- | --- |
| `uv run synapse hotpot --config configs/vectorengine.yaml --n 10 --embedder api --k 3` | HotpotQA 应答 token ↓ **71.1%**（N=10 点估计，`runs/hotpot_20260724_214352/`） |
| `uv run synapse musique --config configs/vectorengine.yaml --n 10 --embedder api --k 3` | MuSiQue token ↓ **80.9%**（N=3 探索性点估计，`runs/musique_20260724_203011/`；多参考重评与扩样见聚合表） |
| `uv run synapse hotpot-stats --config configs/vectorengine.yaml --n 50 --repeats 3` | 统计稳健化：配对检验 + 95% CI（质量非劣验证） |
| `uv run synapse coqa --config configs/vectorengine.yaml --convs 2 --embedder api --k 6` | CoQA 对话式真实 token + F1 |

`--retrieval single|twohop|bridge` 切换单跳 / 嵌入查询扩展 / 词法实体桥接；`--seed` 固定题序以复现。

### ④ 消融与机制验证

```bash
uv run synapse signal --config configs/vectorengine.yaml --rounds 5 --no-memory   # 记忆因果：无记忆对照（97.6% 收缩归因）
uv run synapse m7 --config configs/vectorengine.yaml --g1 5 --g2 5                # 跨组记忆复用（G2 暖启动）
uv run python scripts/sweep_hotpot_k.py --n 50 --ks 3 4 5 6 8                     # k-前沿：寻找诚实操作点
uv run synapse ab --config configs/default.yaml --rounds 10                       # 合成任务双模式 A/B
```

### ⑤ 测试

```bash
uv run pytest
```

### ⑥ Docker / openEuler 容器

```bash
docker build -t synapse:latest .
docker run --rm synapse:latest
```

## 📁 项目结构

```
src/synapse/
  cli.py              命令行入口（smoke / ab / probe / signal / m7 / coqa / hotpot / musique / hotpot-stats）
  config.py           配置：dataclass + YAML 覆盖
  tasks.py            合成任务族（关联连续 / 负例族 / G1 / G2）
  protocol/           结构化控制面：CNR 握手、能力发现、编码协商、任务路由
  stateplane/         非文本状态面：residual（残差编码）/ embedding / cas（内容寻址）/ checksum
  memory/             共享记忆：store / retrieval / consolidate / tom
  modes/              text_mode（全文基线）/ synapse_mode（VLC：Verified Lossy Coordination）
  runtime/            model（后端工厂）/ team（四类 Agent 编排）
  qa/                 真实数据集 harness：dataset / harness / pipeline / scoring / stats
  eval/               ABRunner / metrics
  prompts.py
configs/              default.yaml（离线 mock）/ vectorengine.yaml（真实 API）
scripts/              fetch_coqa / fetch_hotpot / fetch_musique（数据集）/ sweep_hotpot_k（k-前沿）
tests/                test_smoke / test_qa
```

## 📦 交付材料

除本仓库源码外，下列材料随提交一并交付（对应赛题交付要求）：

| 材料 | 文件 | 说明 |
| --- | --- | --- |
| 系统设计文档 | `SYNAPSE项目说明书.docx` | 六章完整文档：理论建模、五模块设计、实验、实现难点、赛题维度对照 |
| 实验报告 | 说明书 §4 + `runs/*.json` | 三数据集实验数据与 77 次真实实验原始存档，可溯源复验 |
| 部署文档 | 本 README「运行与验证」+ `Dockerfile` | openEuler 24.03-LTS-SP3 容器一键编译运行 |
| 演示视频 | `SYNAPSE演示视频.mp4` | 系统运行与实验过程演示 |
| 作品介绍 | `SYNAPSE作品介绍PPT.pptx` | 评审速览 |

---

<p align="center">
  <strong>SYNAPSE</strong> · <em>Coordination as Compression</em>
  <br>
  <sub>让一次协作，成为下一次的边信息。</sub>
</p>

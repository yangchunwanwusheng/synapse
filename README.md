![SYNAPSE — 协作即压缩](assets/readme-hero.drawio.png)

<p align="center">
  <strong>第三届中国研究生操作系统开源创新大赛 · 社区赛题作品</strong>
  <br>
  <sub>4 Agents · Structured Protocol · Non-text State · Shared Memory · openEuler</sub>
</p>

---

## 从“文本接力”到“状态协同”

多智能体系统不应把人类语言当作唯一的通信总线。

当 Planner、Retriever、Executor 与 Summarizer 共同完成一项复杂任务时，传统方案往往让 Agent 反复传递长文本、重复解释上下文、重新推理已经解决过的问题。协作轮次越多，Token、时延与语义损耗便越明显——系统拥有更多经验，通信却没有因此变得更聪明。

**SYNAPSE 将这个问题重新定义为一项系统级的条件编码任务。** 接收方已经掌握的内容不必再次传输，发送方只需表达“预测之外的信息”。共享记忆不断积累，接收方的预测能力随之增强，真正需要传递的惊讶残差持续变小。

> **Memory ↑　→　Prediction ↑　→　Residual ↓　→　Communication ↓**
>
> 经验越多，预测越准；预测越准，通信越省。

这不是一次对提示词的局部优化，而是一套贯穿协议、状态、存储、校验与评测的完整协作机制：让多 Agent 从冗长的“文本接力”，升级为可积累、可验证、可演进的“状态协同”。

## 三重机制，构成同一条链

### 01 · 结构化通信：先让 Agent 说同一种语言

SYNAPSE 以统一消息协议承载动作、参数、结果与能力描述，并通过 CNR 完成握手、能力发现、编码协商与任务路由。自然语言不再承担全部控制职责，Agent 之间交换的是边界清晰、可以调度、可以度量的协作意图。

**结果是：控制信息更短，协作关系更清楚，通信开销能够被真正计算。**

### 02 · 非文本状态：只传递预测失败的部分

系统把中间语义状态编码为句向量，利用共享记忆生成接收方预测，再计算 `Z = Y − Ŷ`。发送端不传完整向量，而是对残差进行率失真编码、稀疏量化并写入内容寻址存储，在线缆上只交换轻量句柄。

为了让“有损”不等于“不可靠”，SYNAPSE 设计了 **Verified Lossy Coordination（VLC）**：重构结果通过一致性校验后才进入下游；关键语义失配时自动提升精度或回退全文路径。系统既敢于压缩，也知道何时不能压缩。

### 03 · 共享记忆：让一次协作成为下一次的边信息

任务中的证据、摘要、策略与结论被沉淀为统一记忆单元。关键词、标签与语义相似度三路检索共同选择预测基，记忆演化链负责关联扩展、取代检测与过时过滤。

在 SYNAPSE 中，Memory 不只是知识仓库，它同时承担四个角色：**经验资产、状态预测器、通信压缩器与新颖性传感器。** 系统不再每次从零开始，而是在持续协作中形成“越用越省、越用越聪明”的正反馈。

## 一条从协作到复用的闭环

![SYNAPSE 系统架构：结构化控制面、非文本状态面与共享记忆闭环](assets/architecture.drawio.png)

四类 CodeAgent 共同覆盖任务规划、信息检索、工具执行与结果整合；结构化控制面负责协商和调度，非文本状态面负责预测、残差、CAS 句柄与校验，共享记忆则把本轮有效经验送回下一轮协作。

这条闭环的关键不在于把文本“压得更小”，而在于**减少需要表达的信息本身**：完整状态被改写为语义增量，历史经验被转化为解码端边信息，通信成本因此可以随协作深入而持续收缩。

## 实验，让机制自己说话

![SYNAPSE 真实 API 与公开数据集实验结果](assets/results.drawio.png)

SYNAPSE 在 HotpotQA、MuSiQue 与 CoQA 三类真实任务上完成纯文本模式与结构化模式的同条件 A/B 评测，并以配对检验、因果消融和受损注入验证通信效率、答案质量与可靠性。

- **通信收缩：** HotpotQA Token 开销降低 **71.09%**，MuSiQue 降低 **80.90%**；端到端线缆字节最高节省 **96.45%**。
- **质量竞争力：** N=200 配对检验中，结构化模式与全文基线的答案质量在统计上不可区分；MuSiQue 上进一步取得 **ΔF1 = +0.333**。
- **记忆因果性：** 有共享记忆时，残差由 `2787 B` 收缩至 `960 B`；无记忆对照几乎不收缩，**97.6%** 的收缩可归因于记忆复用。
- **可靠协作：** 在受控有损注入中，VLC 检出并回退全部 16 个受损样本，静默损坏为 **0**。
- **意外发现：** 残差信号对分布漂移的检测 AUC 达 **1.0**——通信成本本身，成为一个模型无关且无需额外开销的系统健康信号。

## 为真实系统而构建

SYNAPSE 不是概念图上的算法组合，而是一套可以编译、运行、对照和测量的多智能体协作原型：

- 四类 Agent 形成完整任务闭环，Executor 通过 CodeAct 执行模型生成的代码；
- 三档混合协议可在 residual、embedding 与 text 之间自适应选择；
- CAS 将大状态从消息体中分离，内容句柄支持去重与按需恢复；
- text / synapse 双模式在相同任务、模型与配置下完成顺序隔离式 A/B；
- 指标覆盖消息次数、Token、线缆字节、非文本载荷、时延、记忆命中与任务质量。

我们希望证明的并不只是“某一次实验更省”，而是一条更具普适性的系统规律：

> **当多个智能体共享不断增长的经验，它们之间的通信成本应当随协作深入而下降，而不是继续线性甚至平方级增长。**

## 运行与验证

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

> 两份配置：`configs/default.yaml`（离线 mock，hash embedder）用于机制自检；`configs/vectorengine.yaml`（真实 LLM `qwen3-235b-a22b-instruct-2507` + 句向量 `text-embedding-3-small`）用于真实评测。所有命令均支持 `--config` 覆盖。

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
| `uv run synapse hotpot --config configs/vectorengine.yaml --n 10 --embedder api --k 3` | HotpotQA Token ↓ **71.09%** |
| `uv run synapse musique --config configs/vectorengine.yaml --n 10 --embedder api --k 3` | MuSiQue Token ↓ **80.90%**、ΔF1 = **+0.333** |
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

## 项目结构

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

---

<p align="center">
  <strong>SYNAPSE</strong> · Coordination as Compression
  <br>
  <sub>让经验进入通信回路，让协作真正拥有记忆。</sub>
</p>

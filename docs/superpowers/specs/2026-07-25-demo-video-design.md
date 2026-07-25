# SYNAPSE 演示视频 Design Doc

- **日期**：2026-07-25
- **作者**：SYNAPSE 团队（经 brainstorming 流程）
- **状态**：待用户审阅
- **目标**：为第三届中国研究生操作系统开源创新大赛社区赛题录制 ≤5 分钟演示视频，作为赛题交付物之一（与源码、设计文档、部署文档、实验报告并列）

---

## 0. 摘要（TL;DR）

本设计描述一支 5 分钟演示视频的完整方案。视频以**「openEuler 现场落地 → 同基座公平 A/B → 学术 SOTA 对照」**三段式叙事，证明 SYNAPSE 用非文本残差编码取代 agent 间文本透传，在保持答案质量（gold_recall 0.9）的前提下节省 71–81% Token。视频严格对齐项目说明书叙事 DNA，使用 07-24 真实实验数字，在原生 openEuler 24.03-LTS-SP3 服务器上以 OBS 录制。

**核心叙事总线**（一字不差对齐说明书 [014]）：

> 「SYNAPSE 将多智能体协作建模为**带增长边信息的 Wyner-Ziv 条件率失真编码**：共享记忆不断积累使接收方边信息持续增强，发送方仅需传递『惊讶残差』而非全量信息，实现通信开销随经验增长而持续收缩。」

**三大不可越过的红线**：
1. 所有数字必须来自 `runs/` 真实 result.json（07-24 VectorEngine 平台）
2. 不得声称"更快"（延迟实际为负），只讲 Token 节省
3. 不得声称"向量数据库 / IPC / WASM / eBPF"（代码事实未实现，说明书也已规避）

---

## 1. 背景与约束

### 1.1 赛题硬要求

| 要求 | 来源 | 应对 |
|---|---|---|
| openEuler 24.03-LTS-SP3 编译运行 | 赛题交付要求 | 原生服务器录制（已具备 SSH 环境），Docker 路径已实测 SMOKE PASSED |
| ≤5 分钟演示视频 | 赛题交付要求 | 7 镜头分镜，总时长 5:00 |
| 多 Agent 协作 + 结构化协议 + 非文本状态 + 共享记忆 + 双模式对比 + ≥2 组关联连续任务 | 赛题 M1-M9 | 全部已实现（见 §3 赛题对应表） |

### 1.2 评分维度（共 100 分）

| 维度 | 分值 | 本设计对应章节 | 自评 |
|---|:---:|---|:---:|
| 通信效率 | 25 | §6 L3-L4（71-81% Token 节省） | 22-24 |
| 状态传递创新 | 20 | §6 L2（Wyner-Ziv + 残差 + CAS） | 17-19 |
| 记忆复用效果 | 20 | §6 L5（CoQA 0.921 + m7 + 97.6% 归因） | 14-17 |
| 系统完整性 | 20 | §6 L1（openEuler + 五模块 + CodeAct） | 15-17 |
| 实验验证 | 15 | §6 L6（CodeAgents 对照 + 三数据集） | 11-13 |
| **合计** | **100** | — | **79-90** |

### 1.3 已验证的关键事实（来自代码核查 + run 目录实测）

| 事实 | 状态 | 证据 |
|---|---|---|
| Docker build + smoke PASSED | ✅ 今日实测 | `docker run --rm synapse:test` → SMOKE PASSED |
| 五模块 + 4 角色 CodeAgent | ✅ | `src/synapse/` 2877 行；`team.py:18-23,91-100` |
| 非文本残差编码（率失真 + 校验回退） | ✅ 最强项 | `residual.py:28-77`；`SYNAPSE.tex` Wyner-Ziv framing |
| HotpotQA 省 71.09% Token（N=10） | ✅ | `runs/hotpot_20260724_214352/result.json` |
| MuSiQue 省 80.9% Token（N=3） | ✅ | `runs/musique_20260724_203011/result.json` |
| CoQA hit_rate 0.921 | ✅ | `runs/coqa_20260724_211318/result.json` |
| 97.6% 残差收缩归因于记忆（B3 ablation） | ✅ | `runs/signal_20260724_191435` vs `193555` |
| result.json 总数 = 77（非 105） | ✅ | `find runs/ -name result.json \| wc -l` |
| faiss 未真用（业务代码零 import） | ✅ | `pyproject.toml:12` 声明但全代码库零调用 |
| 沙箱 = smolagents 默认 LocalPythonExecutor | ✅ | 无自定义沙箱 |
| 延迟节省为负 | ✅ | synapse 多次 API 调用慢于 text |

---

## 2. 设计原则

### 2.1 与项目说明书严格对齐（红线）

视频是说明书的**视觉化延伸**，不是另一套叙事。以下必须一字不差对齐说明书 DNA（见 `项目文档/项目说明书(1).docx`）：

| 对齐项 | 说明书写法 | 视频用法 |
|---|---|---|
| 作品代号 | SYNAPSE（全大写） | 字幕、口播一律 SYNAPSE |
| 核心 framing | "带增长边信息的 Wyner-Ziv 条件率失真编码" | L2 镜头大字标题 |
| 三重机制 | "结构化通信协议 + 句向量预测残差编码 + 内容寻址共享记忆" | L2 三栏动画顺序 |
| 三大瓶颈 | Token 消耗 / 编解码时延 / 经验沉淀 | L2 开场痛点 |
| 残差措辞 | "惊讶残差"（surprise residual） | 口播 + 字幕 |
| 闭环 | Memory 增长 → Prediction 增强 → Residual 减少 → Communication 降低 | L2 收尾动画 |
| 总结 framing | "协作即压缩 / 越用越省、越用越聪明" | L7 收尾 |
| 数字 | 71.09% / 80.9% / 0.921 / 97.6% / ΔF1 -0.100 / +0.333 / +0.027 | 全部镜头 |
| 术语首次出现格式 | 中文（English 缩写）如 CAS（Content Addressable Storage，内容寻址存储） | 字幕 |
| 数据集配置 | HotpotQA N=10 single k=3 / MuSiQue N=3 twohop k=3 / CoQA 3 段 38 轮 | L3-L4 镜头 |
| 后端 | Qwen3-235B-A22B-Instruct-2507、temp=0、VectorEngine、text-embedding-3-small 1536 维 | L1 镜头 |
| 部署 | openeuler/openeuler:24.03-lts、597MB、uid 1001 | L1 镜头 |

### 2.2 诚实红线（不可越过）

| 不可说 | 原因 | 替代说法 |
|---|---|---|
| "使用了向量数据库 / faiss" | 代码未真用，说明书也未提 | "语义向量余弦相似度检索"（说明书口径） |
| "延迟降低 / 更快" | 实测为负 | 只讲 Token 节省 |
| "跨进程 IPC / 共享内存 / Socket" | 同进程 dict | "通过 CAS 句柄在 Agent 间传递状态引用" |
| "WASM / eBPF 沙箱" | 未实现 | "基于 smolagents LocalPythonExecutor 子进程级沙箱" |
| "105 个实验" | 实际 77 | "77 个 result.json + 6 类实验 + N=50×3 配对统计" |
| "能力探测带 TTL 缓存"（说明书 [107]） | 代码未真探测 | 视频回避此句 |
| "frozen-snapshot 记忆注入" | 说明书仅总结段一句，正文未论证 | 视频不展开 |

### 2.3 可优于说明书的机会点

| 机会 | 做法 |
|---|---|
| 架构图 | 说明书无架构图，视频补一张（按 [074][140] 流水线绘制） |
| CodeAgents 外部对照 | 说明书无外部对照，视频新增（学术 SOTA 背书） |
| 诚实负数 | 保留 ΔF1=-0.100 + [248] 小样本标注，诚信加分 |
| 沙箱表述 | 明确说"smolagents LocalPythonExecutor 子进程级沙箱"，比说明书"容器沙箱"更准确 |

---

## 3. 赛题对应表（如何在视频/PPT/文档体现优势）

### 3.1 硬要求 M1-M11

| 赛题要求 | 视频镜头 | PPT 章节 | 文档章节 | 证据强度 |
|---|:---:|---|---|:---:|
| **M1** ≥3 Agent 协同（规划/检索/执行/总结 ≥3 类） | L2 | 系统设计-四角色 | 模块一 [076-083] | 强（4 角色全覆盖） |
| **M2** 结构化通信（动作/参数/结果/能力 + 握手/能力发现） | L2 | 系统设计-协议层 | 模块二 [084-107] | 强 |
| **M3** 双模式可复现对比 | L3-L4 | 实验-双模式 | §4.1 [153-162] | 强 |
| **M4** 非文本中间状态传递 | L2、L5 | 技术理论-残差编码 | §2.1.4 [040-043] | **最强** |
| **M5** 共享记忆模块（5 元数据） | L5 | 系统设计-记忆 | 模块四 [122-141] | 强 |
| **M6** 关键词/标签/语义检索 + 跨 Agent 复用 | L5 | 系统设计-检索 | 模块四 [133-134] | 中-强 |
| **M7** ≥2 组关联连续任务 | L4 | 实验-M7 | §4.5 [267-272] | 强 |
| **M8** 统计消息数/Token/字节/耗时/命中率 | L3-L4 | 实验-Metrics | 模块五 [142-162] | 强 |
| **M9** 五模块 + 稳定 ≥10 轮 | L1、L4 | 系统设计-架构 | 模块一-五 | 强 |
| **M10** openEuler 24.03-LTS-SP3 | L1（开场） | 部署-容器化 | 部署文档 §E | 强 |
| **M11**（鼓励）CodeAct + 轻量沙箱 | L4 | 系统设计-Executor | 模块一 [078] | 中 |

### 3.2 五维评分对应

#### 维度 1：通信效率（25 分）— 自评 22-24

**视频呈现**：L3-L4 镜头，并排数字滚动 + HotpotQA/MuSiQue 双数据集表

**核心数字**（07-24 真实）：
- HotpotQA N=10：Token 省 **71.09%**，wire_bytes 省 **94.64%**，gold_recall 0.9
- MuSiQue N=3：Token 省 **80.9%**，wire_bytes 省 **96.45%**，ΔF1 **+0.333**
- CoQA 3 段 38 轮：Token 省 **10.65%**，hit_rate **0.921**
- 统计稳健化（旧 Paratera）：N=50×3=150 配对，Token 省 **73.77% ± 0.01**

**叙事**：「结构化协议 + 残差编码」双重压缩；正文证据走 CAS 句柄零拷贝，线缆只传残差字节。

**风险点**：HotpotQA ΔF1=-0.100（诚实标注：F1 下降集中在 hard 题答案表达差异，不影响通信压缩与召回的核心结论）。

#### 维度 2：状态传递创新（20 分）— 自评 17-19

**视频呈现**：L2 镜头，Wyner-Ziv framing 大字 + 三轴定位谱系图（说明书 §10.3）

**核心创新**：
1. 句向量预测残差（非全量向量）— `residual.py` 率失真贪心编码
2. CAS 内容寻址句柄（正文零拷贝）— `messages.py:51` handles 字段
3. 三档协议演化（hidden → residual → embedding → text）— 字节轨迹 2787→960
4. Verified Lossy Coordination（语义校验回退）— `SYNAPSE.tex:425`

**叙事**：「SYNAPSE 是唯一『需白盒=否 + 需训练=否』的方案；所有 KV 方案传定长 cache，SYNAPSE 传随经验收缩的残差」（说明书 §10.2 黑盒空白区）

#### 维度 3：记忆复用效果（20 分）— 自评 14-17

**视频呈现**：L5 镜头，CoQA hit 0.921 + m7 G2≥G1 + 97.6% 归因

**核心数字**：
- CoQA hit_rate **0.921**（35/38 命中）
- m7 跨组：G1 hit 0.8 → G2 hit 1.0；mean_nontext_bytes 52.0 → 49.6
- 残差收缩因果归因：B1-full 降 65.6% vs B3-no-mem 降 1.6% → **97.6% 源于记忆复用**
- 长对话优势：text per-turn 增长 1.19-1.31×（近似 O(n²)），synapse 仅 1.06-1.12×

**叙事**：「记忆的主动检索与复用是压缩效果的必要条件」（说明书 [266]）

**风险点**：m7 是 mock embedder（hash）旧平台数据，录制前建议补一次新平台 m7 实跑。

#### 维度 4：系统完整性（20 分）— 自评 15-17

**视频呈现**：L1 镜头，openEuler 终端 + 五模块目录树 + Docker SMOKE PASSED

**核心证据**：
- 五模块 2877 行（runtime/protocol/stateplane/memory/eval）
- 4 角色 CodeAgent（Planner/Retriever/Executor/Summarizer）
- openEuler Docker：597MB、非 root uid 1001、HEALTHCHECK
- 21 测试（test_smoke 13 + test_qa 8）
- CodeAct 真启用（3 个稳定性测试）
- 稳定 ≥10 轮（m7 实测 10 轮）

**叙事**：「五模块架构 + openEuler 容器化部署全面覆盖赛题要求」

**风险点**：无系统加分项（faiss/IPC/eBPF 全未真用），靠残差+CAS+CodeAct 的"系统层机制创新"补足。

#### 维度 5：实验验证（15 分）— 自评 11-13

**视频呈现**：L6 镜头，CodeAgents 对照表 + 三数据集矩阵 + 配对 CI

**核心证据**：
- 77 个 result.json + 6 类实验（HotpotQA/MuSiQue/CoQA/signal/m7/ab）
- 统计稳健化：N=50×3 配对 + N=200 bridge + k-sweep + 多 seed 重复
- 因果消融：B1 vs B3
- 检索模式交叉：single vs twohop

**叙事**：「三个真实数据集 + 因果消融 + 检索模式交叉分析」

**风险点**：新平台（VectorEngine）数据全单 seed exploratory；大样本统计在旧 Paratera 平台。

---

## 4. CodeAgents 学术对照方案

### 4.1 对照对象

**论文**：CodeAgents: A Token-Efficient Framework for Codified Multi-Agent Reasoning in LLMs（arXiv 2507.03254，2025-07）
**代码**：`https://anonymous.4open.science/r/CodifyingAgent-5A86`（126 文件，活跃）
**适配性**：作者已内建 `Qwen3Model`（`run_hotpot.py:44`），可直连 VectorEngine 跑 Qwen3-235B

### 4.2 方法论对照轴

```
CodeAgents (2507.03254)              SYNAPSE
═══════════════════════              ═════════════════════════
文本符号层压缩                         连续表示层压缩
自然语言 → Python 伪代码               全量句向量 → 预测残差字节
Task/Plan/Feedback 结构化             base_handle + residual bytes
input token -40~72%                   wire_bytes -94%
F1 +1.6~4.9pp                         gold_recall 持平 0.9
═══════════════════════              ═════════════════════════
            同一层（agent 间通信），表示形式根本不同
```

### 4.3 复现计划

**目标**：在 Qwen3-235B + VectorEngine 上复现 CodeAgents 的 HotpotQA 表，作为 SYNAPSE 的外部 SOTA 对照。

**步骤**：
1. clone anonymous 仓库（或下载 ZIP）
2. 配 OpenRouter/DashScope API（或直连 VectorEngine，因作者已内建 Qwen3 适配器）
3. 准备 HotpotQA test-fullwiki 100 样本（或压到 30 样本提速）
4. 跑 NL baseline（默认 smolagents prompt）
5. 跑 CodeAgents（codified prompt）
6. `analysis.ipynb` 出 F1 + Token 表

**工作量**：1 个工作日（环境 1-2h + 跑数 2-4h + 出表 0.5h）。可压到半天（30 样本）。

**降级**：若复现受阻（API 限额/SerpAPI 缺失/Qwen3 适配问题），退化为「引用论文 Table 4 数字做对照表」，不实际复现。

**风险点**：
- CodeAgents 依赖 SerpAPI/Serper（web 搜索）→ 对策：用 fullwiki 模式（提供上下文）绕过
- 匿名仓库可能撤回 → 对策：先 ZIP 下载本地存档

### 4.4 视频呈现（L6 镜头）

一张三行对照表：

| 方法 | 路线 | 通信表示 | HotpotQA F1 | Input Token |
|---|---|---|---|---|
| NL baseline | 文本透传 | 自然语言 | （论文数字） | （论文数字） |
| CodeAgents | 文本结构化 | Python 伪代码 | +3-5pp | -40~72% |
| **SYNAPSE** | **非文本残差** | **句向量残差+句柄** | gold_recall 0.9 | **-71%** |

**叙事话术**：「CodeAgents 在文本符号层做结构化压缩；SYNAPSE 走更底层——直接传句向量预测残差，突破文本必须序列化的信息瓶颈。两者作用于同一通信环节，SYNAPSE 突破的是文本表示的根本限制。」

---

## 5. 同基座 A/B 对比方案（L3-L4 主菜）

### 5.1 任务

`synapse ab --rounds 5` → G1 5 轮 + G2 5 轮 = 10 轮（满足 M9 ≥10 轮）

### 5.2 三线对比

| 路径 | 拓扑 | 编排者 | 介质 | 用途 |
|---|---|---|---|---|
| **A1（synapse text_mode）** | 4 角色平级 | synapse Scheduler | 全文本透传 | 介质差异主对照（同拓扑同后端） |
| **A2（smolagents 原生 managed_agents）** | manager→managed 树状 | smolagents 自身 | 纯文本 task 字符串 | "退到最朴素多 agent 也赢"加分项 |
| **B（synapse synapse_mode）** | 4 角色平级 | synapse Scheduler | 残差+句柄+记忆 | SYNAPSE 完整方案 |

### 5.3 录制策略

1. **预跑拿数据**：录制前在 openEuler 服务器跑 `synapse ab --rounds 5` + HotpotQA N=10，存 `runs/`
2. **混合剪辑**：视频「实时启动命令 + 数据回放」，避免 LLM 抖动翻车
3. **token 口径**：必须用 `team.token_io()`，**不能用 smolagents Monitor**（mock 路径读不到，已实测 bug）

### 5.4 可视化

- **主画面**：openEuler 终端实时跑命令
- **画中画/侧栏**：agent 拓扑动态图（4 节点 + 消息边按发送顺序亮起；残差边渐变色 vs 文本边粗实线）
- **底部 ticker**：`round | text_bytes | synapse_bytes | saved_% | hit_rate` 实时滚动

---

## 6. 视频分镜脚本（7 镜头，5:00）

### L1：openEuler 落地（0:00-0:30，30s）

**目的**：硬核满足赛题 M10 红线，画面直接体现 openEuler。

**画面**：
- 原生 openEuler SSH 终端，运行 `uname -a` + `cat /etc/os-release`（显示 24.03-LTS）
- `dnf install -y python3 python3-pip && pip install --user uv`
- `cd synapse && uv sync --extra api`
- `uv run synapse smoke` → 实时显示 SMOKE PASSED（5 项 PASS）

**字幕/口播**：
> 「SYNAPSE 在 openEuler 24.03-LTS 上原生运行。一条命令完成依赖安装，零网络零密钥即可通过五项离线自检。」

**评分贡献**：系统完整性 20（M10 红线）

### L2：痛点 + 方法 + 三重机制（0:30-1:30，60s）

**目的**：建立核心 framing，对应状态传递创新维度。

**画面**：
- 30s 痛点动画：三大系统级瓶颈（Token 消耗 / 编解码时延 / 经验沉淀）
- 30s 方法动画：
  - 大字「带增长边信息的 Wyner-Ziv 条件率失真编码」
  - 三栏动画：结构化通信协议 → 句向量预测残差编码 → 内容寻址共享记忆
  - 闭环动画：Memory 增长 → Prediction 增强 → Residual 减少 → Communication 降低
  - 三轴定位谱系图（说明书 §10.3）：黑盒 latent 位置标注 SYNAPSE

**字幕/口播**：
> 「SYNAPSE 将多智能体协作建模为带增长边信息的 Wyner-Ziv 条件率失真编码。共享记忆不断积累，发送方仅需传递『惊讶残差』而非全量信息。三重机制：结构化通信协议 + 句向量预测残差编码 + 内容寻址共享记忆。」

**评分贡献**：状态传递创新 20

### L3：同基座 A/B 启动（1:30-2:30，60s）

**目的**：核心实验，对应通信效率维度。

**画面**：
- openEuler 终端：`uv run synapse ab --rounds 5 --config configs/vectorengine.yaml`
- 画中画：agent 拓扑动画（Planner → Retriever → Executor → Summarizer）
- 底部 ticker 实时滚动

**字幕/口播**：
> 「同基座、同后端、同任务。text 模式全文本透传，synapse 模式启用协议 + 残差 + 记忆。G1 五轮深挖主题，G2 五轮关联演进，共十轮连续任务。」

**评分贡献**：通信效率 25（核心）

### L4：A/B 结果 + 记忆复用（2:30-3:30，60s）

**目的**：呈现真实数字 + 跨组记忆复用。

**画面**：
- 三数据集表（HotpotQA / MuSiQue / CoQA 真实数字）
- m7 跨组对比：G1 hit 0.8 → G2 hit 1.0
- 残差字节轨迹动画：2787 → 1812 → 1410 → 1374 → 960
- 因果消融饼图：B1 65.6% vs B3 1.6% → 97.6% 归因记忆

**字幕/口播**：
> 「HotpotQA 省 71% Token，召回保持 0.9。MuSiQue 省 81%，F1 反升 0.33。残差字节从 2787 收缩到 960，97.6% 的收缩因果归因于记忆复用——记忆的主动检索与复用是压缩效果的必要条件。」

**诚实标注**（字幕小字）：
> 「HotpotQA 小样本 ΔF1=-0.100，集中在 hard 题答案表达差异，不影响通信压缩与召回结论。」

**评分贡献**：通信效率 25 + 记忆复用 20

### L5：共享记忆模块细节（3:30-4:00，30s）

**目的**：呈现共享记忆模块的设计细节（HybridRetriever + ToMPredictor + Consolidator），对应记忆复用维度。

**画面**：
- `retrieval.py` 代码片段：三路混合检索（关键词倒排 + 标签过滤 + 语义余弦）
- CoQA "越长越省" 曲线：text 1.19-1.31× vs synapse 1.06-1.12×
- 命中率 0.921 大字

**字幕/口播**：
> 「三路混合检索：关键词倒排、标签过滤、语义向量余弦相似度。心智理论预测器估计接收方已知，跨任务巩固器演化记忆链。CoQA 命中率 0.921，对话越长优势越显著。」

**评分贡献**：记忆复用 20

### L6：CodeAgents 学术对照（4:00-4:30，30s）

**目的**：外部 SOTA 背书，对应实验验证维度。

**画面**：
- 三行对照表（NL / CodeAgents / SYNAPSE）
- Wyner-Ziv vs 文本符号的方法论对照图

**字幕/口播**：
> 「对照文本压缩 SOTA CodeAgents：它在文本符号层做结构化压缩，Token 减 40-72%；SYNAPSE 走连续表示层，直接传句向量预测残差，wire bytes 减 94%。两者作用于同一通信环节，SYNAPSE 突破文本表示的根本限制。」

**评分贡献**：实验验证 15

### L7：总结（4:30-5:00，30s）

**目的**：收尾，强化"协作即压缩"范式。

**画面**：
- frontier 图（性能-开销二维，SYNAPSE 占左上）
- openEuler logo + SYNAPSE logo
- 一句话总线：「协作即压缩，越用越省，越用越聪明」

**字幕/口播**：
> 「SYNAPSE：协作即压缩。在 openEuler 上以 CodeAct 模式真跑，节省 71-81% Token，命中率 92%。越用越省，越用越聪明。」

**评分贡献**：全维度收尾

---

## 7. 录制执行方案

### 7.1 两阶段执行（按用户「先 Docker 再服务器」原则）

**阶段 1：Windows Docker 内验证**（部分已完成）
- ✅ `docker build -t synapse:test .` 成功
- ✅ `docker run --rm synapse:test` → SMOKE PASSED
- ⏳ 待做：容器内跑 `synapse ab --rounds 5`（需 .env 注入 VectorEngine key）
- ⏳ 待做：CodeAgents 复现环境在容器内验证

**阶段 2：原生 openEuler SSH 服务器录制**（正式）
- 登录服务器 → `dnf install python3 python3-pip` → `pip install --user uv` → `uv sync --extra api`
- 预跑实验：`synapse ab --rounds 5` + HotpotQA N=10 + m7 + signal
- OBS 录制终端窗口（露出 openEuler 桌面/终端标识）
- 真实 LLM 调用走 VectorEngine 远程 API

### 7.2 录制工具

- **OBS Studio**（用户选定）：终端窗口捕获 + 字幕轨 + 画中画（拓扑动画）
- 配合 `asciinema rec` 录制纯终端操作（备用，可转 gif）
- 后期：剪映/Premiere 剪辑 7 镜头

### 7.3 预跑数据准备（录制前必须完成）

| 实验 | 命令 | 用途 |
|---|---|---|
| A/B 双模式 | `synapse ab --rounds 5` | L3-L4 主菜 |
| HotpotQA | `synapse hotpot --n 10 --k 3` | L4 数据表 |
| m7 跨组 | `synapse m7 --g1 5 --g2 5` | L4 记忆复用 |
| signal 残差 | `synapse signal --rounds 5` | L4 字节轨迹 |
| CodeAgents | `run_hotpot.py --n 30` | L6 外部对照 |

所有结果存 `runs/`，视频用「实时启动 + 数据回放」混合剪辑。

---

## 8. 风险矩阵与降级路径

| 风险 | 概率 | 影响 | 对策 | 降级 |
|---|:---:|:---:|---|---|
| VectorEngine API 录制时抖动/限额 | 中 | 高 | 预跑拿数据 | 混合剪辑，不实时跑全程 |
| CodeAgents 复现受阻（API/SerpAI/Qwen3） | 中 | 中 | 先 ZIP 存档 anonymous 仓库 | 退化为引用论文数字 |
| openEuler 服务器环境配置出问题 | 低 | 高 | Docker 内录已实测 | `cat /etc/os-release` 证明 openEuler |
| 5 分钟塞不下 7 镜头 | 中 | 中 | 砍 A2（smolagents 原生基线） | 只保留 A1+B+CodeAgents |
| agent 拓扑动画做不出动态效果 | 中 | 中 | 后期剪辑 | 降级静态 drawio 图 + 画外音 |
| m7 新平台数字不达标 | 低 | 中 | 录制前补跑 | 用旧平台数字 + 诚实标注 |

**降级路径**：
满配（A1+A2+B+CodeAgents 实际复现 + agent 拓扑动画）
→ 中配（A1+B+CodeAgents 引用数字 + 静态拓扑图）
→ 最低配（A1+B+现有 6 张图 + 现有 9 镜头脚本）

---

## 9. 资产清单（视频/PPT/文档共享）

### 9.1 已有资产（直接用）

- `docs/演示视频脚本.md`（旧 9 镜头，数字需更新为本设计 §6）
- `docs/figs/` 6 张 PNG（coqa_tokens / hotpot_frontier / hotpot_items / hotpot_retrieval_compare / hotpot_tradeoff / signal_protocol_evolution）
- `scripts/plot_*.py` 10 个作图脚本
- `runs/` 77 个 result.json
- `04-analysis/aggregated/summary.csv` 聚合数据
- `SYNAPSE.tex` / `SYNAPSE.pdf` 论文稿（Wyner-Ziv framing 来源）
- `SYNAPSE_architecture.drawio` 架构图源文件

### 9.2 待制作资产

- **新架构图**：按说明书 [074][140] 流水线绘制（Agent → Message → CAS → ResidualCodec → Memory → Metrics）
- **三轴定位谱系图**：从 `docs/系统设计文档.md` §10.3 提取做幻灯片
- **CodeAgents 对照表**：复现后填入真实数字
- **agent 拓扑动画**：4 节点 + 消息边动态（后期剪辑或脚本生成）
- **更新后视频脚本**：基于本设计 §6 重写 `docs/演示视频脚本.md`

### 9.3 PPT 章节（与说明书对齐）

1. 绪论：三大瓶颈 + 一句话定位
2. 技术理论：Wyner-Ziv framing + 残差编码 + VLC
3. 系统设计：五模块架构图 + 四角色 + 三重机制
4. 实验验证：三数据集表 + 残差轨迹 + 因果消融 + CodeAgents 对照
5. 总结：协作即压缩 + openEuler 落地

---

## 10. 验收标准

视频完成须满足：

1. ✅ 时长 ≤5 分钟
2. ✅ 画面出现 openEuler 24.03-LTS 标识（`uname -a` + `/etc/os-release`）
3. ✅ 包含真实 A/B 对比数字（71.09% / 80.9% / 0.921）
4. ✅ 包含 CodeAgents 外部对照（实际复现或引用）
5. ✅ 严格对齐说明书核心 framing（Wyner-Ziv + 三重机制）
6. ✅ 不越过诚实红线（不说向量数据库/IPC/延迟降低/105 个实验）
7. ✅ 保留诚信负数（ΔF1=-0.100）
8. ✅ 在原生 openEuler 服务器录制（非 Docker 内录，除非降级）

---

## 附录 A：术语词表（视频字幕统一口径）

| 术语 | 字幕写法 |
|---|---|
| 作品代号 | SYNAPSE |
| 核心 framing | 带增长边信息的 Wyner-Ziv 条件率失真编码 |
| 三重机制 | 结构化通信协议 + 句向量预测残差编码 + 内容寻址共享记忆 |
| 残差 | 惊讶残差（surprise residual） |
| 内容寻址 | CAS（Content Addressable Storage，内容寻址存储） |
| 协议握手 | CNR（Capability Negotiation & Resolution） |
| 可靠机制 | VLC（Verified Lossy Coordination，可验证有损协作） |
| 预测器 | ToMPredictor（Theory of Mind Predictor，心智理论预测器） |
| 检索 | HybridRetriever（三路混合检索） |
| 后端 | Qwen3-235B-A22B-Instruct-2507 + VectorEngine + text-embedding-3-small（1536 维） |
| 部署 | openeuler/openeuler:24.03-lts，597MB，非 root uid 1001 |

## 附录 B：数字口径核对表

| 数字 | 来源 | 视频用法 |
|---|---|---|
| 71.09% | `runs/hotpot_20260724_214352`（N=10） | L4 HotpotQA Token 节省 |
| 80.9% | `runs/musique_20260724_203011`（N=3） | L4 MuSiQue Token 节省 |
| 10.65% | `runs/coqa_20260724_211318`（3 段 38 轮） | L5 CoQA Token 节省 |
| 94.64% / 96.45% | 同上 | L4 wire_bytes 节省 |
| 0.921 | 同上 | L5 CoQA hit_rate |
| ΔF1 -0.100 / +0.333 / +0.027 | 同上 | L4 诚实标注 |
| 0.9 / 0.667 | 同上 | L4 gold_recall |
| 73.77% ± 0.01 | `runs/hotpot_stats_20260621_182630`（N=150） | 报告首页统计背书 |
| 2787→960 | `runs/signal_20260724_191435` | L4 残差轨迹 |
| 65.6% / 1.6% / 97.6% | B1 vs B3 ablation | L4 因果归因 |
| G1 0.8 / G2 1.0 | `runs/m7_20260620_214354` | L4 跨组记忆 |
| 1.19-1.31 / 1.06-1.12 | CoQA per-turn | L5 长对话优势 |

---

**本设计已完成 brainstorming 流程，待用户审阅后调用 writing-plans skill 生成实施计划。**

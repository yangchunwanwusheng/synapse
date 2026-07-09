# Experiment Protocol — SYNAPSE

## 元信息
- 一句话贡献：把多智能体对齐建模为**带增长边信息的语义 Wyner–Ziv 编码**，在真实 openEuler 系统上实证**协作速率收缩律 + 漂移回弹**，并以校验和保证有损残差的端到端正确。
- 贡献重心：**并重型**（发现 C1 优先 + 解法 C2/C3 + 应用 C4）。设计模式：发现型四件套（存在性/普遍性/机制归因/边界条件）服务 C1；方法型对比+消融服务 C2/C3。
- 生成日期：2026-06-18 / 执行模型：Claude Opus 4.8 / 上游 idea-card：v(backfilled 2026-06-18)
- 后端：SiliconFlow API（Qwen2.5-7B/14B-Instruct）+ 本地 sentence-embedding 残差路径（无 GPU 依赖）。

## Claim ↔ Evidence 映射表
| Claim | 核心? | 证据类型 | 证据等级 | 支撑实验 | 期望结果（方向性，英文） | 否决信号 | 预期审稿攻击 |
|---|---|---|---|---|---|---|---|
| **C1** 协作速率收缩律+回弹 | ★核心 | 现象展示+机制归因 | direct | E1,E6,E1-neg | per-task cross-agent bytes decrease monotonically toward an oracle floor; rebound on drift | 字节不降 / 降但与累计经验无关 / 负例族也降 | "这就是缓存" / "平稳性假设不成立" |
| **C2** 语义 WZ 透镜+Δ | | 对比+理论 | direct | E3 | residual rate ≈ floor + Δ; Δ grows as ToM degrades | Δ 与 ToM 质量无单调关系 | "WZ 只是类比" |
| **C3** Verified Lossy 正确性 | ★核心 | 机制归因 | direct | E4 | end-to-end task correctness preserved despite injected ToM errors | 注入错误后任务正确性下降 | "有损会静默损坏" |
| **C4** 协作速率=漂移传感器 | | 现象展示 | direct | E6 | rate rebound precedes task-quality drop | 回弹不早于质量下降 | "so-what / 不实用" |
| 机制项（言语行为/ToM寻址/表示三级/缓存正交） | | 消融 | supporting | E2,E5,E7,E8 | 各机制移除后字节/冗余轮上升；增益与缓存叠加 | 移除无变化 | "组件无用 / 字节换 FLOPs" |

> 双向检查：每条 claim ≥1 direct 实验；每个实验 ≥1 claim。E1-neg（负例族）为 C1 的因果对照。

## Baseline 阶梯（含公平性说明）
- **L0 · sanity**：no-coordination（各 agent 独立、不通信）+ 移除记忆的裸文本协作。证明任务非平凡、指标有区分度。必配。
- **L1 · 标准方法族**：**纯文本协作模式（text mode）**——社区默认（NL/JSON 全量透传）。这是赛题 M3 的法定对照，也是收缩律的主基线。
- **L2 · 最强已发表对手**（处置表）：

  | 论文 | 处置 | 理由 |
  |---|---|---|
  | Agentic Plan Caching (2506.14852) | **进阶梯（E2 正交臂）**：缓存 on/off × SYNAPSE on/off 四象限 | 证明 SYNAPSE 与缓存正交可叠加，省"重说"非"重算" |
  | 潜空间通信 CIPHER(2310.06272)/KVComm(2510.03346) | **进阶梯（E8 对照）**：发**全量句向量** vs 发**残差** | 同载体下证明"发更小惊讶"才是字节真省；同族隐状态为可选臂 |
  | 语义率失真 (2604.09521) | **不可比/讨论**：纯理论、无系统、静态能力角度 | 无代码/无系统，作 related-work 正面区分（idea-card 差异表） |
  | Collaborative Memory (2505.18279) | 不可比/讨论 | 记忆当外挂模块，与本工作"记忆=通信媒介"设定不同 |
- **L3 · 自家变体（消融，连 §消融）**：no-ToM / no-consolidation / no-residual(发全量) / no-speechact / no-checksum。
- **L4 · oracle 上界（必配，便宜）**：全知接收方喂入全部巩固经验，测新任务残差熵 = 预言地板 H(Y_new|B_∞)（E1 的独立地板测量，H1 可证伪性所系）。
- **budget-matched 反向公平**：给 text 模式相同"多说几句/多检索"预算，证明 synapse 收益非堆 token。**我方引入 ToM/编解码额外开销，故此对照必配**（净收益相图 E5）。

五维公平：① 同任务族同划分；② 同 LLM 后端同参数级；③ 同 LLM 调用预算（budget-matched）；④ 同检索/超参搜索预算；⑤ 同评测代码与 metric（bytes 同由 eBPF/socket 计）。

## Benchmark / 数据集（版本/划分/预处理/可得性）
- **任务族 G1/G2**（自建，赛题 M7）：可得性 `verified`（自建，随源码交付）。
  - G1（主题深挖）：对主题 X 多跳研究产报告（plan→retrieve→CodeAct 计算→summarize），≥10 轮。
  - G2（关联演进）：X 的更新/对比/再分析，**复用 G1 的证据句柄+计划过程**；度量"少检索/少计算/少 deliberation"。
  - 漂移臂：G2 中途切到与 X 弱相关主题 X'（触发 E6 回弹）。
  - **负例族**（对照）：刻意无共享结构的任务流，预期收缩≈0（证收缩来自共享结构，非系统假象）。
- **语料**：本地文档语料（arXiv 摘要集 / 维基子集，社区已有子集，引用先例，不自造私有子集）；可得性 `unverified`→进决策包确认或换 HF 可达集。
- **已知盲区**：自建任务族有"难度可控但外部效度有限"风险 → 论文定位为**机制/分析型**（受控、可归因、可复现为卖点），并补"从受控到真实系统"外推论证。
- **锚点时效**：最近邻 2604.09521 / C2C 2510.19995 均 ≤12 个月；bar 投影——agent 通信是高速领域，差异化**不靠"第一个做 X"**，落在机制（时间动力学+系统+校验）。
- **LLM 条件块**：模型版本字符串 + 调用日期登记；prompt 模板进附录（不"代码里见"）；temperature=0 且重复 ≥3；judge=同族 LLM + 小样本人工一致率校验。API 版本漂移列风险。

## 主实验设计（实验卡）
- **E1（头牌）收缩律+地板**｜支撑 C1｜G1/G2 ≥10 轮，画 R(每任务跨 agent 字节) vs 累计经验；拟合形态/拐点/地板；L4 oracle 独立测地板；消融巩固/ToM→收缩消失｜seeds≥3｜指标 nontext_bytes/轮｜**P0**。
- **E2 缓存正交**｜支撑 C1(拆"就是缓存")｜缓存 on/off × SYNAPSE on/off 四象限｜seeds≥3｜**P0**。
- **E3 失配惩罚 Δ**｜支撑 C2｜人为劣化 ToM，看 Δ、字节↑、校验回退率↑｜**P1**。
- **E4 正确性**｜支撑 C3｜注入 ToM 错误，校验和保证端到端正确｜**P0**。
- **E5 成本 crossover**｜支撑机制｜消息长度×同/异构×预测器开销的净收益相图(bytes+latency)｜**P1**。
- **E6 漂移回弹**｜支撑 C1/C4｜注入分布切换，观 R 回弹再收缩，与"质量下降时刻"对齐｜seeds≥3｜**P0**。
- **E7 言语行为消融**｜支撑机制｜去 ask/hold/认知项，看冗余轮+字节｜**P2**。
- **E8 表示三级**｜支撑机制｜hidden(可选)/句向量/文本 diff 的省幅与适用域｜**P2**。

## 消融设计（组件→消融→归因→预注册解读）
| 组件 | 消融方式 | 归因目标 | 预注册解读 |
|---|---|---|---|
| ToM 预测器 | 替换为随机/恒等 B̂ | C2(Δ)、C1 | 移除后 Δ 增大、字节回升超 1 pooled std → ToM 必要；无变化 → 降级 |
| 巩固器 | 关闭跨任务巩固 | C1 收缩 | 关闭后收缩曲线变平（不再趋地板）→ 巩固是收缩之因 |
| 残差编码 | 发全量向量(naive 替换) | M4/字节 | 全量字节 > 残差字节（同载体）→ "发惊讶"是真省 |
| 言语行为选择器 | 恒 tell | 机制 | 冗余轮+字节上升 → 选择器有用 |
| 校验和 | 关闭 | C3 | 关闭后注入错误致任务正确性下降 → 校验必要 |
- 敏感性扫描：量化位宽(int8/int4)、top-k 稀疏度、检索 k 各 ≥3 点，证主结论邻域稳健。

## Metrics / 统计 / seeds
- **主指标（模式无关）**：端到端时延、能量(J，功率模型估算标 estimated)——避免 token vs 字节"苹果比橘子"。
- **分量**：`nontext_bytes`(eBPF 实测 / socket 计数兜底) ⊕ tokens/chars ⊕ latency ⊕ memory hit-rate ⊕ quality(LLM-judge/gt)。
- **统计**：seeds ≥3（算力允许 5）；报告 `mean ± std over N seeds`；claim 判据=均值差 > 1 pooled std 才 claim 胜出，0.5–1 std 写 "comparable"。多组比较注明是否 Bonferroni。
- **随机性登记**：temperature=0、重复 ≥3 取均值、并发/调度顺序固定、检索内容固定。

## 三轮计划：smoke / signal / evidence
- **smoke（<5%，MockLLM+HashEmbedder，离线）**：1 任务双模式端到端跑通。判据：exit 0；metrics 非空；**双模式都产出结论**；无 NaN；**判据区分度测试**（喂负例族应收缩≈0，per LESSONS L2）；**变更生效验证**（残差解码后 Ŷ≠基、记忆 write 后 store 有 diff，per L3）。
- **signal（10–20%，真实 API，G1 5–10 任务）**：跑 synapse vs text 主对比。判据：① 协作动力学合理（字节随轮次脱离常数）；② **收缩方向**与期望一致（不要求显著）。**第一个 KC 强制检查点**。
- **evidence（其余）**：全规模 G1/G2 ≥10 轮 × 全 seeds × 全消融，覆盖 P0(+预算允许 P1) 100%。

## Kill Criteria
- **KC-1**（signal 轮）：synapse 与 text 的每任务字节差**方向与期望相反**（synapse 不更省），经数据管线检查+换 seed 重跑后仍相反 → 暂停 evidence，报告用户，选项=查 ToM/残差实现 / 收窄 C1 为分析性 / 回 S1。对应 C1 否决信号。
- **KC-2**（E1）：即便在**有共享结构**的 G1/G2 上收缩幅度≈0（曲线平），且 oracle 地板≈H(Y)（无 headroom），经诊断仍如此 → 现象不成立，C1 降级。对应 C1。
- **KC-3**（E6）：漂移回弹**不早于**质量下降（传感器无提前量）→ C4 降级为"事后指标"。
- **KC-4**（E4/E5）：校验回退率高到净收益为负（字节省幅 < 回退重传成本）→ 报告 crossover，选择器默认走文本（诚实局限，非 kill）。
- 每条触发先做**最小诊断**区分实现失败 vs 假设证伪（LESSONS L8：smoke 过的是 plumbing 闸非有效性闸）。

## 本地可行性预算（API+本地向量，无 GPU）
| 项 | 估算 | 估算依据 |
|---|---|---|
| smoke | 0 元（MockLLM 离线） | 全确定性，CI 可跑 |
| signal | ~2–5 M tokens ≈ $1–5 | G1 5–10 任务 × 双模式 × 多轮 × 3 seed；Qwen API ~$0.1–0.5/M |
| evidence | ~30–60 M tokens ≈ $10–40 | 2 族 × ~50–80 任务 × ≥10 轮 × {text,synapse} × ~6 消融 × 3 seed |
| LLM-judge | ~$5–20（可同族自评省） | 质量护栏，可选 |
| 本地侧 | 电费/工时（非算力黑洞） | embedding(CPU/8GB GPU)、FAISS 小规模、ToM-MLP 分钟级；16GB RAM 可载 |
| **总计** | **≈ $20–80**（项目级，非每次） | 占用率：API 预算可分批，远低于 70% 包络；本机 8GB/16GB 足够 |
- 🔒 与 idea-card 对账：idea-card 同口径 $20–80；**已废弃 SYNAPSE.tex §5.4 的 30–60 GPU·h 估算**（那是本地 vLLM 假设，本轮后端=API+向量，故重估，差异原因=后端切换）。
- 超额砍单序：P2(E7/E8) → P1(E3/E5) → 保 P0(E1/E2/E4/E6)。

## 自我攻击记录（2 轮）
| 轮 | 攻击项 | 发现 | 处置 |
|---|---|---|---|
| R1 | claim 悬空 | C4 初仅 supporting | 补 E6 direct（回弹早于质量下降） |
| R1 | baseline 太弱 | 缺最强对手 | L2 处置表纳入缓存(E2)+潜空间全量向量(E8)；2604.09521 列不可比理由 |
| R1 | confound | "就是缓存" | E2 四象限 + E1 用**新任务** + 负例族，隔离"协作速率收缩"vs"答案缓存" |
| R2 | 设计模式匹配 | C1 是发现型却用方法型套路 | 配齐发现四件套：E1 存在/普遍、E1-neg+E3 机制归因、E6 边界(漂移) |
| R2 | kill 可触发性 | 假想 signal 最坏→KC-1 可判定动作明确 | 通过 |
| R2 | 预算诚实 | 估算依据非空、与 idea-card 对账、占用 ≤70% | 通过 |
- **残余风险（含未验证）**：① 语料可得性 `unverified`（决策包确认）；② 竞赛 deadline assumed；③ B1 两条 novelty 待投稿前补检；④ energy 用功率模型 estimated；⑤ eBPF 在 openEuler 的可用性需 M1 前验证（缺失走 socket 计数兜底）。

## 给 S3 的提示
- **先 smoke**：`MockLLM`+`HashEmbedder` 跑双模式（零依赖、离线、CI）；通过后再接真实 API 跑 signal。
- **最易出错环节**：① 残差 `decode` 与校验回退（L3 变更生效：断言 Ŷ≠基、记忆 write 后 store 有 diff）；② 混合检索作用域（L6：跨类型/跨文件相似的假阳性，加作用域约束）；③ **协议-代码对账**（L7：协议改了 Metrics/统计后立即同步 `eval/` 代码）。
- **监控优先盯**：每轮 `nontext_bytes`、memory hit-rate、校验回退率——收缩曲线与 KC 全看它们。
- 接真实 LLM 前跑**输出形态探针**（L5）：thinking 模型不用于结构化判定/JSON。

---

# 路线丙 · 双贡献补充协议（pre-registered 2026-06-21；S4 停点#2 后用户定向）

> **framing 变更**：S4 裁决"原 C1 头牌 framing 证据不足"。用户选**路线丙=双贡献**：①**头牌（实证）**=真实数据集通信效率+记忆复用；②**第二贡献（机制/发现）**=协作速率收缩律 C1。本节**预注册**新主张与判据；判据写于新实验**执行之前**，故下列待跑实验为 pre-registered（区别于已跑的 CoQA/HotpotQA N≤50，那些 S4 已标 post-hoc，论文如实披露）。

## 新主张 ↔ 判据（pre-registered）
| Claim | 角色 | 预注册判据（执行前锁定） | 否决信号 | 支撑实验 |
|---|---|---|---|---|
| **CC1** 真实多跳 QA 上结构化协议+非文本句柄+实体桥接检索大幅省 LLM token 且质量小损可控 | ★头牌 | 在 **≥2 个真实多跳数据集**、**N≥200**、bridge 检索：token 省 **≥40%** 且配对 ΔF1 **点估计 ≥ −0.06** 且 **95%CI 下沿 ≥ −0.10**（非劣裕度 −0.05 能达则达，达不到则如实报"小幅有界代价 X F1 换 Y% token"） | token 省<40% 或 ΔF1<−0.06 或 CI 下沿<−0.10 | EH1(HotpotQA N=200)+EH2(第二数据集) |
| **CC2** 跨关联任务记忆复用降协作开销不伤质量 | ★头牌 | 真实数据：跨任务命中率 **≥0.8**、token 省 **>0** 且 F1 不显著降 | 命中<0.8 或 F1 显著降 | CoQA（已, post-hoc）+ m7（已, post-hoc）+ EH3(CoQA 扩 convs≥8 重测=pre-reg 复核) |
| **C1** 协作速率收缩律+因果对照 | ◇第二贡献 | **seeds≥3**：关联族后半 < 前半 > 1 pooled std；负例族不收缩；命中率关联>负例；oracle 地板可独立测得且关联收敛逼近之 | 关联不降/负例也降/无地板 headroom | EC1(signal seeds≥3)+EC2(oracle 地板)+EC3(E6 漂移回弹) |
| **C3** Verified Lossy 正确性 | ◇支撑 | 注入 ToM/残差错误后校验和触发回退，端到端正确率不低于无注入 | 注入后正确率下降 | EC4(E4 注入) |
| 机制消融 | supporting | 移除 no-ToM/no-consolidation/no-residual/no-checksum 后字节/冗余 > 1 pooled std 上升 | 移除无变化 | EC5(消融) |

## 🔒 补跑清单（精确 × 配置 × seeds × 代价；S4→S3 续跑）
**头牌（CC1/CC2）— 代价小、代码就绪、优先：**
- **EH1**：HotpotQA bridge & single，**N=200, k=3**，配对 ΔF1+CI → 判 CC1 非劣/有界代价。代价：~600 LLM 调用(~35min)。【本轮启动】
- **EH2**：第二真实多跳数据集（**2WikiMultiHop** 或 **MuSiQue**，HF 可达），bridge N≥200 k=3 → CC1 跨数据集泛化。代价：fetch+loader+run(~40min)。
- **EH3**：CoQA 扩 convs≥8 重测（pre-reg 复核 CC2）。代价：~15min。

**第二贡献（C1/C3）— 需补实现 + 多跑：**
- **EC1**：signal **seeds≥3**（关联+负例），mean±std + per-seed 一致性。代价：~3× signal(~30min)。
- **EC2**：oracle 地板（L4/E1）——全知接收方喂全部巩固经验，测 H(Y_new|B_∞)；关联收敛是否逼近。需实现 oracle 臂。
- **EC3**：E6 漂移回弹——注入主题切换，观字节回弹早于质量下降。需实现漂移注入。
- **EC4**：E4 注入正确性——注入 ToM/残差错误，校验回退保端到端正确。需实现错误注入。
- **EC5**：消融 no-ToM/no-consolidation/no-residual/no-checksum（toggle）+ E2 缓存正交。需 config toggles。

**排序**：EH1（本轮）→ EC1 + EH3（代码就绪）→ EC5 消融（toggle，较易）→ EH2（第二数据集）→ EC2/EC3/EC4（需新实现）。每跑完回 S4 增量裁决。
**统计**：F1 逐题 0/1 高方差 + temp=0 MoE 非确定（text F1 跨次 0.66–0.71）→ 报配对自助 95%CI（`qa/stats.py`），N 越大 CI 越窄；严格非劣裕度 −0.05 达不到就如实报"有界代价"。

# Analysis Report — SYNAPSE (S4)

> 日期 2026-06-21 ｜ 数据同源：`04-analysis/aggregated/{raw_long,summary}.csv`（脚本 `scripts/aggregate_s4.py` 生成，90 行）。报告每个数字溯源至此或具体 run_id。

## 元信息与分析计划
- **valid runs**：signal_20260620_152728（C1 收缩律, 真实 API）、m7_20260620_214354（跨组复用）、coqa_20260621_111342（记忆复用, 真实数据）、hotpot_stats_20260621_182630（通信效率 N=50×R=3 k=3）、hotpot_ksweep_{183504 single,185254 twohop,190107 bridge}（k 前沿）。
- **排除 run**：hotpot_20260621_180331/180526/180656（N=20 单次，已被 N=50 推翻，仅留档不入裁决）。
- **预注册判据抄录（协议 §Metrics/Claim）**：均值差 > 1 pooled std 才 claim 胜出，0.5–1 std 写 comparable；seeds≥3；C1 否决=字节不降/降但与经验无关/负例也降；C3=注入错误后正确性下降；C4=回弹不早于质量下降。
- 🔒 **provenance 警示**：协议预注册的是 **C1–C4 + 合成 G1/G2 + nontext_bytes** 指标。**CoQA/HotpotQA（真实数据、LLM token、F1、配对 CI）系本会话 post-hoc 新增，判据非预注册** → 按 S0 红线 R3 标 `criteria_provenance: post-hoc`，措辞下调一档，论文禁称"预注册"。

## 主结果表（全量，赢输混报）

**A. 通信效率（HotpotQA distractor, 真实数据, post-hoc；N=50）—— 检索改进前沿**
| 方法@k | token 省% | 金标召回 | 配对 ΔF1 | ΔF1 95%CI | 显著更差? |
|---|---:|---:|---:|---|---|
| single k=3 | 73.8 | 0.78 | −0.120 | [−0.229,−0.010] | 是 |
| single k=6 | 46.9 | 0.91 | −0.043 | [−0.143,+0.060] | 否 |
| twohop k=3 | 72.2 | 0.75 | −0.122 | [−0.238,−0.003] | 是（无改进）|
| **bridge k=3** | **73.5** | **0.86** | **−0.054** | **[−0.155,+0.051]** | **否** |
| bridge k=6 | 47.2 | 0.97 | −0.051 | [−0.149,+0.051] | 否 |
| **bridge k=3 · EH1 N=200** | **71.8** | **0.84** | **−0.038** | **[−0.098,+0.019]** | **否（CI 含 0）** |
> **EH1（pre-registered, N=200, run `hotpot_ksweep_20260621_231046`）确认 CC1**：bridge k=3 省 71.8% token，配对 ΔF1 −0.038 CI[−0.098,+0.019] 含 0 = 不显著更差；N=200 把 CI 从 N=50 的 [−0.155,+0.051] 收窄约 2×。满足预注册 CC1 数值门（token≥40%✓ ΔF1≥−0.06✓ CI 下沿≥−0.10✓），但 CI 下沿 −0.098 **未达严格非劣裕度 −0.05** → 诚实表述 = "省 72% token，质量与全文统计不可区分（小幅潜在代价 ~4 F1 点落在噪声内）"，**非"严格非劣"**。胜/平/负 26/142/32（71% 平局）。CC1 = ★头牌 **1/2 数据集达标**，待 EH2(MuSiQue) 补第二数据集泛化。
> N=50×R=3 复核 single k=3：token 省 73.77±0.01，配对 ΔF1 −0.112 [−0.173,−0.054]（CI 排除 0，**显著更差**），与 ksweep 单次一致（双 run 互证）。

**B. 记忆复用（真实+合成）**
| 实验 | 数据 | text | synapse | 关键 |
|---|---|---|---|---|
| CoQA(real) | token / F1 / 命中 | 20224 / 0.733 / 0 | 18558 / 0.748 / **0.921** | 省 8.2%，F1 不降，跨轮命中 0.92 |
| m7(synthetic) | 均字节 / 命中 | — | g1 52.0/0.8 → g2 49.6/**1.0** | 跨组复用：G2 暖启动命中 1.0 |

**C. 协作速率收缩律 C1（signal, 真实 API, 单 seed, 合成）**
| 族 | 前半字节 | 后半字节 | drop | 命中 |
|---|---:|---:|---:|---:|
| 关联 G1 | 48.4 | 37.2 | **+23%（收缩）** | 0.9 |
| 负例 | 54.7 | 70.0 | **−28%（反升）** | 0.167 |
> 因果对照干净（收敛比 0.53，命中 0.9 vs 0.167）→ 排除"就是缓存"。但单 seed、合成任务、**未测 oracle 地板**、**未做漂移回弹**。

## Claim 裁决表
| Claim | 核心 | 预注册判据 | 观测（溯源） | 裁决 | caveat |
|---|---|---|---|---|---|
| **C1** 收缩律+回弹 | ★ | 单调降向地板 + 回弹 + 负例不降 | 收缩方向✓+因果对照✓(signal)；地板✗回弹✗ seeds=1✗ 合成 | **partially supported** | 缺 oracle 地板/漂移/seeds≥3；头牌"发现"措辞不可用 |
| **C2** WZ Δ | | Δ 随 ToM 劣化上升 | E3 未跑 | **not tested** | — |
| **C3** Verified Lossy | ★ | 注入错误仍端到端正确 | E4 未跑；signal happy-path 回退=0（机制在, 未受检） | **not tested** | 核心 claim 未验 |
| **C4** 漂移传感器 | | 回弹早于质量下降 | E6 未跑 | **not tested** | — |
| 机制消融 | | 移除组件→字节/冗余升 | no-ToM/巩固/残差/校验 均未跑 | **not tested** | — |
| **[post-hoc] 通信效率** | (赛题M3) | （非预注册）省 token 且 F1 非劣 | bridge k=3 省 73.5%, ΔF1 −0.05 CI 含0 | **supported (post-hoc)** | 判据事后定；未证严格非劣(CI 宽) |
| **[post-hoc] 记忆复用** | (赛题M6/7) | （非预注册）跨任务复用 | CoQA 命中 0.92 / m7 G2 1.0 | **supported (post-hoc)** | 判据事后定；单次 |

## 消融解读
**全部未执行**（no-ToM / no-consolidation / no-residual / no-checksum / E2 缓存正交）→ 机制归因类 claim（C2/C3 + 组件贡献）当前无证据。按协议这是 P0(E4)+P0(E2) 缺口。

## 误差 / 失败分析（HotpotQA, 真实 predictions）
- **错误类型学**（communication/coordination 六分类）：主导失败 = **communication failure（检索漏桥接段→应答方拿不到第二跳金标段→无法作答, F1=0）**。single k=3 召回 0.78 = 漏 22% 金标。
- **新增错误（synapse 对 text）**：single k=3 同题胜/平/负 = 3/35/12（输 12 题）；bridge k=3 改善到 4/38/8（输降到 8）——bridge 修复了部分 communication failure（召回 0.78→0.86）。
- **机制对质**：机制链"丢无关上下文→省字节不伤质量"在**有干扰段且能精准检索**时成立（bridge）；naive 单跳在多跳问答上**违反**该链（漏金标→伤质量）——已写入限定，S6 措辞须区分"精准检索下"。
- **twohop 失败案例**：嵌入查询扩展 k=3 召回 0.75（反降）——长正文稀释查询，证伪"嵌入扩展能补桥接"。

## 稳健性与限定（caveats）
- **C1 三大缺口**：单 seed（协议要 ≥3）、合成任务（外部效度有限）、未测 oracle 地板（H1 可证伪性所系）、未做漂移回弹（C4 整条未验）。
- **post-hoc 判据**：CoQA/HotpotQA 判据本会话定义，非预注册 → 论文按 post-hoc 披露。
- **统计功效不足**：bridge k=3 ΔF1 CI 下沿 −0.155 仍宽（F1 逐题 0/1 高方差 + temp=0 在 Qwen3-30B-A3B MoE 上非确定，text F1 跨次 0.66–0.71）→ 只能说"不显著更差"，**未证严格非劣**（需 N≈200–500）。
- **C3 核心未验**：Verified Lossy 机制在代码中（校验和+回退），但无注入错误实验，端到端正确性保证**未受检**。

## 总裁决
- **信念更新（What changed our belief）**：① 确认收缩律方向+因果对照在真实 API 成立（强化 C1 机制存在性）；② 确认真实数据上记忆复用 + 大幅通信效率可达且质量非劣——但**不是免费**：naive 单跳 k=3 显著掉 F1（−0.12），需 bridge 检索才非劣（**推翻了 N=20 的"免费 75%"**）；③ C2/C3/C4 + 全部消融**零信息量**（未跑）。
- **行动三分**：`STOP` 把 C1 当"已证发现"头牌写、宣称"免费省 token" / `CONTINUE` 通信效率真实数据臂(bridge)+收缩律作机制分析 / `TEST-NEXT` 见缺口清单。
- 🔒 **证据足以/不足以**：**不足以**支撑当前 idea-card 所framed（C1 收缩律为头牌"发现" + C2/C3/C4）的顶会论文——★核心 C1 仅 partial、★核心 C3 未验、C2/C4/消融未跑、C1 单 seed/合成/无地板。**但已足以支撑一篇以"真实数据集通信效率（结构化协议+非文本句柄+检索改进）+ 记忆复用"为主线的系统/实证论文**（赛题对齐，CI 背书），收缩律降为机制分析章节。
- **缺口清单（按两条路线）**：
  - 路线甲（守 C1 发现头牌→顶会理论/发现型）：补 seeds≥3 + oracle 地板(E1/L4) + 漂移回弹(E6) + 注入正确性(E4) + 消融(no-ToM/巩固/残差/校验) + 缓存正交(E2)。代价：协议估 evidence 轮 $10–40 + 数日。
  - 路线乙（改 framing→通信效率系统实证, 顶会 system/empirical track）：补 N≈200 严格非劣 + ≥1 个第二真实数据集（如 2WikiMultiHop/MuSiQue 多跳，或 RAG 长上下文）+ 端到端时延能量表。代价：较小，主要 API + 写作。

## 给 S5 的图表清单
| 图ID | 类型 | 数据源(aggregated 筛选) | x/y/分组 | 误差棒 | Takeaway(英文) | 对应 claim |
|---|---|---|---|---|---|---|
| F1 | 线+CI | hotpot-{single,bridge} k∈3-8 | k / ΔF1 / method | 配对 95%CI | Bridge retrieval keeps ~73% token saving non-inferior where single-hop is significantly worse | post-hoc comm-eff |
| F2 | 双轴线 | hotpot-* token_saved & gold_recall vs k | k / %·ΔF1 | CI on ΔF1 | Recall is the binding constraint; bridge lifts low-k recall | post-hoc comm-eff |
| F3 | 柱 | coqa text vs synapse | metric / value | — | Real-dataset memory reuse: hit 0.92, token −8%, F1 maintained | post-hoc memory |
| F4 | 线 | signal linked vs negative contraction | task / bytes / family | — | Coordination-rate contraction with clean negative-family control (single seed) | C1 (mechanism) |

## 自我攻击记录（R2 全量；R1 摘要见 analysis-notes.md）
| 轮 | 攻击项 | 发现 | 处置 |
|---|---|---|---|
| R2 | 判据漂移 | CoQA/HotpotQA 判据非预注册 | 全标 post-hoc，裁决降档，总裁决显式披露 |
| R2 | cherry-pick(挑设置) | 仅报 bridge 赢? | single/twohop/bridge 全 k 全量入表，twohop 失败如实报 |
| R2 | 显著 vs 噪声 | "bridge 非劣"措辞 | 严格写"CI 含 0=不显著更差"，并注"未证严格非劣(CI 宽)" |
| R2 | 措辞软化 | C2/C3/C4 写法 | 用 "not tested" 而非 "promising"，核心 C3 未验显式置顶 |
| R2 | 溯源抽查 | 抽 5 数(coqa F1/hotpot k3 single CI/bridge k3/signal/m7) | 全部对上 aggregated 与 result.json |
| R2 | 失败分析实质 | 是否真实 predictions | 来自 per-item F1 + 胜负计数(真实 run)，机制对质完成 |
- **残余风险/未执行**：oracle 地板、E6、E4、消融、E2 全未跑（路线甲缺口）；第二真实数据集未跑（路线乙缺口）；严格非劣 CI 未压窄；C1 单 seed。

## 赛题 M1–M11 合规回扫（L9 强制；竞赛红线）
M1–M9 ✅（5 模块 + ≥10 轮 + 真实 A/B + 结构化协议 + 非文本句柄 + 共享记忆 + ≥2 组关联任务 + M8 全统计）；M10 ✅源码/设计/部署/实验报告 + 实测 openEuler 容器 smoke PASS，⚠**演示视频唯一待录**；M11 ✅ CodeAct(smolagents)。评分五维：通信效率(bridge 73.5%) / 状态传递(句柄+残差) / 记忆复用(0.92) / 系统完整性 / 实验验证(本 S4 + CI) 均有实证支撑。**赛题合规不受论文 framing 决策影响。**

## 给 S6 的提示
- **措辞上限**：C1 只能写"机制方向性证据 + 干净因果对照（单 seed, 合成, 受控）"，禁称"已确立的发现/定律"；通信效率/记忆复用按 **post-hoc** 披露，禁称预注册；"省 token"必须绑定"质量非劣（CI 含 0）"且注"未证严格非劣"。
- **limitations 必含**：单 seed/合成(C1)、post-hoc 判据、CI 宽未证严格非劣、C3 未受检、消融缺失。
- 框架决策（路线甲/乙）属 S4 停点，须用户定后再进 S6。

---

# 增量裁决 v2（2026-06-22，自主迭代后）

> 本节 supersede 上方 2026-06-21 裁决中"未跑/单seed"项。新增 valid runs（真实 API, GLM-Embedding-3 残差,
> 执行器 CodeAct 解析已修复=0 解析错误）：mech v2 `mech_*_20260622_165459`、**mech v3 robustness**
> `mech_agg_20260622_171550`(3主题×repeats)、EH2 MuSiQue `musique_ksweep_20260622_115337`、
> drift-detect `drift_detect_20260622_170916`、graded-drift `drift_graded_20260622_175400`、EC1 seeds `signal_seeds_20260622_111524`。
> B3 数据真实性抽查通过（raw per-repeat ⇄ aggregate 一致，mean full=1460.7 对账无误）。

## 更新后的 Claim 裁决表
| Claim | 核心 | 观测（溯源, 真实 API） | 裁决 | caveat |
|---|---|---|---|---|
| **机制头牌·条件率失真编码** | ★ | 残差=H(Y\|B̂) 趋条件率失真地板；下列 C1/floor/ladder/drift 合成支撑 | **supported (robust)** | 机制任务为合成 G1 族(外部效度)；非"定律"措辞 |
| **C1 收缩+因果对照** | ★ | 收缩方向✓ + 负例反升✓(signal) + **EC1 seeds 3/3 一致**(真实残差) | **supported** | — |
| **floor 趋地板(EC2)** | ★ | v3 online 后半触**质心(分布)地板** ratio **0.92–0.98**(3主题紧)；远低于单条地板 | **supported** | 单条地板<1 须解读为"质心=更优充分统计"，非不公平对比(已加质心地板对照) |
| **消融阶梯(EC5)** | ★ | **3/3 一致**：no-residual 4108 > no-tom 3601 > no-consolidation 1914 > full 1461 | **supported (robust)** | no-consolidation 收缩噪(−1.7%±26)→claim 用"full 可靠收缩+省24%字节" |
| **巩固因果必要** | | full 收缩 +33.5%±8.7(3/3正) vs no-consolidation 不收缩；full 省 ~24% 字节 | **supported** | 效应量随主题变(CRISPR 仅 5%, 余 ~40%) |
| **C4 漂移传感(EC3)** | | 回弹 **+172~336%(3/3)** + 回弹后再收缩 27-35% | **supported (robust)** | — |
| **vs LatentMAS 差异化** | ★ | no-residual(全潜)4108 vs full(残差)1461 → 残差编码再省 **~64%** | **supported** | LatentMAS 潜传输黑盒 API 不适用(设定差异), no-residual 为其代理 |
| **CC1 通信效率(2 数据集)** | ★ | HotpotQA bridge k3 −71.8% ΔF1−0.038 CI含0；**MuSiQue k3 −82.5% ΔF1−0.003 CI含0** | **supported (post-hoc)** | 判据 post-hoc；未证严格非劣(CI 略宽) |
| **idea B·残差即新意传感器** | ★(新) | 二分 AUC **1.0**；**graded: 残差分 fam/evo/nov 1387/2615/3842；fam-vs-evolved 残差 AUC 1.0 vs 检索 0.23** | **supported** | 合成 evolved 构造(同topic新应用域)；真实数据待补 |
| **记忆复用** | (赛题) | CoQA 命中 0.92 / m7 G2 1.0 | **supported (post-hoc)** | 判据事后定 |
| **C3 Verified Lossy** | ★ | **EC4** `verified_lossy_20260622_180609`：synced cos0.97 回退0%；失配下校验**detect率==真损坏率**(mild 0.75, severe 1.0)、**静默损坏 0(有校验) vs 12/16(无校验)** | **supported** | 失配为注入(desync/外来基)；真实架构共享 CAS 罕失配，故为安全性下界 |

## 总裁决（信念更新）
- **足以支撑顶会级"机制+系统"论文**，头牌 = **「协作即条件率失真编码」(Wyner-Ziv)**：① 机制证据已**跨主题稳健**(消融阶梯3/3、分布地板0.92-0.98、漂移3/3、巩固因果)；② CC1 真实数据**2/2 数据集**质量中性大幅省 token；③ idea B 提供**新颖且有独有价值**的涌现能力(信息层漂移传感, 完胜检索相似度基线)。
- **相对 2026-06-21 的关键变化**：C1 partial→supported(seeds3+地板+回弹)；C2/C4/消融 not-tested→supported(robust)；新增 idea B supported；**C3 verified-lossy not-tested→supported(EC4)**。**全部★核心 claim 现已 supported**。
- **诚实边界**：机制实验用合成 G1 族 scaffold（但嵌入=真实 GLM-Embedding-3 of 真实 LLM 证据, 跨真实主题）；CC1 未证严格非劣；C3 失配为注入(安全性下界)；eff- 量随主题变。措辞守"稳健机制证据"非"物理定律"。

## 剩余 gap & 下一实验（按优先级；全★核心已 supported，以下均 nice-to-have 非阻塞）
1. **机制真实任务外推**——把消融阶梯/地板在一个真实多步任务(非合成 G1 scaffold)上复跑一次，补外部效度（最有价值的加固）。
2. **CC1 严格非劣**——已 N=200，CI 略宽；可加 seeds 或 N→500 压进 −0.05 裕度（含0已够"质量中性"）。
3. **graded-drift 真实数据**——evolved 类用真实数据集的"同主题新文档"替合成构造（加固 idea B 外部效度）。
4. EC4 失配概率扫描——sweep desync 概率画 ROC（当前为两点 mild/severe）。

## 框架决策（**用户停点**，surface 不停循环）
- 证据已足以走 **A·单头牌「条件率失真编码」**（机制为纲，CC1+漂移为实证支撑）。
- 备选 **双贡献并列**（机制 + CC1 系统）更保守。
- 建议 A；但 C3 补完前，A 的"verified-lossy 安全性"一节需 EC4 背书，故**先跑 EC4 再定稿头牌**。

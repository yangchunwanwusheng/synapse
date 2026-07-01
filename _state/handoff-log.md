# Handoff Log — SYNAPSE

## [S0 入场分诊 + S1 backfill] — backfilled — 2026-06-18
- 输入消费：用户原始材料 SYNAPSE.tex（收敛定稿 idea，原 v5）/ SYNAPSE.pdf / SYNAPSE_architecture.drawio / 竞赛赛题.md
- 产出：00-project.yaml、_state/handoff-log.md、_state/pipeline-status.md、01-idea/idea-card.md（provenance: backfilled）
- 分诊结论：entry_route = **E3**（已有 idea + 设计草案）→ 切入 S2（校验/补缺模式）
- Backfill 承重项：
  - **B1 撞车窗检索**：SYNAPSE.tex §7 已于 2026-06-17 用 semantic-scholar + web-search-prime 执行（近 6 月 + 近 90 天），最近邻 arXiv:2604.09521 已逐一区分。**残留待核验**（附录 A）：① ToM 用于"最小消息寻址"为最弱一条；② arXiv:2511.04235 域未独立核到。→ 进决策包，投稿前必补一次定向检索。
  - **B2 venue/deadline**：竞赛官方 deadline 未登记（assumed）；交付硬约束 = openEuler 24.03-LTS-SP3 可编译运行测试。→ 进决策包。
- 自我攻击：S0 红队 1 轮（分诊行号取第一个命中 E3；assumed 项已全部入决策包；B1 如实标"沿用昨日检索+残留待核验"，未虚构）
- 给下游的提示：S2 须把 SYNAPSE.tex 的 E1–E8 转写为 S2 契约结构；设计模式=**并重型**（发现 C1 优先 + 解法 C2/C3）；预算按 API+本地向量重估（非 GPU）。
- 残余风险 / 待办：① B1 两条待核验 novelty；② 竞赛 deadline assumed；③ 任务族语料 assumed。
- 门禁裁决：可进入 S2（wip）。入场决策包随本轮收尾一并呈交。

## [S2 实验设计] — done — 2026-06-18→20
- 输入消费：01-idea/idea-card.md + 00-project.yaml(constraints)
- 产出：02-design/experiment-protocol.md、02-design/design-notes.md
- 状态：done（协议用户 2026-06-20 认可 + 授权真实实验/Paratera 密钥；已被 S3 消费）
- 门禁裁决：用户已认可协议+预算 → 进 S3

## [S3 实现执行] — done — 2026-06-20→21
- 输入消费：02-design/experiment-protocol.md + smolagents 基座（5 模块）
- 产出：真实 API(Paratera Qwen3-30B-A3B) 多轮 run，artifacts 在 `runs/`：
  - signal_20260620_152728（C1 收缩律：KC-1 PASS，关联收缩+23% vs 负例反升−28%，因果比 0.53，命中 0.9 vs 0.167）
  - m7_20260620_214354（跨组复用：G2 命中 1.0、均字节 49.6≤G1 52.0）
  - coqa_20260621_111342（记忆复用·真实数据：命中 0.92、token 省 8.2%、F1 0.733→0.748）
  - hotpot_stats_20260621_182630 + ksweep ×3（通信效率·真实数据·配对 CI；bridge k=3 省 73.5% 质量非劣）
- 达标判据：signal 轮 KC-1 通过；真实 token 口径 + F1 + 配对 CI 已立；Windows GBK 崩溃已修(utf-8 stdout)。
- 自我攻击：bridge 行为单测 + 8 QA 测试 + smoke 全绿；ruff clean。
- 残余风险/待办（evidence 轮缺口，进 S4 caveats）：C1 单 seed/合成/无 oracle 地板/无漂移回弹(E6)；C2(E3)/C3(E4 注入)/C4/消融 均未跑。
- 门禁裁决：S3 done → 进 S4。

## [S4 结果分析] — done — 2026-06-21
- 输入消费：runs/（signal/m7/coqa/hotpot_stats/ksweep×3）+ 02-design/experiment-protocol.md（预注册判据）
- 产出：04-analysis/analysis-report.md + analysis-notes.md + aggregated/{raw_long,summary}.csv（脚本 aggregate_s4.py，90 行同源）
- 达标判据：每条 claim 三档裁决（C1 partial / C2,C3★,C4,消融 not-tested / 通信效率·记忆复用 supported-posthoc）；数字溯源抽查 5 项通过；M1–M11 回扫(L9)。
- 自我攻击：R2 全量 6 项（判据漂移→post-hoc 全标；cherry-pick→全量入表含 twohop 失败；显著vs噪声→CI 含0 措辞；溯源抽查通过）。
- 给下游提示：S5 图表清单 4 图就绪（数据源 aggregated）；S6 措辞上限=C1 禁称"发现/定律"、通信效率按 post-hoc。
- 残余风险：C1 evidence 轮缺口；post-hoc 判据；CI 宽未证严格非劣；C3 核心未受检。
- 🔒 门禁裁决：**需用户审批（S4 停点#2）** — ★核心 claim 未获完全支撑；总裁决"以现 idea-card framing(C1 头牌) 证据不足，但足以支撑改 framing 的通信效率/记忆复用系统实证论文"。请用户在【路线甲=守 C1 补 evidence 轮】与【路线乙=改 framing 走通信效率实证】间定向。

## [S3 续跑 · 路线丙 EH1] — wip(暂停) — 2026-06-21
- 用户裁决：选 **路线丙=双贡献**（CC1 通信效率+CC2 记忆复用 头牌 + C1 收缩律 第二贡献）。协议已 pre-register（experiment-protocol §路线丙补充协议）；idea-card framing 已更新。
- 产出：EH1 真实 run `runs/hotpot_ksweep_20260621_231046/`（HotpotQA bridge N=200 k=3）；MuSiQue 数据已 fetch（EH2 就绪）；sweep 增 `--data` 支持第二数据集。
- EH1 结果：token 省 71.8%、ΔF1 −0.038 CI[−0.098,+0.019] 含0=不显著更差 → CC1 数值门达标(1/2 数据集)，非严格非劣。已写入 analysis-report 主表 A。
- 门禁裁决：**用户指示 EH1 后暂停，明天继续**。剩余补跑 EH2→EC1→EH3→EC5→EC2/3/4（见 NOW.md 暂停点）。
- 残余待办：明天 aggregate_s4.py 加 N 标记重跑（纳入 EH1，避免重复行）。

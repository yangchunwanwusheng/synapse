# NOW — SYNAPSE 长任务状态（跨会话恢复用）

更新：2026-06-22

## 当前目标（用户 2026-06-22 定向：自主迭代冲国一+顶会，聚焦实验效果+idea创新，双达标方停）
以 SYNAPSE（协作即压缩）为核心基座，赛题为基础 + 顶会论文路线。**已授权自主循环**（破坏性操作仍需确认；重大裁决会 surface 但不停循环）。

## 🔀 framing 锐化（2026-06-22 撞车窗检索后，路线丙·强调翻转，证据先行）
- **撞车窗发现**：「非文本/潜状态省 token」已被 **LatentMAS (arXiv 2511.20639, ICML'26 Spotlight, 省70.8-83.7% token)** 占据；省 token 的 MAS 拥挤(AgentPrune ICLR'25 196cites/AgentDropout)。→ **CC1 省 token 不能作头牌**。
- **新头牌（机制/发现）= 收缩律 C1 + WZ 地板 C2 + 漂移传感 C4**；省 token 降为"原理有用"的验证（黑盒 API 设定下，LatentMAS 潜传输不适用）。详 `_state/rootcause-idea-20260622.md` + 记忆 synapse-novelty-positioning。
- ✅ **2026-06-22 证据已转强（前提满足）**：EC1 seeds3/3 + EC2 floor 0.889 + EC3 drift +191.6% + EC5 4级消融阶梯 + 巩固因果必要。
  头牌锐化为「**协作即条件率失真编码**」(Wyner-Ziv)：残差=H(Y|B̂)，随共享结构趋条件率失真地板；统一 CC1(2数据集)+vsLatentMAS(残差再省~2×)+漂移传感。
- ⚠ **最终 framing（单头牌 A vs 双贡献并列）= 用户停点**（S4 §6）；证据已足以支撑 A，但措辞仍守诚实底线（floor<1 需正确解读、CC1 未证严格非劣）。

## 本会话已完成（2026-06-22）
- **修 codec dim>256**（`stateplane/residual.py` 索引宽自适应 1B/2B）→ 收缩律现可用**真实 GLM-Embedding-3 2048维残差**测（非 hash）。加回归测试 `test_residual_highdim_2byte_index_roundtrip`，17 测全绿、ruff clean。
- **EC5 消融开关**（`config.py` abl_no_tom/no_consolidation/no_residual/no_checksum + `synapse_mode.py` 应用，默认全 False 零影响）。
- **机制实验驱动 `scripts/run_mechanism.py`**（floor=EC2 oracle地板 / drift=EC3漂移回弹 / ablation=EC5；--offline 自检通过：drift 回弹+133%、no-tom 0%收缩、no-residual 140B vs full 15B）。
- **EC1 驱动 `scripts/run_signal_seeds.py`**（signal×重复，真实残差）。
- **修 `aggregate_s4.py`**：glob `*_ksweep_*`（纳入 musique）+ tag 含 dataset+N（解 N=50/200 bridge 行重复 + musique 区分）。

## ✅ EC1 完成（收缩律 seeds≥3, 真实残差, `runs/signal_seeds_20260622_111524/`）
linked 后半字节恒约负例一半(1792 vs 3794)、命中 0.875 vs 0.167、**3/3 一致**；within-run drop 噪(16/19/1.7%, MoE)→关联快速逼近地板。**因果分离稳健**=低协作成本源于共享结构。supersede 旧 hash signal。

## ✅ mechanism 完成（EC2/EC3/EC5, 真实残差, `runs/mech_*_20260622_113530/`）
- **EC5**：no-tom 3588 vs full 1993（ToM 减半）✅；**no-residual(≈LatentMAS全潜) 4108 vs full 1993（残差编码再省51%）✅**对LatentMAS差异化；no-consolidation≈full（巩固器原 no-op）⚠。
- **EC3 漂移**：回弹 +85%（2076→3843）✅ 漂移传感成立。
- **EC2 地板**：cold 3528→warm 1920，留一地板 1080；地板存在且 cold≫warm≫floor，但 online 为地板 1.78×（未在10任务收敛）。
- **诚实裁决**：机制头牌可辩护（ToM减半/残差再省半/漂移回弹/地板存在）；但**"平滑单调收缩"过度承诺→改述"记忆出现即陡降+地板上噪声平台"，本质=可预测性驱动压缩**。详 experiment-log + analysis 待增量。

## ✅ 本会话（2026-06-22 自主迭代）核心进展
1. **根因修复 · 执行器 CodeAct 解析失败**（`runtime/model.py` `normalize_codeact`）：Qwen3 偶发
   `final_answer(...)</code>`（缺开标签）；smolagents 1.26 对未以 `</code>` 结尾的输出**回补**停止标签
   → 变 `code</code>` 无配对 → `parse_code_blobs` 烧光 max_steps。**修法=补成 `<code>..</code>` 配对**（非裸剥）。
   端到端复现测 + 单测共 11 绿、ruff clean、真实 API 探针返回正确值。省每次 CodeAgent 运行的重试预算。
2. **EH2 MuSiQue 完成（`runs/musique_ksweep_20260622_115337/`）→ CC1=2/2 数据集**：k=3 **token −82.5%**
   配对 ΔF1 **−0.003** CI[−0.059,+0.055] 含0（更难2-4跳却更干净）。HotpotQA bridge k=3 −71.8% ΔF1 −0.038 含0。
3. **mechanism v2 完成（`runs/mech_*_20260622_165459/`，质心巩固器+净化 prompt）——机制头牌大幅走强**：
   - floor：online 2011→1027（**−48.9%**），second/floor **0.889**（后半低于单条最优地板=触到更低的分布地板）。
   - **ablation 阶梯（4 级干净）**：no-residual(≈LatentMAS全潜)4108 → no-tom 3589 → no-consolidation 2039 → full **1522**。
   - **巩固因果必要**：full 后半收缩 **+22.9%** vs no-consolidation **−17.3%**(反升)；v1 巩固 no-op 时此消融≈full，现显效。
   - drift 回弹 **+191.6%**（强于 v1 +85%）+ 回弹后再收缩 35.9%。
4. **idea 增补**（详 `_state/rootcause-idea-20260622.md`）：A 头牌重构「协作即条件率失真编码」(Wyner-Ziv，统一CC1+vsLatentMAS+漂移)；
   B 新颖能力「通信成本即免费漂移/新意传感器」(新驱动 `scripts/run_drift_detect.py`，AUC/PR)；C 学习式预测基(质心已够→暂缓)。

## ✅ drift-detect 完成（idea B 初证，`runs/drift_detect_20260622_170916/`）
- familiar **1240.6B** vs drift **3843.0B**（3.1×零重叠）；**AUC(残差)=1.0** P1.0/R1.0@3666B → 通信成本=完美免标注新意传感器。
- ⚠ 诚实：二分设定里**检索相似度基线也 AUC=1.0**（打平）→ 残差独有价值需**分级**(同topic新aspect)证。

## 🧪 本会话新增实验基础设施（offline 自检+ruff 全绿，待真实 API 跑）
- `run_mechanism.py --repeats N`：跨 TOPICS(5主题)重复，聚合 mean±std + 阶梯一致性（generalization seeds≥3 robustness）。
- `exp_floor` 加**质心地板**（充分统计 oracle=分布地板）：解读 second/floor<1（online 自上方逼近真·分布地板，非不公平对比）。
- `run_drift_detect.py --graded`：familiar/evolved(同topic新应用域)/novel 三级；关键 = familiar-vs-evolved AUC 残差 vs 检索相似度。

## ✅ mechanism v3 完成（3 主题 robustness, `runs/mech_agg_20260622_171550/`, **0 解析错误**）
跨 Transformer / CRISPR / 广义相对论三主题，机制阶梯与地板**泛化**（seeds≥3 门槛达成）：
- **消融阶梯 3/3 一致**：no-residual 4108±0 > no-tom 3601±3 > no-consolidation **1914±301** > full **1461±115**。
- **巩固因果**：full 省 ~24%(1461 vs 1914) 且**可靠收缩**(drop +33.5%±8.7, 3/3 正)；no-consolidation 不收缩(−1.7%±26, 噪)。
- **质心地板（airtight）**：online 后半触**分布地板** ratio **0.92–0.98**（3 主题，紧）→ 触到真·条件率失真地板，远低于单条地板。
- **drift 回弹 3/3 强**：231.7% / 171.7% / 336.0%（均 ~246%）+ 回弹后再收缩 27-35%。
- 诚实：no-consolidation 收缩噪（−1.7%±26），稳健 claim 用"full 可靠收缩+省24%字节"，非"去巩固=零收缩"。

## ✅ graded-drift 完成（idea B 独有价值证实，`runs/drift_graded_20260622_175400/`）
残差分 familiar/evolved/novel = **1387/2615/3842**（干净三级梯度）；sim = 0.549/0.552/0.177。
**fam-vs-evolved（同主题）：残差 AUC 1.0 vs 检索相似度 0.23** → 残差检测**信息层**新意，检索相似度(主题层)盲。

## ✅ S4 增量裁决完成（`04-analysis/analysis-report.md` 末"增量裁决 v2"）
总裁决：**足以支撑顶会级"机制+系统"论文**，头牌=条件率失真编码。唯一遗留★核心 = **C3 verified-lossy**（EC4 进行中）。

## ✅ EC4 verified-lossy 完成（C3 supported，`runs/verified_lossy_20260622_180609/`）
synced cos 0.97 回退 0%（快路径安全）；失配下**校验 detect率==真损坏率**(mild 0.75/severe 1.0)、**静默损坏 0(有校验) vs 12/16(无)**。
→ 语义校验**精确**标记损坏(无假阴/假阳)、保证零静默损坏。**全部★核心 claim 现已 supported**。

## 🎯 证据全景完成 → 待用户裁框架决策（surface 了，循环继续）
- 机制（条件率失真,3主题稳健）+ CC1（2/2数据集）+ idea B（漂移传感 AUC1.0 独有价值）+ C3（verified-lossy 零静默损坏）四支柱齐。
- **框架决策**：A 单头牌「协作即条件率失真编码」（建议，证据足）vs 双贡献并列。已 surface 待裁。
- nice-to-have（非阻塞）：机制真实任务外推；CC1 严格非劣 N→500；graded 真实数据。

## S4 产物（2026-06-21，top-tier-paper-workflow S4）
- `04-analysis/analysis-report.md`(claim 三档裁决+误差分析+caveats+总裁决+S5 图表清单+M1-M11 回扫) + `analysis-notes.md` + `aggregated/{raw_long,summary}.csv`(脚本 `scripts/aggregate_s4.py` 90 行同源)。
- 状态机已 reconcile：S1 backfilled/S2 done/S3 done/S4 done(停点#2)。
- 赛题 M1-M11 合规✅(仅演示视频待录)，不受 framing 决策影响。

## 根因→调整→扩样本（2026-06-21，用户"分析根因→调整/扩大实验"+"现在就去做"）
- **根因（量化确定）**：CoQA token 只省 8.2% 因**故事地板占 81% token**（无状态 LLM 每轮必看全文，省幅天花板 ~19%）。机制收益 ∝ 可压缩上下文比例。
- **调整=换 regime → HotpotQA distractor**（每题 10 段=2 金标+8 干扰，可压≈80%）。
- ⚠ **N=20 单次乐观被扩样本推翻**（曾报 k=3 省75.6%/F1升；小样本掩盖召回不足）。
- **N=50×R=3+配对 CI（`runs/hotpot_stats_20260621_182630/`）**：k=3 token 省 **73.8%±0.01**(硬)，但 **配对 ΔF1 −0.112 CI[−0.173,−0.054] 全负=F1 显著下降**，召回 0.78 → **75% 不免费**。
- **N=50 k-前沿（`runs/hotpot_ksweep_20260621_183504/`）**：单调 Pareto，单跳诚实点 k=6 省 ~47%。瓶颈=金标召回(多跳需两段)。
- **改进检索成功（用户选"改进检索"）→ bridge 词法实体桥接**（`config.qa_retrieval=bridge`，`runs/hotpot_ksweep_20260621_190107/`，图 `docs/figs/hotpot_retrieval_compare.png`）：第二跳金标段标题被第一跳正文提及→取之。**k=3 召回 0.78→0.86、ΔF1 −0.12→−0.054 CI[−0.155,+0.051] 含0=不显著差、省幅维持 73.5%**。twohop(嵌入扩展)无效(对照留档)。
- **操作点跃迁：单跳 k=6 省47% → bridge k=3 省 ~73.5%，质量无统计显著损失。**
- **统计边界**：CI 偏宽(F1 0/1 方差+MoE 非确定 text F1 0.66–0.71)，**未证严格非劣**(需 N≈200–500)。
- **两臂分工**：HotpotQA=通信效率(25, **bridge k=3 省73.5%不掉质量**)+状态传递(20)；CoQA=记忆复用(20)。
- **下一步候选**：① 扩 N≈200 压 bridge k=3 的 CI 进严格非劣带；② NER/别名增强 bridge 提残留召回；③ 转其他赛题项(演示视频/五维自评)。

## 后端（2026-06-20 切换，全局生效）
- 大模型 API = **Paratera 算力平台**（`https://llmapi.paratera.com/v1`，OpenAI 兼容；密钥 `PARATERA_API_KEY` 仅在 `.env`）。
- 模型 `Qwen3-30B-A3B-Instruct-2507`；**真实句向量 `GLM-Embedding-3`(2048维)已接**(`embedder=api`)。覆盖原 SiliconFlow（已入全局 preferences）。

## 真实数据集结果（CoQA，run `runs/coqa_20260621_111342/`，`synapse coqa --convs 3 --embedder api`）
- **诚实 token 口径**(真实 LLM 输入+输出)：synapse 省 **8.2%** token、**F1 0.733→0.748(不降略升)**、命中 0.921；3 段全 F1 保持。
- **节省随对话轮次增长**：turn15 +10% 且上升（正解"重复上下文"痛点）。权衡：激进句检索 k=10 省 35% 但 F1 跌 0.60。报告 `docs/实验报告-coqa真实数据集.md`。
- ⚠ 前期 signal/m7（合成任务 + token 口径错误）已加修正声明，只作收缩律机制验证，不作赛题通信效率正式数据。

## signal 轮（合成任务，仅机制验证，run `runs/signal_20260620_152728/`）
- 收缩律 C1 机制成立：关联族收缩 +23%、负例反升 −28%、收敛比 0.53、hit 0.9 vs 0.167（驳"就是缓存"）。**注**：token 省 24% 为旧口径，不作正式通信效率数据（见 CoQA）。

## 已完成
- 清理：删 v1–v4 迭代；v5 重命名为正式 idea **SYNAPSE**（SYNAPSE.tex/.pdf/_architecture.drawio，已去 v5 措辞、重编译 11 页 PDF）。
- 赛题留档：`竞赛赛题.md`（M1–M11 + 评分 + 验收自检清单，权威基准）。
- 管线状态：`00-project.yaml`(E3→S2) / `_state/handoff-log.md` / `_state/pipeline-status.md` / `01-idea/idea-card.md`(backfill)。
- 规格：`docs/系统设计文档.md`(含 M1–M11 覆盖回扫表) / `02-design/experiment-protocol.md`(S2) / `design-notes.md`。
- 骨架→**已 rebase 到 smolagents 1.26.0 基座**（runtime=`model.py`+`team.py`，4 个 CodeAgent）；KEEP protocol/stateplane/memory/eval 四创新面；modes 驱动 smolagents。删旧 runtime/llm·roles·sandbox·agent。
- 验证(rebase 后)：离线 smoke PASS（wire 省 **26.25%**、命中 **0.833**、负例 **0.167**、**0 回退**、收缩 **[66,12,12,12,12,12]**）；8 单测全绿；ruff(src,tests) 通过；`uv.lock` 含 smolagents。
- 后端：smolagents `OpenAIServerModel`→SiliconFlow(无GPU)；离线路径 `MockChatModel`+`HashEmbedder`(零网络)。

## 状态机
- S1 backfilled / **S2 approved**（用户 2026-06-20 授权真实实验 + 提供 Paratera 密钥）/ **S3 signal PASS**（真实 API KC-1 检查点通过；evidence 轮待推进）。

## 优先级：赛题为基础，论文为辅（用户 2026-06-20 指示）

### 赛题 M 红线状态（M1–M11 全部满足，仅演示视频待录）
- ✅ M1–M6、M9、M11（四环使用闭合、五模块、≥10 轮、CodeAct）
- ✅ **M7**：真实 API 跑 G1→G2（`runs/m7_20260620_214354/`），G2 命中 1.0、均字节 49.6≤G1 52.0 → 跨组复用成立。
- ✅ **M8**：全套统计成表入报告 §M8（消息/token/非文本字节/耗时/命中/提升）。
- ✅ **M10 部署**：Dockerfile(openEuler 24.03-lts 非 root)+ compose + .dockerignore + `docs/部署文档.md`；**实测 build+run smoke PASS（容器内 597MB）**；实验报告 `docs/实验报告-signal轮.md`。
- ⚠ **M10 演示视频**：唯一待办（脚本：docker run PASS → signal 收缩曲线 → m7 跨组复用 → 出图）。

### 待办（赛题优先，按序）
1. **M10 演示视频**：录制（可先写分镜脚本，录制需用户操作屏幕）。
2. **赛题验收自检逐条勾选**（`竞赛赛题.md` §验收清单）+ 五维自评定稿。
3. （论文为辅 / evidence 轮）真实 `GLM-Embedding-3`(解 dim>256) → seeds≥3 → 漂移臂 E6(C4) → 巩固器 L1 → 全消融+E2+E4。
4. 投稿前补 B1 两条待核验 novelty。

## 关键路径 & 命令
- 离线自检：`uv run synapse smoke`；测试：`uv run python tests/test_smoke.py`。
- **真实 signal**：填 `.env`(PARATERA_API_KEY) → `uv sync --extra api` → `uv run synapse probe`（形态探针）→ `uv run synapse signal --rounds 10 [--topic "..."]`（关联+负例 A/B，存 `runs/signal_*/`）。
- lint：`uvx ruff check src tests`。
- 真实路径已落地：`runtime/model.py`(CountingOpenAIServerModel temp=0)、`prompts.py`(无工具/直接 final_answer/禁 assertion)、`stateplane/residual.py`(语义 WZ 率失真编码 verify_threshold=0.97)。

## 约束
- 无独立大显存 GPU；机密仅 .env；openEuler 24.03-LTS-SP3 可编译运行测试为交付红线。

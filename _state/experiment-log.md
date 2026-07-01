# Experiment Log — SYNAPSE

> 每个真实运行一段；记 run dir、配置 delta、指标、结论。失败/诊断也记（失败原因即知识）。
> 后端 = Paratera 算力平台（`Qwen3-30B-A3B-Instruct-2507`, temp=0, OpenAI 兼容）。

## smoke 轮（离线 mock，零成本）
- 一直 PASS：wire 省 ~24%、contraction `[full, ~0, 0, …]`、hit 0.83、负例 0.17、0 回退。
- **L8 实锤**：mock 用确定性同主题证据 → 每任务 Y 完全相同 → 收缩"过强"`[66,12,12,…]` 是**identical-evidence 假象**，不是真实收缩能力。smoke 过的是 plumbing 闸，不是有效性闸。

## signal 轮（真实 API，G1 关联连续任务）— 迭代史

### Iter-1（plumbing，2026-06-20）
- 接通 Paratera；修真实路径 3 缺陷：token 统计读 `TokenUsage.output_tokens`（原把对象当 dict→AttributeError）、`temperature=0`、`.env` 自动加载。
- `probe`（输出形态探针 L5）：`Qwen3-30B-A3B-Instruct-2507` 输出干净 `PROBE_OK`、无 thinking 块、CodeAct 可解析。**模型选型确认**。

### Iter-2（content）
- 诊断：retriever 幻觉调用 `web_search` → InterpreterError → 退化证据"insufficient information"。占位主题 `alpha` 对真实 LLM 无意义。
- 修：`prompts.py`（无工具/自有知识/直接 final_answer）+ 真实主题 → retriever 产出真实 131 词 Transformer 证据。summarizer 使用环闭合（synapse 经共享 CAS 句柄取证据，text 经透传文本）。

### Iter-3（the science fix：收缩律真正成立）
- **诊断（最小诊断：实现 vs 证伪）**：`cos(Y,B̂)` 随记忆累积**确实在涨**（0.815→0.888），但 `sparsity_eps=0`+精确校验把改善锁死 → nnz 恒 ~47/64 → 收缩曲线平 `[108,96,108,104,106]`。判定=**实现失败**，非假设证伪。
- **修**：残差编码重写为**语义 Wyner–Ziv 率失真编码**——按 |残差分量| 降序贪心只发"最惊讶"分量，到失真目标 `cos(Ŷ,Y)≥verify_threshold(0.97)` 即止；基越准→达标分量越少→**字节随经验收缩**。校验改为接收方重嵌入共享正文比对 cos（catch 预测基失配）。
- **结果**：收缩曲线 `[56,36,48,40,26,22,26,40]`（8 跳）——真实下降 ~2.5×（56→22 floor）。但发现 token 统计 bug（`reset=True` 清零 monitor → 跨任务 delta 负数 → 89.8% token 省是假象）+ executor 幻觉写 `assert word_count==N` → max steps。

### Iter-3.5（honest metrics）
- 修 token 统计：模型层 `CountingOpenAIServerModel` 累计（跨 agent reset 持久）。修 executor prompt（禁 assertion/硬编码）。
- 10 跳 + 负例对照：wire 省 38.3%、**token 省 20.0%（诚实值）**、hit 0.9、0 回退；关联收敛后半 37.2 vs 负例 64.7。但负例用占位主题 `topic1`（退化证据）+ drop% 度量对噪声敏感（关联 14.7% vs 负例 12.6% 显弱）。

### Iter-4（clean causal control）— 见下方最终结果
- 负例族改真实互不相关主题（French Revolution/photosynthesis/…）；因果度量改"收敛速率水平"（关联后半 vs 负例后半 + 命中率），抗逐点噪声。

### Iter-4 最终结果（2026-06-20，run `runs/signal_20260620_152728/`）
- 配置：`Qwen3-30B-A3B-Instruct-2507`, temp=0, embedder=hash, G1 10 跳(Transformer) + 负例 6(真实互不相关主题)。
- **KC-1 检查点 PASS（signal 轮第一强制门）**：
  - wire 省 **41.4%**、token 省 **24.3%**（诚实值）、**0 回退**。
  - 关联族**收缩**：contraction `[76,44,36,42,44,22,56,36,46,26]`，前半 48.4 → 后半 37.2（**drop +23.1%**），hit **0.9**。
  - 负例族**不收缩**（反向）：`[32,66,66,74,60,76]`，前半 54.7 → 后半 **70.0（drop −28%，反升）**，hit **0.167**。
  - **因果区分干净**：收敛速率比 **0.53**（关联收敛到负例字节率的一半），命中 0.9 vs 0.167 → 收缩源于**共享结构**而非缓存（驳"就是缓存"）。
- **结论**：协作速率收缩律(C1) 在真实变化证据 + 真实 API 上**方向成立且有因果对照**；KC-1 不触发。曲线仍噪（真实 LLM 逐跳证据方差）→ evidence 轮需 seeds 平均 + 可选真实 embedding 平滑。
- **残留待升级（evidence 轮）**：① 真实句向量 `GLM-Embedding-3`（需 dim>256 降维，残差码当前 ≤256）；② 漂移臂 E6（注入主题切换看回弹）；③ seeds≥3 mean±std；④ 巩固器 L1（当前 no-op）；⑤ executor 偶发 max-steps（已大幅缓解，残留 prompt 噪声）。

## 赛题红线收尾（2026-06-20，用户指示"赛题为基础，论文为辅"）

### M10 部署（验收红线）✅
- `Dockerfile`（`openeuler/openeuler:24.03-lts` 基础镜像、非 root uid 1001、内置 healthcheck）+ `docker-compose.yml`(env_file required:false) + `.dockerignore`（排除 .env/密钥）+ `docs/部署文档.md`。
- **实测**（Docker 29.1.2）：`docker build` 通过、镜像 597MB；`docker run` 与 `docker compose run` 容器内 **SMOKE PASSED**（非 root）；compose config 校验通过。

### M7 两组关联连续任务（真实 API，run `runs/m7_20260620_214354/`）✅
- `synapse m7 --g1 5 --g2 5`（同会话 G1 深挖→G2 演进，G2 复用 G1 记忆）。
- G1 均 52.0 字节 / hit 0.8（首任务冷）；**G2 均 49.6 字节 / hit 1.0**（每任务命中 G1）→ 跨组复用成立，直接支撑记忆复用(20 分)。

### M8 全套统计（已成表入报告）✅
- 关联族 text vs synapse：消息 30/40、文本 token 2091/**0**、文本字节 15536/**0**、非文本字节 0/428、总线 20446/**11989(−41%)**、命中 0.0/**0.9**、回退 0/0。见 `docs/实验报告-signal轮.md` §M8。

## 真实数据集修正（2026-06-21，用户指出"合成任务+token=0"两硬伤）
- **承认两硬伤**：①前期 signal/m7 用**自建合成任务**非数据集；②"文本通信 token=0"是字段口径错误（只统计消息 `text` 字段，结构化 payload 记成 header_bytes，且从未统计真实 LLM **输入** token）。
- **修指标**：token 计数改"真实 LLM 输入+输出"（`CountingOpenAIServerModel` + `MockChatModel` 双计数器；`improvement.llm_token_saved_pct`）；新增词级 **F1**(`qa/scoring.py`) 保证"省 token 非靠少干活"。
- **换数据集**：CoQA（`stanfordnlp/coqa`，每段对话=一组天然关联连续任务）。实测 HotpotQA 问题相互独立(共享金标实体≈0)→不适合记忆复用，弃用。接真实 `GLM-Embedding-3`(2048维，CoQA 检索不走残差码故无 dim≤256 限制)。
- **诚实结果**（`runs/coqa_20260621_111342/`, `synapse coqa --convs 3 --embedder api`）：
  - **token 省 8.2%（输入 8.5%），F1 0.733→0.748(不降略升)，命中 0.921**；3 段全部 F1 保持。
  - **节省随轮次增长**：turn5 −2% → turn11 +6% → turn15 **+10% 且上升**（对话越长省越多，正解赛题"重复上下文"痛点）。
  - 权衡：激进检索 k=10 省 34.6% 但 F1 降到 0.60（短文 retrieval 漏答案句）→ 故事完整保留是质量安全点。
- **诚实局限**：无状态 LLM 须每轮重传故事→短文短对话省幅小；大幅省 token 待 ① HotpotQA 大语料检索臂(丢干扰段，预期省 50%+不伤质量) ② 同族 KV/隐状态共享(需 GPU，约束外)。报告 `docs/实验报告-coqa真实数据集.md`。

## 根因驱动的通信效率臂（2026-06-21，用户指示"分析根因→调整/扩大实验"）
- **根因（用真实 run 量化，确定）**：CoQA 每轮第一跳累计 token ≈ 故事地板，两模式相同；地板 × 轮数 = 16341/20224 = **81%**。无状态 LLM 每轮必看全文做阅读理解 → 故事不可压 → CoQA token 节省**理论天花板 ~19%**，拿到 8.2% 已吃掉 ~43%。砍进故事(句检索 k=10)→漏答案句→F1 崩 0.60。**这是 regime 结构性上限，非 bug。**
- **机制定律**：SYNAPSE 收益 ∝ "被重传却不需要的上下文比例"。CoQA 该比例≈0；**HotpotQA distractor ≈80%**（每题 10 段，2 金标+8 干扰）。
- **调整=换 regime**：新增 HotpotQA distractor 臂（`hotpotqa/hotpot_qa` 验证集前 20 题全 hard，avg 1016 词/题）。代码：`scripts/fetch_hotpot.py`、`qa/dataset.py`(HotpotItem)、`qa/pipeline.py`(run_text/synapse_hotpot)、`qa/harness.py`(run_hotpot)、`cli.py`(cmd_hotpot)、`config.qa_para_k`。
- **N=20 预备（已被 N=50 推翻，留教训）**：曾报 k=3 省 75.6%、F1 0.664→0.693(升)。小样本恰好掩盖召回不足。**教训：小样本 F1 结论必须配对 CI 复核。**
- **扩样本+多次重复+配对 CI（用户"现在就去做"，2026-06-21）**：新增 `qa/stats.py`(mean_std/bootstrap_ci/paired_winloss)、`run_hotpot_stats`+`synapse hotpot-stats`(N×R 共享 embedder)、`scripts/sweep_hotpot_k.py`(k-前沿)、`plot_hotpot_frontier.py`。修 Windows GBK 崩溃：CLI+脚本 `sys.stdout.reconfigure(utf-8)`、脚本增量落盘。
  - **N=50×R=3 (k=3, `runs/hotpot_stats_20260621_182630/`)**：token 省 **73.8%±0.01**(硬信号)；**配对 ΔF1 −0.112，95% CI [−0.173,−0.054] 全负 → F1 显著下降**；胜/平/负 6/111/33；召回 0.78。**k=3 的 75% 不免费。**
  - **N=50 k-前沿 (`runs/hotpot_ksweep_20260621_183504/`, text F1 0.704)**：单调 Pareto——k=3 省73.8%/ΔF1 −0.12[−0.23,−0.01]显著差；k=4 省65%/[−0.21,+0.01]；k=5 省57%/[−0.18,+0.04]；**k=6 省 46.9%/召回0.91/ΔF1 −0.04[−0.14,+0.06] 含0=不显著差(最佳平衡)**；k=8 省25%/召回0.96/[−0.13,+0.04]。
  - 单跳诚实操作点曾=k=6 省 ~47%。瓶颈=金标召回(多跳需两段)。
- **改进检索（用户选"改进检索"，2026-06-21）**：`config.qa_retrieval` single|twohop|bridge；`pipeline._retrieve_paras`；`--retrieval` + `plot_retrieval_compare.py`。
  - **bridge（词法实体桥接）成功**：第二跳金标段标题(实体)通常被第一跳段正文提及 → 取标题串现于第一跳正文的段。零额外 LLM/嵌入。**k=3 召回 0.78→0.86、ΔF1 −0.12→−0.054 [−0.155,+0.051] 含0=不显著差，省幅维持 73.5%**(`runs/hotpot_ksweep_20260621_190107/`)。各 k 的 ΔF1 持平 ~−0.05 → **k=3 直接最优**。
  - **twohop（嵌入查询扩展）失败（诚实记录）**：拼第一跳整段做嵌入扩展→长正文稀释查询、补不回桥接段（实体桥接是词法/实体链接非语义相似）。k=3 召回 0.75/ΔF1 −0.12(无改进)(`runs/hotpot_ksweep_20260621_185254/`)。
  - **操作点跃迁：单跳 k=6 省 47% → bridge k=3 省 ~73.5%，质量无统计显著损失**。图 `docs/figs/hotpot_retrieval_compare.png`。
  - **统计边界**：CI 偏宽(F1 0/1 方差+MoE 非确定 text F1 0.664–0.708)，**未证严格非劣(CI 进 ±0.03)**，需 N≈200–500。
- **两臂分工**：HotpotQA=通信效率(25, **bridge k=3 省 73.5%不掉质量**)+状态传递(20)；CoQA=记忆复用(20)。互补不矛盾。

## S4 → 路线丙双贡献（2026-06-21，用户定向；S4 停点#2 后）
- S4 交付：`04-analysis/analysis-report.md`+`aggregated/`(脚本 aggregate_s4.py)；裁决"原 C1 头牌 framing 证据不足"→用户选**路线丙**=头牌 CC1 通信效率+CC2 记忆复用(实证) + 第二贡献 C1 收缩律(机制)。
- 协议 §路线丙补充协议 **pre-register** CC1/CC2/C1/C3 判据（写于新实验前→修 post-hoc）。补跑清单 EH1→EC1+EH3→EC5→EH2→EC2/3/4。
- **EH1（pre-registered, HotpotQA bridge N=200 k=3, `runs/hotpot_ksweep_20260621_231046/`）**：token 省 **71.8%**、召回 0.838、**配对 ΔF1 −0.038 CI[−0.098,+0.019] 含0=不显著更差**、胜/平/负 26/142/32、text F1 0.671。N=200 较 N=50 CI 收窄 ~2×、ΔF1 −0.054→−0.038。**满足 CC1 数值门(token≥40/ΔF1≥−0.06/CI下沿≥−0.10)，但 CI 下沿 −0.098 未达严格非劣 −0.05** → 诚实表述"省 72% token 质量统计不可区分(小幅~4F1 潜在代价落噪声内)"，非"严格非劣"。**CC1 = 1/2 数据集达标，待 EH2(MuSiQue)**。
- **暂停（用户指示：EH1 后停, 明天继续）**。EH2 已就绪：MuSiQue 200 题(20 段/2 金标)已 fetch，sweep 支持 `--data data/musique_sample.json --retrieval bridge`。
- ⚠ aggregated CSV 暂未含 EH1（避免与 N=50 bridge 行重复）；明天 consolidation 时给 aggregate_s4.py 加 N 标记后重跑。

## 自主迭代轮（2026-06-22，用户："自主迭代冲国一+顶会，聚焦实验效果+idea创新，双达标方停"）

### framing 锐化（撞车窗检索 B1 → 强调翻转）
- web-search-prime 检索（semantic-scholar 429 兜底）发现「非文本/潜状态省 token」已被 **LatentMAS (arXiv 2511.20639, ICML'26 Spotlight, 训练-free 潜空间KV, 省 70.8–83.7% token, +14.6% acc)** 占据；省-token MAS 拥挤(AgentPrune ICLR'25 196cites、AgentDropout ACL'25)。
- **结论**：CC1「省 token」不能作顶会头牌。**新头牌=收缩律 C1 + WZ 地板 C2 + 漂移传感 C4（机制/发现）**；省 token 降为"原理有用+黑盒 API 可用(LatentMAS 潜传输不适用)"的验证。详 `_state/decision-novelty-pivot-20260622.md`。

### 工程（17 测全绿、ruff clean）
- **修真实 bug：残差 codec dim>256**（`stateplane/residual.py` 索引宽自适应 1B/2B + 回归测试）→ 收缩律现可用**真实 GLM-Embedding-3 2048维残差**测（非 hash），解 evidence 轮残留①。
- EC5 消融开关（config + synapse_mode，默认零影响）；`scripts/run_signal_seeds.py`(EC1)、`scripts/run_mechanism.py`(EC2/3/5, --offline 自检过)。
- `aggregate_s4.py`：glob `*_ksweep_*`(纳 musique)+tag 含 dataset+N(解行重复)+`_latest_real`(滤 mock smoke)+ 纳入 EC1/EC2/EC3/EC5 解析。

### EC1 收缩律 seeds≥3（pre-registered, 真实残差, `runs/signal_seeds_20260622_111524/`）
- 配置：Qwen3-30B-A3B temp=0, **embedder=api(GLM-Embedding-3 2048维)**, rounds=8 × repeats=3, g1(Transformer) + 负例(真实互不相关主题)。
- **per-repeat**：linked drop 16.0%/19.4%/1.7%；neg drop 1.6%/0.3%/0.6%；hit L0.875 / N0.167（三次完全一致）。
- **summary**：linked 后半字节 1792±150 vs **负例后半 3794±33（关联≈负例一半）**；收敛比 0.43–0.52；**n_consistent 3/3**。
- **诚实裁决（C1 良好支撑，slope 噪/level 稳）**：**因果分离 robust**——关联族协作字节恒约为负例一半 + 命中 0.875 vs 0.167（三次一致）→ 低协作成本源于**共享结构**非协议自身/缓存。**within-run drop% 噪**(16/19/1.7, MoE 非确定)——提示关联族**快速逼近地板后趋平**(r2 起点已低)，故 level 证据强于 slope；"收敛到地板"待 EC2 直接验。supersede 旧 hash signal 作 C1 正式证据。

### mechanism batch 结果（EC2/EC3/EC5, real API 2048维残差, rounds=10, `runs/mech_*_20260622_113530/`）

**EC5 消融（最强信号=variant 间 level 差，非 within-run slope）：**
- **no-tom 均字节 3588 vs full 1993** → ToM 预测基**约减半**协作成本 ✅（机制必要）。
- **no-residual(≈LatentMAS 全潜传输) 4108 vs full 1993** → **WZ 残差编码在全潜之上再省 ~51%** ✅（**对 LatentMAS 的定量差异化**）。
- **no-consolidation 1882 ≈ full 1993** → **巩固器无效（原 no-op）** ⚠ → 已实现质心原型巩固器（store.upsert_prototype + consolidate 归一化质心），待 mechanism v2 重测是否闭合地板差。

**EC3 漂移（C4 漂移传感器）✅**：bytes 在漂移点 2076→3843 **回弹 +85.1%**（分布切换→无共享记忆→残差重升）。漂移传感成立。post 再收缩噪（新主题方差大+一个 12 异常点），"检测漂移"强、"漂移后再收缩"弱。

**EC2 oracle 地板**：online cold-start 3528 → warm ~1920；**留一全记忆地板 1080**（约 cold 的 1/3）。**地板存在且远低于 cold**（收缩 cold→warm 真实，task0→1 即 −50%），但 **online 后半为地板 1.78×**（未在 10 任务内收敛到地板）。within-run slope 噪/弱（drop 3.3%）。

**诚实裁决（C1/C2/C4 机制头牌）**：
- 强且可辩护：①ToM 减半 ②残差编码再省一半(vs LatentMAS) ③漂移回弹 +85% ④地板存在且 cold≫warm≫floor。
- 诚实降级：**"平滑单调收缩"过度承诺** → 真实是"**记忆出现即陡降(cold→warm) + 在地板之上噪声平台**"。机制本质=**可预测性驱动的压缩**（接收方越能预测发送方→协作成本越低），动力学是 fast-then-plateau 非平滑单调。
- **新主张表述**：协作成本 ∝ 接收方对发送方的不可预测性；记忆/ToM/残差编码逐级压低之、趋信息地板；分布漂移时回弹（=漂移传感器）。

### 进行中：EH2（MuSiQue bridge N=200 k=3,4，CC1 第二数据集验证，`runs/_eh2_musique.log`）

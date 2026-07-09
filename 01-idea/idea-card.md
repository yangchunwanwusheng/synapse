---
provenance: backfilled        # 由 S0 从用户材料（SYNAPSE.tex）蒸馏，非 S1 原生执行
backfill_date: 2026-06-18
source_material: SYNAPSE.tex / SYNAPSE.pdf / SYNAPSE_architecture.drawio / 竞赛赛题.md
minimal_checks_done: [B1, B2]   # B1=撞车窗检索(沿用 2026-06-17,含残留待核验); B2=venue/交付约束
---

# Idea Card — SYNAPSE（协作即压缩 / Coordination as Compression）

## 一句话贡献（英文，入论文）
We model multi-agent coordination as **Wyner–Ziv source coding with learnable, experience-growing decoder-side side information** (shared memory + a Theory-of-Mind predictor), and show — on a real openEuler system with byte-level instrumentation — a **falsifiable "coordination-rate contraction law"**: per-task cross-agent communication shrinks toward an independently measurable information floor as shared experience accumulates, and **rebounds under distribution drift before task quality degrades**, turning coordination rate into a free, model-agnostic drift sensor. Lossy residual exchange is made **end-to-end correct** by per-message checksums (Verified Lossy Coordination).

## 贡献重心
> ⚠ **路线丙 framing 更新（2026-06-21，S4 停点#2 后用户定向）**：S4 裁决"原'发现优先(C1 头牌)'framing 证据不足"（C1 单 seed/合成/无地板，C2/C3/C4 未跑）。改为**双贡献、实证优先**：
> - **头牌（实证）**=真实数据集**通信效率**（结构化协议+非文本句柄+实体桥接检索，HotpotQA bridge 省 73.5% 质量小损可控，CI 背书）+ **记忆复用**（CoQA 命中 0.92）。直接对齐赛题通信效率(25)+记忆复用(20)。
> - **第二贡献（机制/发现）**=协作速率收缩律 C1（需 evidence 轮：seeds≥3+oracle 地板+漂移）。
> 详见 `02-design/experiment-protocol.md` §路线丙补充协议（CC1/CC2 头牌 + C1/C3 第二贡献，已 pre-register）。下方原文保留（provenance）。

**（原 backfill 措辞，留档）并重型**（发现 + 解法），**发现优先**：
- 发现（头牌，论文成败所系）：协作速率收缩律 + 漂移回弹。
- 解法（竞赛分 + 工程价值）：可运行的低开销通信/非文本状态传递/共享记忆系统 + Verified Lossy。

## 机制因果链（可证伪的中枢）
共享记忆跨任务巩固 → 接收方边信息 B_j 增大 → ToM 对 B_j 估计 B̂_j 更准 → 发送方只发"惊讶残差" z=Y−Ŷ，残差熵下降 → **每任务跨 agent 字节沿曲线收缩** → 逼近物理地板 H(Y|B_∞)。
漂移 D→D'：巩固出的 B_∞ 对 D' 不再充分 → H(Y'|B_∞) 阶跃上升 → **字节回弹**；agent "多说几句补偿" → **回弹先于任务质量下降**。

## 可证伪假设（→ S2 的 direct 证据需求）
- **H1（收缩+地板）**：随累计经验，期望每任务协作速率单调不增，并**停在一个可独立测量的地板**（全知 oracle 接收方测 H(Y_new|B_∞)）。曲线停在该线=验证；停不到=证伪。
- **H2（漂移回弹，应用）**：注入分布切换后协作速率阶跃回弹，且**回弹时刻早于任务质量下降时刻**。
- **H3（失配惩罚）**：人为劣化 ToM → Δ=I(Y;B_j|B̂_j) 上升、字节上升、校验回退率上升（单调）。
- **H4（Verified Lossy 正确性）**：注入 ToM 错误时，校验和保证端到端任务正确性不被有损残差破坏。
- **H5（与缓存正交）**：缓存 on/off × SYNAPSE on/off 四象限，增益可叠加（新任务上 SYNAPSE 仍压字节）。

## 预期 Contributions（C1–C4）
- **C1（现象·头牌，框架无关）**：协作速率收缩律 + 漂移回弹——可测曲线、可独立测的地板、漂移阶跃。
- **C2（透镜·已被学界验证）**：形式化为带增长边信息的语义 Wyner–Ziv，给可达方案 + 失配惩罚 Δ；明确区分 arXiv:2604.09521（静态能力异质）。
- **C3（保证·部署级，框架无关）**：Verified Lossy Coordination——校验和令有损语义信道端到端正确（代价 O(几十字节)）。
- **C4（应用·so-what，框架无关）**：协作速率作为模型无关的提前漂移/新颖性传感器。
- 降级为机制/消融（不当头牌）：言语行为决策 tell/ask/write/hold、ToM 寻址、MDL 压缩层。

## 最接近 3+ 工作 · 差异表
| 工作 | 它做什么 | 与 SYNAPSE 的关键差异 |
|---|---|---|
| **arXiv:2604.09521** 语义率失真（最近邻） | 静态、纯理论、能力异质的率失真刻画 | 我们做**动态（边信息随经验增长）、真系统、字节级实证**的时间收缩+漂移回弹+校验有损+ToM寻址；它把透镜立了起来（去风险），金矿没挖 |
| 潜空间通信 CIPHER/KVComm/LatentMAS | 发全量潜表示替代文本 | 它们发**更大**的向量且会静默损坏；我们发**更小的惊讶残差**+校验保证正确 |
| 缓存 Agentic Plan Caching(2506.14852) | 重复任务复用，省"重算" | 我们面向**全新任务**省"重说"的协作比特；**与缓存正交可叠加** |
| Collaborative Memory(2505.18279, ICML'25) | 记忆当外挂模块 | 我们让**记忆=通信媒介=解码端边信息 B_j**，通信与记忆同一机制 |

## 可行性估算（按本轮选定后端：API+本地向量，无 GPU）
- LLM：SiliconFlow API（Qwen2.5-7B/14B-Instruct）；非文本载体=本地 sentence-embedding 预测残差；向量库 FAISS/Milvus-lite。
- 字节级实测：openEuler 上 eBPF（或 socket 层计数兜底）。ToM 预测器=小 MLP/检索式（CPU，分钟级）。
- 钱预算 ≈ $20–80（API/LLM-judge，可同族自评进一步省）；本机 8GB GPU/16GB RAM 足够（无需大显存）。
- 墙钟：规格+骨架（本轮）→ M1–M5 实现与实验（8–12 周，见 SYNAPSE.tex §6）。

## 撞车风险栏（B1，2026-06-17 检索 + 残留待核验）
- 已核到并区分：2604.09521 / C2C(2510.19995) / 2506.14852 / 2604.03295 / 2505.18279 / CIPHER(2310.06272) / KVComm(2510.03346) / AgentPrune(2410.02506)。
- ⚠️ **待核验（投稿前必补定向检索）**：① "ToM 用于**最小消息寻址**"为最弱一条（ToM-MAS 多在追踪信念，未见用于压消息字节，但未穷尽）→ 检索 audience design / pragmatic compression / RSA×agents；② arXiv:2511.04235（空间预测编码+HRL）域未独立核到，引用措辞前自查。

## 给 S2 的提示
- 设计模式=**并重型**：发现型四件套（存在性/普遍性/机制归因/边界条件）服务 C1；解法型对比+消融服务 C2/C3。E1=头牌（收缩+oracle地板），E2=缓存正交，E6=漂移回弹，优先级最高。
- 关联连续任务族 G1/G2 必须**刻意构造共享结构**（赛题 M7）；配**负例族**（无共享结构→收缩≈0）证因果（诚实风险 R1）。
- 主指标用**模式无关**的端到端时延/能量，避免 token vs 字节"苹果比橘子"；bytes 用 eBPF 实测。
- 预算按 API+本地向量重估，**勿沿用 SYNAPSE.tex 的 GPU·小时估算**（那是本地 vLLM 假设，已被本轮后端选择替换）。

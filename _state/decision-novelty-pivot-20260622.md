# 决策记录 · 新颖性定位与 framing 锐化（2026-06-22）

> 触发：用户定向"冲国一+顶会，聚焦 idea 创新+实验效果"。本轮做承重墙 B1 撞车窗检索（web-search-prime，semantic-scholar 429 兜底），结论改变头牌 framing 的**强调顺序**（仍属路线丙双贡献，非推翻）。

## 撞车窗检索发现（2024-2026，多智能体 LLM 通信效率）

| 工作 | venue/影响 | 与本工作关系 |
|---|---|---|
| **Cut the Crap / AgentPrune** (G.Zhang 2025) | ICLR'25, **196 cites** | 通信剪枝省 token，是"省 token"赛道的标准基线 |
| **AgentDropout** (Z.Wang 2025) | ACL'25, 79 cites | 动态删 agent 省 token；定义"communication redundancy" |
| **LatentMAS / Latent Collaboration** (2511.20639) | **ICML'26 Spotlight** | ⚠最危险并发邻居：潜空间(KV)协作、training-free、**省 70.8–83.7% token**、+14.6% acc、4× 快 |
| SupervisorAgent (2510.26585) | 2025 | 省 ~29.68% token |
| PACT action-state comm (2606.05304) | 2026 | "agent 该说什么"，省 38.7% token |
| Task-Oriented Data Compression for MAS (TechRxiv) | MARL | 删非增益消息降通信率（最接近"压缩"，但 MARL 非 LLM、无地板律） |

## 核心结论：头牌不能是"省 token"

1. **"非文本/潜状态通信省 token"已被 LatentMAS（ICML'26 Spotlight）以更强形态占据**（潜空间 KV、training-free、+acc、省 83%）。我方 CC1"省 72% token"与之高度重叠且更弱 → **不能作头牌**，否则=更弱的并发版本。
2. "省 token 的 MAS"整体是**拥挤赛道**（AgentPrune 196 cites 等）。

## 存活的可辩护新颖性（LatentMAS/AgentPrune 都没做的）

1. **协作速率收缩律（C1）= 头牌**：持续协作中，**每任务协作比特率是可压缩、随共享记忆累积而收缩、并收敛到信息论地板**的动态量。竞品都是**静态**单任务方法，无"随经验收缩+地板"的**动力学+定律**，无负例因果对照。
2. **Wyner–Ziv 残差编码透镜（C2）**：发"相对接收方可预测部分的惊讶残差"，**严格小于发全量潜向量**（LatentMAS 传完整潜工作记忆；我方传 Δ）。→ `no-residual` 消融 = 近似 LatentMAS 式全潜传输，量化证明残差编码在其之上再省。
3. **Verified Lossy 正确性（C3）**：校验和 + 失配回退，保证有损潜传输端到端正确。LatentMAS 无正确性保证。
4. **协作速率=漂移传感器（C4）**：用收缩/回弹检测分布漂移。无竞品有此用途。
5. **黑盒/API 适用**：我方走 embedding+残差编码，**无需 KV/白盒同模型**；LatentMAS 需白盒同构模型。→ 真实差异化场景。

## 修订 framing（路线丙·强调翻转，待证据确认）

- **头牌（机制/发现）= 收缩律 C1 + WZ 地板 C2 + 漂移传感 C4**：把"省 token"重述为**该原理的实用验证**（在黑盒 API 设定下仍 SOTA-competitive，且 LatentMAS 的潜传输在此不适用）。
- **支撑（实证）= 通信效率 CC1（HotpotQA/MuSiQue）+ 记忆复用 CC2（CoQA）**：作为"原理有用"的证据，对标 AgentPrune；定性区分 LatentMAS。
- **正确性 C3** 作为有损传输的安全保证（vs LatentMAS 无保证）。
- ⚠ **证据先行**：头牌最终定为收缩律的前提是 EC1(seeds)+EC2(地板)+EC3(漂移) 证据够强。若弱则诚实回退到"双贡献并列"。framing 跟着证据走，不反向裁剪。

## 实验优先级修订（投资转向"定律"侧）

1. **EC1 收缩律 seeds≥3**（运行中，真实 GLM-Embedding-3 残差，已修 dim>256）。
2. **EC2 oracle 地板**（关键：把"收缩"升级为"收缩到信息地板"=定律）。
3. **EC3 漂移回弹**（C4 漂移传感，独特新颖性）。
4. **EC5 消融**：`no-residual`（对标 LatentMAS 全潜传输）+ no-ToM/no-consolidation/no-checksum。
5. **EC4 注入正确性**（C3，vs LatentMAS 无保证）。
6. **EH2 MuSiQue + EH1 HotpotQA** 作通信效率验证（支撑非头牌）。

## 待补 related-work / baseline（投稿前）
- 必引并区分：LatentMAS(2511.20639)、Cut the Crap/AgentPrune、AgentDropout、PACT(2606.05304)。
- baseline 阶梯加：AgentPrune 式剪枝（省 token SOTA 对照）；`no-residual` 臂近似 LatentMAS 全潜传输。
- semantic-scholar 429 未取到精确 cite/venue 字段 → 投稿前用 semantic-scholar 补 BibTeX 与计量（标"web 源，未充分计量验证"）。

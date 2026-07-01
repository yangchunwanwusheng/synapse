# Design Notes — SYNAPSE S2（过程档案）

> 供回溯，篇幅不限。交付物是 `experiment-protocol.md`；本文件记录调研、被否方案与第一轮攻击。

## 关键设计决策
1. **后端从本地 vLLM 改为 API+本地向量**（2026-06-18 用户定）：SYNAPSE.tex 假设 24–40GB GPU 跑同族 vLLM 取隐状态；本机仅 RTX 4060 8GB（S2 算力档案）。改为 SiliconFlow API + 本地 sentence-embedding 残差路径，隐状态降为可选臂。预算随之从 30–60 GPU·h 重估为 $20–80 API。
2. **非文本载体=句向量"预测残差"而非全量向量**：直接回应 v1 审计 A5（"潜载荷常更大"）与赛题 M4。残差稀疏编码使字节随 ToM 改善而下降（收缩律的微观可测量）。
3. **Verified Lossy 用 hash 检测**：checksum 对量化网格上的 Y；ToM 好→残差小→重构落同格→校验过；ToM 差→残差大→量化/裁剪失真→校验不过→回退 ASK(full)。这是 C3 在代码层的落地。
4. **ToM 自监督信号=重构成功率**（非"信念" ground truth）：绕开 R2。
5. **设计模式=并重型，发现优先**：C1 用发现型四件套，C2/C3 用方法型对比+消融。

## 被否方案
- ~~在线多智能体 RL 学通信协议~~：算力黑洞，SYNAPSE.tex §5.4/v2 审计已判死；本机更不可行。
- ~~纯隐状态零拷贝为主路~~：要求同族+本地 vLLM+大显存，与本机/后端选择冲突；降为可选臂。
- ~~重证 WZ 逆定理~~：不重证；应用并扩展（idea-card C2 诚实声明）。

## 第一轮自我攻击摘要（全量见 experiment-protocol.md 自我攻击记录）
- claim 悬空 / baseline 太弱 / confound("就是缓存") / 发现型套方法型 → 均已在协议中处置（E1-neg 负例族、E2 四象限、oracle 地板、发现四件套）。

## 待核验残留（B1）
- ToM 用于"最小消息寻址"为最弱 novelty 一条 → 投稿前检索 audience design / pragmatic compression / RSA×agents。
- arXiv:2511.04235 域未独立核到。

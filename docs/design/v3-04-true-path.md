# V3-04 前置设计冻结：残差/VLC 真数据通路（Issue #148746）

> 状态：**冻结**（2026-08-28，Issue 要求"8-28 前冻结，评审后开工"）；同日经三路独立审查
> （GPT-5.6 / code-reviewer / strong-model-adviser）+ 真实 API signal 复验后修订为 v2
> 依据：`docs/决赛前源码彻查报告-20260827.md` R-P0-1/2/3/4；`docs/决赛T45总执行方案-v3.md` N1/N2
> 实现门控：`cfg.residual_true_path`（默认 **False** = 旧旁路路径原样保留，回归防护；本 Issue 后续真实评测重跑时翻转）

## 0. 问题重述（现状为何是"旁路"）

| P0 | 现状 | 位置 |
|----|------|------|
| R-P0-1 | 接收方校验前已 `cas.get(text_handle)` 取全文；重构向量仅作布尔校验；summarizer 消费 `recv_text`（全文直读）——删掉重构逻辑答案不变 | `synapse_mode.py` |
| R-P0-2 | `checksum = digest_ints(quantize(Y))`——接收方只有 Ŷ（有损近似），**数学上不可能复算**，故运行路径从未校验；篡改残差字节后余弦校验仍 True | `residual.py` / `checksum.py` |
| R-P0-3 | `abl_no_residual` 只改 `nontext_bytes` 记账数字（dim×2+12），数据路径未变 | `synapse_mode.py` |
| R-P0-4 | tier 只是 meta 标签；residual/embedding 档走同一 `codec.encode`；`CNR.negotiate()` 从未被调用；冷启动也标 residual | `synapse_mode.py` / `handshake.py` |

## 1. 前置设计一：checksum 哈希对象重设计（两级分立）

**旧对象废弃理由**：对全量量化 Y 取哈希，接收方持有的是 Ŷ（残差有损重构），等式 `digest(Ŷ) == digest(Y_q)` 仅在零失真时成立——校验与编码目标（cos ≥ 0.97 即止）矛盾，永远无法在接收侧闭合。

**新设计（v2：域扩展）**：

- **L1 完整性校验（bit-exact，帧层计算）**
  - 哈希对象：`H(payload || base_ref || generation || session_id || domain || content_digest)`，blake2b 8 字节。
  - 接收方仅凭线缆帧字段（payload 字节、base_ref、meta.generation、会话标识、payload_kind、content_digest）即可**复算**，零文本依赖。
  - 拦截面：传输损坏、未同步篡改（改字节不改校验和）、跨任务代/跨会话的陈旧 packet 重放、residual/embedding 跨档字节复用、恢复内容与帧声明错配。
  - **威胁模型边界（审查修订）**：无密钥裸哈希——这是**完整性/损坏检测**，不是认证；能改 payload 的主动攻击者可重算校验和绕过。防主动篡改需 keyed MAC（后续 Issue）。8 字节摘要在长期大对象量下需评估 birthday bound。
- **L2 语义校验（近似）+ 身份校验（bit-exact）**
  - L2 判据：`cos(Ŷ_q, Y_cand_q) ≥ verify_threshold`——接收方以重构向量检索 VectorIndex 所得 top-1 的相似度。
  - 身份判据（v2 新增）：恢复文本的 `digest_bytes` 必须等于帧声明的 `content_digest`——拦截索引近邻错配/decoy 静默消费（L2 只保证语义近似，身份由 digest 保证）。
  - 失败动作：走回退链（残差→embedding→text），非静默。
- `ResidualPacket.checksum` **保持旧口径** `digest_ints(量化Y)`（旧路径对外字段零变化）；真通路 L1 在帧层单独计算。

## 2. 前置设计二：重建结果消费语义（v2：接收方从线缆帧驱动）

**发送方**（retriever）：

1. `Y = embed(evidence)`；`b_hat, base_id, base_sim = ToM.best_base(...)`。
2. **向量可寻址索引**（`stateplane/vector_index.py`）：`vec_index.put(text_handle, quantize(Y))`。**帧本身不携带 text_handle**（v2：初始帧 handles = (payload_handle, base_ref)）——接收方无直接取全文的句柄；身份绑定经 content_digest（8B 摘要，无法反查内容）。
3. **率失真选档**（v2：signal 真实 API 回归根因修复）：有基时试编码残差，`残差字节 ≤ 全量向量字节` 走 residual 档，否则 embedding 档——保证 residual 真通路单帧字节恒不劣于全量向量（修复弱基无条件发全量导致 wire 节省 -119.52% 的分档缺陷）。
4. 预测基只传 **mem_id**（v2：审查 P0-4 方案一）——接收方从自身 MemoryStore 解析该单元 embedding 并量化为基。**记忆是解码端边信息**：不传基向量（无 dim×2B 线缆成本）、不直接复用发送方 b_hat 对象。基缺失/维度不符 → 受控回退。
5. 帧字段：`handles=(payload_handle, base_ref)`、`checksum=L1`、`meta={nontext_bytes, nnz, tier, generation, content_digest, dim}`。

**接收方**（`_receive_frame(msg)`：v2 起**仅凭线缆帧字段驱动**，经 to_wire() 反序列化的 Message 同样可恢复——测试锁定）：

1. text 帧：读帧内正文，content_digest 一致 → 消费。
2. residual/embedding 帧：L1 复算 → residual 按 base_ref（mem_id）从自身记忆解析基（零基 base_ref="" 本地构造）→ `decode_bytes` 重构（畸形字节 ValueError 受控回退）→ L2 检索 + 身份校验 → 恢复文本。
3. 恢复文本即 summarizer 的唯一 evidence 输入。
4. 回退链逐跳（v2：**每跳都经构造帧→_receive_frame 消费**，不复用发送方局部变量）：残差失败→补发 embedding 帧（同样过 L1/L2/身份）→ 仍失败→text 帧（全文唯一通道，接收方从帧 text 字段读取）。
5. 畸形帧（非对齐长度/越界索引/奇数向量字节）→ ValueError → 回退，不崩溃。

## 3. 三档真实分叉 + CNR 驱动 + 冷启动诚实标档（v2：text 真帧）

**发送方选档**（值域 `{residual, residual_zero, embedding, text}`）：

| 条件 | 意向档 | 线缆载荷 |
|------|--------|----------|
| `abl_no_residual` 消融 | `embedding` | 全量量化向量 packet（真实字节，R-P0-3） |
| 无基（冷启动） | `residual_zero`（诚实档） | 零基残差 packet |
| 有基且率失真残差 ≤ 全量 | `residual` | 稀疏残差 packet（mem_id 基引用） |
| 有基且残差 > 全量 | `embedding` | 全量量化向量 packet |
| CNR 协商限幅 | 按秩降档 | text 档=**真文本帧**（v2：无向量载荷，口径恒等 tier_text=1 ∧ nontext=0） |

CNR 门控：`negotiate()` 每任务真实调用，档位按 `_TIER_RANK`（与 ENCODING_RANK 对齐，含 hidden:3）限幅。

**指标口径（v2：分列防漂移）**：
- `fallback_events`（首帧失败任务数）与 `fallback_steps`/`fallbacks`（降档重发跳数）分列；旧路径一次失败一帧 → 三者相等，语义无漂移。
- `tier_*` 为**帧档位计数**（真通路含回退重发帧）；旧路径 tier_residual 含零基、真通路分列 residual_zero——两口径不可跨 run 混排，以 manifest.config.residual_true_path 区分。
- 任务返回增 `final_recovery_ok`（最终恢复成功）与 `checksum_ok`（首帧 L1+L2 通过）分立。

## 4. 附带修复（本 PR 范围内）

- `cosine()` 维度强校验：`len(a) != len(b)` 抛 `ValueError`（zip 静默截断会造出假高相似）。
- `abl_no_memory` 消融同步重置 VectorIndex（防悬空句柄污染消融口径）。
- `_TIER_RANK` 补 hidden:3 映射（与 CNR ENCODING_RANK 值域同步）。
- `decode_bytes`/`deserialize_base` 畸形输入显式 ValueError（受控回退，不崩溃）。
- 其余附带项（演化链 self-link、复用计数语义、CoQA 真 top-k 或参数改名、ToM 选基三档报告）**不入本 PR**，拆后续提交。

## 5. 兼容与回归防护

- `cfg.residual_true_path = False`（默认）：完整保留旧路径（旁路+改账消融+标签三档），既有测试与历史口径零影响。
- `ResidualCodec.decode(pkt, B_hat)` 旧接口保留；`encode()` 的 `pkt.checksum` **保持旧口径** digest_ints（跨 run 对账字段零变化）；新路径 L1 在帧层单独计算。
- `abl_no_checksum` 在真通路下语义 = **无校验信道**（L1+L2+身份校验全关，接收方接受任意 top-1 恢复）——展示无校验的静默损坏风险，非单变量微消融；需单变量消融时应分别用 L1/L2 独立开关（后续 Issue）。
- 翻转默认值 = 独立提交（配合真实 API 评测重跑与指标口径说明），不在本 PR。

## 6. 能力边界声明（v2：三路审查后如实分档；v3 数字随分支末态刷新）

**已实现且已验证（mock 80 tests + 真实 API signal/hotpot/CoQA 探针）**：
- 同进程共享 CAS/VectorIndex 原型上，残差/全量向量重构结果真实驱动文本检索恢复并成为 summarizer 唯一输入；
- L1 帧级完整性可由仅凭线缆帧字段的接收逻辑复算（to_wire 反序列化驱动，测试锁定）；keyed MAC 128bit + 常量时间比较 + 重放窗口已实现（同会话内成立）；
- 基=mem_id 记忆边信息解析、content_digest 身份校验、逐跳回退链每跳消费帧、四档（residual/residual_zero/embedding/text）真实分叉 + 三方率失真选档、CNR negotiate 驱动、no-residual 真向量消融、ToM 三档选基分列；
- 真实 API wire 演进链（同任务族 signal，qwen3-235b + text-embedding-3-small 1536 维）：
  原域残差 **-42.5%** → 三方率失真（短文本轮自动 text 档）**-21.4%** → 投影域 proj384 **+25.1%**（收缩 +64.3%/因果 0.27/5-5 残差恢复零回退）；CoQA 句级 top-k token 省 62.4% 且 F1 非劣（详见 §8）。

**原型或代理验证（不得对外夸大）**：
- CAS 与 VectorIndex 为 SynapseSession 内同进程对象；发送方同轮发布 `量化Y→text_handle` 恢复目录（"自我实现恢复"的代理实现）；vec_index 线性扫描跨任务无界增长（V3-06 数据平面处理）；
- 接收逻辑与发送方在同一函数调用序列内执行（结构上已隔离为 `_receive_frame(msg)`，但无独立进程/传输层）；
- executor 链路的 evidence 注入仍为发送方域内直通（CodeAct 需精确输入；真通路约束的是 retriever→summarizer 流）。

**规划中（V3-05/V3-06 及以后）**：SharedMemoryCAS、独立接收端进程、AF_UNIX receive loop 与数据 blob 同步、跨进程密钥协商分发、faiss 索引、跨进程端到端字节/延迟。

**禁止的强表述**（在上述完成前）："跨进程真通路已实现"；"接收方仅靠自身记忆恢复"（现为共享 MemoryStore）；"完整端到端通信成本=residual bytes"（CAS/索引/记忆建立成本另计）。

## 7. 第二轮复审补强（2026-08-28 晚，Issue 完整闭环）

用户裁决"不留问题待后续处理"后补完的 Issue checklist 项与审查遗留：

- **ToM 选基三档**（`cfg.base_policy`）：oracle（发送方以 Y 择优=乐观口径）/ query_top1（检索 top-1，接收方可复现=诚实口径）/ learned（topic 巩固原型=聚合学习式）；非文本字节按档分列（`base_bytes_*`）——R-P0-6"三档另报"落地，oracle 载荷不再单独对外。
- **三方率失真选档**：残差 / 全量向量 / 全文取最小（payload 字节同口径比较）——短文本+稠密向量场景诚实选 text 档；wire 结论按 Pareto 报告，不设档位偏好。
- **keyed MAC**：L1 升级为会话密钥 blake2b（`key` 参数）——主动方无密钥不能重算校验和（伪造测试锁定）；跨进程密钥分发经 CNR hello 协商（路线图）。
- **重放窗口**：已成功消费帧（key=generation:msg_id，Scheduler 跨任务 msg_id 重复须以任务代区分——实测修复）重复投递拒绝。
- **演化链修复**：原型 self-link 消除（幂等覆盖无旧版本实体，links=()；同时消除原型被自身 supersede 而检索不到的 bug）；链接扩展允许召回 superseded 历史版本（0.3× 权重）——"沿链接扩大召回"自此真实发生。
- **复用计数语义**：仅被消费的 top-1 计 `reuse_count`（top-k 全计为乐观口径）；扩展召回不计。
- **CoQA 真句级 top-k**（`cfg.qa_story_mode: full|sentences`）：sentences 模式故事切句入记忆、每轮按问题检索 top-`qa_sentences_k` 句（参数自此真实生效，mock 测试锁 token 下降）；full 保留历史口径。

## 8. 创新增强：JL 投影域残差（`cfg.residual_project_dim`，默认 0=关）

问题：高维稠密句向量（text-embedding-3-small 1536 维）能量均匀，原域稀疏残差达标分量数 O(dim)，
短文本场景残差大于全文（wire 负收益的物理根因）。

机制（`stateplane/projection.py`）：确定性 ±1/√dim 随机投影到 k 维（JL 引理近似保持余弦几何，
符号矩阵 seed 派生零存储共享）后，残差/索引/L2 校验全在投影域——达标分量数按维数比缩至 O(k)，
残差字节 ≈ k/dim 倍下降；接收方基解析经同一共享投影（帧 meta.project_dim 声明，不一致即回退）；
content_digest 身份校验仍在文本域兜底（投影域 cos 与原域存在 ~O(1/√k) 估计偏差，
错配候选由身份校验拒绝走回退链）。

**真实 API 实测（2026-08-31，qwen3-235b + text-embedding-3-small 1536 维，signal 5+5 轮/点，
runs/signal_20260831_*）**：

| proj_dim | wire 节省 | 关联族收缩 | 因果比 | 恢复/回退 |
|----------|-----------|------------|--------|-----------|
| 0（原域） | -21.4%（三方率失真后） | 0→759B 反向 | WARN | 5/5（2res+3text）/ 0 |
| 256 | +26.2% | -11.9% | 0.78 | 5/5（4res+1emb）/ 1 |
| **384（建议 operating point）** | **+25.1%** | **+64.3%** | **0.27** | **5/5 全 residual / 0** |
| 512 | +18.8% | +54.3% | 0.40 | 5/5 全 residual / 0 |

原域残差 ~1170B/轮 → proj384 后 ~190-250B（≈维数比，符合理论）；wire 从 -42.5%（原域残差）
逆转为 +25.1%，KC-1 三判定全 PASS。mock 验证另见
test_projection_domain_residual_shrinks_bytes。

**ToM 选基三档实测（评审 P3-3 补齐，N=10 × proj384，runs/signal_20260831_12*，2026-08-31）**：

| base_policy | wire 节省 | 关联族收缩 | 因果比 | 恢复/回退 | 分列字节 |
|-------------|-----------|------------|--------|-----------|----------|
| oracle（发送方以 Y 择优，乐观口径） | +25.8% | +14.4% | 0.41 | 10/10 / 1 | 3096 |
| **query_top1（检索 top-1，接收方可复现）** | **+31.0%** | **+63.3%** | **0.16** | **10/10 全残差 / 0** | **2133** |
| learned（topic 巩固原型） | +30.0% | +39.8% | 0.25 | 10/10 全残差 / 0 | 2370 |

关键发现：**诚实口径 query_top1 全面优于 oracle 乐观口径**（更省、零回退、因果区分更强）——
R-P0-6"encoder-oracle 乐观载荷"的担忧被实测消解：协议不依赖发送方偷看 Y 也能拿到更优数字。

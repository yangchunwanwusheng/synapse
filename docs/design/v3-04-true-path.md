# V3-04 前置设计冻结：残差/VLC 真数据通路（Issue #148746）

> 状态：**冻结**（2026-08-28，Issue 要求"8-28 前冻结，评审后开工"）
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

**新设计**：

- **L1 完整性校验（bit-exact，替代旧 checksum）**
  - 哈希对象：`H(residual_bytes || base_handle || generation)`，blake2b 8 字节。
  - 接收方仅凭消息内字段（residual 句柄取回的字节、base_handle、meta.generation）即可**复算**，零文本依赖。
  - 拦截面：传输损坏、residual 字节篡改、跨 generation 重放（同字节同基在不同任务代必失败）。
  - `Message.checksum` 字段语义升级为该值；`ResidualPacket.checksum` 同。
- **L2 语义校验（近似，保留余弦语义）**
  - 判据：`cos(Ŷ_q, Y_cand_q) ≥ verify_threshold`，其中 `Y_cand_q` 是接收方按句柄/向量索引检索所得候选的量化向量（见设计二）。**不再**为校验取全文重嵌入——旁路根因即在此。
  - 拦截面：预测基失配（desync）、int8 裁剪失真过大。
  - 失败动作：走回退链（残差→embedding→text），非静默。

两级语义：L1 保证"字节没坏"，L2 保证"语义够近"；任一失败即降档，端到端正确性由回退保障。

## 2. 前置设计二：重建结果消费语义

**发送方**（retriever，run_task 内）：

1. `Y = embed(evidence)`；`b_hat, base_sim = ToM.best_base(...)`（择基逻辑不变）。
2. **量化基入 CAS**：`base_bytes = pack_int16(quantize(b_hat))`（零基 = 全零向量同样入库，路径统一）→ `base_handle = cas.put(base_bytes)`。此后发送方的 `b_hat` 浮点对象**不再**被接收方引用。
3. `pkt = codec.encode(Y, b_hat, base_handle, generation)`；`residual_handle = cas.put(pkt.residual)`。
4. **向量可寻址索引**（新组件 `stateplane/vector_index.py::VectorIndex`）：`vec_index.put(text_handle, quantize(Y))`——文本句柄 ↔ 量化向量的共享检索面（M4 非文本状态寻址 + M5 共享记忆的交点）。
5. 消息：`handles = (residual_handle, base_handle, text_handle)`，`checksum = L1 值`，`meta = {nontext_bytes, nnz, tier, generation}`。

**接收方**（summarizer 侧恢复）：

1. `residual = cas.get(residual_handle)`（字节）。
2. **L1**：`H(residual || base_handle || generation) == msg.checksum`？失败 → 回退链。
3. **按句柄解析基**：`bq_recv = unpack_int16(cas.get(base_handle))`——接收方只依赖句柄可见内容。
4. `Ŷ_q = codec.decode_bytes(residual, bq_recv, dim)`。
5. **L2 + 文本恢复**：`(cand_handle, sim) = vec_index.search(Ŷ_q, top1)`；`sim ≥ verify_threshold` → `recv_text = cas.get(cand_handle).decode("utf-8")`。**recv_text 即 summarizer 的唯一 evidence 输入**。
6. 回退链（任一级失败）：
   - 跳 1（embedding 档）：发送方补发全量量化向量 `vec_handle = cas.put(pack_int16(Y_q))`，`payload_kind="embedding"`；接收方 `vec_index.search(Y_q)` 恢复（精确命中，sim=1）。
   - 跳 2（text 档）：全量文本直传（现回退路径）。
   - 每次降档重发计一次 `fallbacks`（口径=降档次数，PR 说明）。

**e2e 无旁路断言**（对应 Issue"删重建逻辑答案必须变化"的可测形式）：
- L2 恢复被替换（注入更相似干扰项 / monkeypatch 索引返回）→ summarizer 输入随之变化，证明 Ŷ 真实驱动下游；
- 重建被破坏（decode 输出垃圾）→ 检索失配 → 回退通道接管（recovery/fallback 计数变化），而非静默沿用旁路全文。
- mock 模型输出由 topic 决定，conclusion 字符串对输入不敏感，故断言落在"summarizer 实际输入 + 路径统计"上（等价且更严格）。

## 3. 三档真实分叉 + CNR 驱动 + 冷启动诚实标档（R-P0-4）

**发送方意向选档**（诚实分档，值域 `{residual, residual_zero, embedding, text}`）：

| 条件 | 意向档 | 线缆载荷 |
|------|--------|----------|
| 有基且 `base_sim ≥ verify_threshold` | `residual` | 稀疏残差 packet |
| 有基但 `0 < base_sim < 阈值` | `embedding` | 全量量化向量 packet（dim×2B + 头） |
| 无基（冷启动） | `residual_zero`（诚实档，非 residual） | 零基残差 packet（字节大，收缩序列合法起点） |
| `abl_no_residual` 消融 | `embedding` | 全量量化向量 packet（**真实字节**，修复 R-P0-3 改账） |

**CNR 门控（negotiate() 真实调用）**：`tier = min(意向档, cnr.negotiate(retr, summ))` 按 `ENCODING_RANK` 降档；residual_zero 与 residual 同受 residual 能力门控；negotiate 返回 text → 直接文本档。`residual_zero` 计入新指标 `tier_residual_zero`（与 `tier_residual` 分列，冷启动不再冒充强基）。

**接收端恢复路径统计**（新增）：`recovery_residual / recovery_embedding / recovery_text` 计数 + `tier_residual_bytes / tier_embedding_bytes` 字节构成（Issue"三档字节构成断言+回退率统计"）。

## 4. 附带修复（本 PR 范围内）

- `cosine()` 维度强校验：`len(a) != len(b)` 抛 `ValueError`（zip 静默截断会造出假高相似）。
- 其余附带项（演化链 self-link、复用计数语义、CoQA 真 top-k 或参数改名、ToM 选基三档报告）**不入本 PR**，拆后续提交，避免单 PR 范围失控。

## 5. 兼容与回归防护

- `cfg.residual_true_path = False`（默认）：完整保留旧路径（旁路+改账消融+标签三档），既有测试与历史口径零影响。
- `ResidualCodec.decode(pkt, B_hat)` 旧接口保留（旧路径/旧测试使用）；新路径走 `decode_bytes(residual, bq_recv, dim)`。
- `encode()` 的 checksum 统一升级为 L1 对象（旧路径中该值仅为消息字段透传，无行为差异）。
- 翻转默认值 = 独立提交（配合真实 API 评测重跑与指标口径说明），不在本 PR。

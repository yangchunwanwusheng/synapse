# GitLink Issue 发布包 v3.1

> 用途：在 https://gitlink.org.cn/liuruifei/yzmxdzntxzddkxtxztcdygxjyjz 逐条建单，供团队（A 机制 / B 系统 / C 实验 / D 质量与材料 四角色，2–4 人）协作开发。发布动作待用户确认后执行（手动粘贴或走 API）。
> 依据：`docs/决赛T45总执行方案-v3.md`（v3.1 定稿）+ `docs/决赛前源码彻查报告-20260827.md`。
> 通用规则（建单时置顶为仓库公告）：①Conventional Commits；②每 PR 必过 `scripts/ci.ps1`（或 ci.sh）；③新机制一律 config flag 门控默认关；④四个锁旧口径测试的基线更新须独立 commit 说明差量；⑤`runs/` 只增不改；⑥四档 Claim 纪律（CONTRIBUTING §4）。
> 建议标签：`P0`/`P1`、`Batch1`–`Batch4`、`mechanism`/`transport`/`stats`/`evidence`/`docs`/`infra`；里程碑按批次建 4 个（G1–G4 门槛日期为里程碑截止）。

---

## Batch 1（8-27 → 9-6，里程碑 G1：真实性地基）

### V3-01 · docs(claims): 全部完成态 Claim 三跳可溯源，旧强数字从 README/PPT/说明书物理替换
**标签**：P0, Batch1, docs · **负责人建议**：D · **人日**：2–3 · **依赖**：无

**背景**：内部审计确认部分完成态表述缺少可检验证据链，个别强数字的证据口径需要收敛。本 Issue 建立主张台账并统一材料口径。

**Checklist**：
- [ ] 建 `docs/claim-evidence.csv`（claim_id/表述/状态四档/source_path/test_path/run_path/可用措辞/禁用措辞）——验收：覆盖 README+PPT+说明书全部完成态声明
- [ ] README 数字按 v3.1 §三改口表逐条替换——验收：每条挂聚合表或 run 链接
- [ ] **旧材料物理替换**：说明书/PPT 经 `docs/final/` 构建链重生成（不手改二进制）——验收：新材料数字与 README 同源，仓库无新旧两套并存
- [ ] 撤下/降档四项：ΔF1+0.333、MuSiQue 80.90%（→探索性标注）、"统计不可区分"（→区间表述）、"零拷贝/沙箱安全"（→实际档位表述）——验收：全文检索无残留
- [ ] Claim 台账与代码对账一轮——验收：每条主张三跳内可达证据（主张→文件→run/测试）
- [ ] PPT 相关工作段按三类对照重写（含 MemOS 划界）——验收：无"唯一/首次"类表述

**不建议提交**：审计未完成前新增任何完成态能力声明；手改 PPT/说明书二进制。

### V3-02 · feat(evidence): 双层计量 manifest——chat/embed、logical/transport 自动聚合且计数守恒
**标签**：P0, Batch1, evidence · **负责人建议**：C（schema 冻结后 A 协同改发送方计量）· **人日**：5–7 · **依赖**：无

**背景**：现有落档缺 code_sha/数据版本/逐题记录；计量存在手工相加代理值与真实帧长不一致的问题。本 Issue 建立全实验证据基础设施。

**Checklist**：
- [ ] result JSON Schema 定稿（run 元信息/逐题/聚合三层）——验收：schema 文件入库+校验脚本
- [ ] `cli.py` 全部 9 个子命令落档 manifest（code SHA、配置快照、模型与数据集版本、seed、温度、UTC 时间、OS/Python/依赖锁摘要）——验收：任一命令跑后 result.json 含全字段
- [ ] chat/embedding token 分列计数（usage 缺失时 fail 而非计 0）——验收：单测覆盖缺失场景
- [ ] logical_bytes（协议表达）与 transport_bytes（真实帧长，对 `to_wire()` 编码后计数）双口径——验收：恒等式 transport=Σ帧长、logical=Σ(header+payload) 对账测试通过
- [ ] CAS 写入与 embedding 请求计入 cold 成本，warm 路径记录 cache hit——验收：冷/暖两栏分列
- [ ] 合成 AB 聚合补 llm_input/output_tokens 累加，旧代理指标删除或显著标记——验收：实跑后非零
- [ ] config 加载 fail-fast（YAML 异常退出而非回默认）——验收：坏配置单测
- [ ] 旧 106 个 runs 生成 sidecar 索引（不改写原始文件）——验收：索引含 run 时间/类型/模型版本

**不建议提交**：聚合不幂等；旧 runs 原始文件被改写；schema 未冻结就开改 metrics.py（会阻塞 V3-04）。

### V3-03 · test+exp(stats): 多参考 F1/EM 与题目级 cluster bootstrap 通过 golden case，MuSiQue N≥100 重跑
**标签**：P0, Batch1→Batch3（统计代码 Batch1，重跑 Batch3）, stats · **负责人建议**：C · **人日**：5–7+API · **依赖**：V3-02

**背景**：评分器未按官方多参考口径（MuSiQue aliases 被丢弃、EM 缺失）；统计存在题内重复被当独立样本的问题；MuSiQue 强数字证据不足需扩样。

**Checklist**：
- [ ] `normalize_answer`/单参考 F1/多参考 max 聚合/EM 实现，对齐 SQuAD/HotpotQA 官方脚本——验收：官方 golden case 对拍通过
- [ ] 抓取脚本保留 `answer_aliases`/`question_decomposition`（CoQA 全参考）+ dataset revision 固定 + 数据 SHA 入 manifest——验收：重抓数据哈希一致
- [ ] MuSiQue 异常题过滤（19 段/单金标题）+ 过滤日志——验收：200 题全量校验通过
- [ ] 题目级 cluster bootstrap（先题内均值再题间 bootstrap），报告 run 间/item 间方差——验收：已知小样本精确输出锁定单测
- [ ] 预注册非劣界（δ 提前写入实验协议），配对 AB/BA 题级交替+执行序列落档——验收：协议文件先于跑批入库
- [ ] N=10 双数据集方向探针（新模型）——验收：探针报告落 runs/，不升格结论
- [ ] MuSiQue N≥100 全量重跑（Batch3；含负结果）——验收：逐题预测+金标+全参考落档，聚合脚本一键复算

**不建议提交**：N<30 结果升格主结论；对 WORSE 结果选择性沉默；阈值事后调参。

### V3-04 · feat(mechanism): 残差/VLC 真通路——接收方仅凭句柄重建并消费，三档载荷真实分叉
**标签**：P0, Batch1→Batch2, mechanism · **负责人建议**：A · **人日**：12–16 · **依赖**：V3-02

**背景**：现路径接收方在校验前已从同进程 CAS 取得全文，重构向量仅作布尔校验未进任务数据流；编码档位为标签；校验码未参与验证。本 Issue 让机制成为真实数据通路。

**Checklist**：
- [ ] **前置设计冻结（8-28）**：checksum 哈希对象重设计（对 residual 字节+base_handle+generation 哈希，接收方可复算；与余弦语义校验分立两级）——验收：设计说明入 docs，评审通过
- [ ] **前置设计冻结（8-28）**：重建结果消费语义（Ŷ→按句柄检索匹配→恢复文本表示→入下游；回退链 残差→embedding→text）——验收：设计说明入 docs
- [ ] 失败测试先行："删重建逻辑答案必须变化"、"篡改 residual 字节 checksum 必须拦截"——验收：测试红→绿过程留 commit 记录
- [ ] 接收方仅按 base_handle 从自身记忆解析预测基（不直接复用发送方 b_hat 对象）——验收：单测模拟接收方独立状态
- [ ] 校验后重建结果成为 summarizer 唯一输入（全文仅经独立回退通道获得）——验收：e2e 测试断言无旁路读取
- [ ] 三档真实数据路径：residual/全量 embedding/text 三种编码+计量分叉，CNR `negotiate()` 结果驱动选档，冷启动诚实标 text/embedding——验收：三档字节构成断言+回退触发率统计
- [ ] 真实 no-residual 消融路径（独立 full-vector packet，非改账）——验收：消融 run 载荷与主路径可区分
- [ ] ToM 选基分三档报告：query-top1 / encoder-oracle / 学习式——验收：三档对比表落 runs/
- [ ] 附带修复（随真通路改造）：演化链 self-link、cosine 维度强校验、复用计数语义、CoQA 真top-k 或参数改名——验收：对应单测

**不建议提交**：任何绕过重建直接取全文的捷径残留；阈值调整以掩盖质量下降（走回退率与 Pareto 报告）；破坏 21 个既有测试且无基线说明。

### V3-05 · feat(transport): AF_UNIX 控制面通过 framing/超时/死亡检测故障矩阵
**标签**：P0, Batch1→Batch2, transport · **负责人建议**：B · **人日**：5–7 · **依赖**：V3-02

**背景**：现调度为进程内直调。建立 Transport 抽象与真实 AF_UNIX 控制面，为跨进程数据平面与真实 transport 计量打地基。

**Checklist**：
- [ ] `protocol/transport.py` Transport 协议 + `InProcessTransport` 包装现有路径——验收：21 测试零回归
- [ ] framing（长度前缀或 SEQPACKET）、超时、优雅/重复关闭、并发 send 语义单测——验收：契约测试全过
- [ ] `UnixSocketTransport`：对端不存在/崩溃/半开/消息截断故障测试——验收：全矩阵通过（Linux 容器内跑）
- [ ] 应用层 transport bytes 接入 V3-02 双口径——验收：Socket 路径计数守恒
- [ ] 容器内端到端探针（握手→发现→路由→关闭）——验收：演示脚本+失败日志入库
- [ ] 背压与自动重连明确为 P1 后续，不阻塞本 Issue——验收：范围声明写入 PR

**不建议提交**：宣称跨平台（限定 Linux/openEuler）；无死亡检测测试。

### V3-08 · chore(infra): SP3 容器门禁 + CodeAct 执行边界如实化
**标签**：P0, Batch1, infra · **负责人建议**：D · **人日**：2 · **依赖**：无

**背景**：openEuler SP3 为赛题验收红线；CodeAct 执行器的隔离能力需实测界定（第三方库自述非安全沙箱、超时线程不可强杀）。

**Checklist**：
- [ ] GitLink DevOps"引擎"配置与 ci.sh 等价门禁——验收：**一次故意失败的 PR 被流水线拦截**（截图/日志入 docs/工程化基线.md）
- [ ] SP3 容器构建+运行证据（镜像 digest/架构/内核/退出码）——验收：带时间戳日志入库
- [ ] CodeAct 边界实测报告（超时后线程状态/import 可达性/文件系统可达性）——验收：报告入 docs
- [ ] 二选一落地：独立可杀执行进程+资源限制（表述升"进程级隔离"）或材料统一降"受限解释器，非安全沙箱"——验收：README/说明书口径一致
- [ ] `--shm-size` 参数预置进 docker-compose（为 V3-06 备）——验收：配置文件更新
- [ ] master 分支保护开启（禁直推/强推，PR≥1 审查）——验收：平台配置导出入库

**不建议提交**：仅容器证据却写"原生 openEuler 已验证"；保留"沙箱安全运行"旧表述。

---

## Batch 2（9-7 → 9-20，里程碑 G2：真实数据平面）

### V3-06 · feat(stateplane): SharedMemoryCAS + 四 Agent 多进程 10 轮稳定无静默损坏
**标签**：门控P0, Batch2, stateplane/runtime · **负责人建议**：A+B · **人日**：10–14 · **依赖**：V3-04+V3-05（**G1 未过不得启动**）

**背景**：现 CAS 为进程内 dict。在真通路机制之上建立跨进程数据面，回答"状态是否真实跨进程交换"。

**Checklist**：
- [ ] BlobStore 协议抽自 cas.py；MVP=每对象一 `/dev/shm` 文件（O_EXCL+0600）——验收：环形分配器等复杂方案明确不做
- [ ] 句柄契约（backend/object_id/generation/length/checksum/lease_expiry）+ 文件锁元数据——验收：跨进程解析测试
- [ ] 子进程按可序列化配置自行重建 Agent/模型 client/executor（禁 pickle 已构造对象；spawn/forkserver）——验收：四进程 spawn 冒烟
- [ ] 故障注入矩阵：bitflip/stale handle/desync 预测基/发送方崩溃/重复释放/进程退出回收——验收：0 静默损坏
- [ ] 64B/4KB/1MB 三档跨进程一致性 + /dev/shm 零残留——验收：泄漏测试
- [ ] 四进程 10 轮双模式×3 次稳定复跑（含异常退出→重启场景）——验收：G2 门槛数据落 runs/
- [ ] 基线 vs SHM 双路径延迟/CPU 数据——验收：对比表落 runs/
- [ ] 崩溃自动重启降 P1（本 Issue 只做确定关闭）——验收：范围声明
- [ ] `/dev/shm` 容量防护（ENOSPC/SIGBUS）与残留清理——验收：异常注入测试

**不建议提交**：偶发 flaky 合并；G1 未过强行启动；无故障矩阵即宣称"可靠协作"。

### V3-09 · docs(repo): 开仓体验——README 主张三跳到达证据
**标签**：P0, Batch2, docs · **负责人建议**：D · **人日**：2（框架） · **依赖**：V3-01+02（框架）；V3-03（数字回填）

**Checklist**：
- [ ] runs/（630K/106 文件，已扫描无密钥无路径）+04-analysis/_state/01-idea/02-design 入库——验收：用户逐目录确认后分批 commit
- [ ] 根 README 首屏加五维对照表锚点+三跳溯源示例（主张→runs 目录→CSV）——验收：任选 3 条主张点验
- [ ] `.zcode/`、`.claude/`、工作区 AGENTS.md 确认不入库——验收：git status 干净
- [ ] 入库前自动扫描（密钥模式/绝对路径/>1MB）——验收：扫描脚本+零命中记录
- [ ] 数字回填位（占位标注"待 V3-03 重跑"）——验收：回填后无占位残留

---

## Batch 3（9-21 → 9-30，里程碑 G3：机制证据）

### V3-07 · exp(ablation): 双矩阵因果归因——语义四档与 IPC 路径分离，HotpotQA N≥100
**标签**：P0, Batch3, evidence · **负责人建议**：C（A/B 锁代码只修阻断）· **人日**：5–7+API · **依赖**：矩阵A=V3-02/03/04/05；矩阵B=+V3-06

**Checklist**：
- [ ] 矩阵 A（固定 IPC，比语义编码）：Text Full→Structured Full→Full Embedding→Residual——验收：同任务/同模型/同 seed 逐项配对
- [ ] **相同检索上下文公平层**：同 top-k 下 text payload vs embedding vs residual（回答"关掉残差 71% 是否还在"）——验收：分项收益表
- [ ] 矩阵 B（固定 payload，比 IPC 路径）：Socket 全量 vs 句柄+共享段——验收：字节/延迟/CPU 三轴
- [ ] HotpotQA N≥100+题目级 bootstrap（统计纪律同 V3-03）——验收：manifest 先行入库
- [ ] 指标四层：质量（F1/EM+CI）/通信（token 双口径+字节双口径）/系统（p50/p95、CPU、RSS、/proc io、strace -c）/学习效应（命中率、残差轨迹、回退率）——验收：四层齐全才下系统级结论
- [ ] 负结果如实入表（失败样本+分位数）——验收：无挑最佳配置
- [ ] claim-evidence 对照自动生成（PPT/README 数字从聚合产物出）——验收：一键再生成一致

**不建议提交**：任一档缺系统指标就宣称系统级结论；矩阵 B 未就绪时用矩阵 A 冒充端到端节省。

---

## Batch 4（10-1 → 10-11，里程碑 G4：冻结答辩）

### V3-10 · docs(final): 答辩产品化——双版本 PPT、黄金演示五连、两环境复现、发布冻结
**标签**：P0, Batch4, docs · **负责人建议**：D 主持全员参与（每周演练自 Batch1 起）· **人日**：4–6 · **依赖**：全部核心项

**Checklist**：
- [ ] 七幕 PPT 15 分钟版+8 分钟版（第六幕=证据账本页：冷/暖分列、清空消融、漂移闭环、全口径总账+仓库路径角标）——验收：数字全部来自聚合产物
- [ ] 黄金演示路径（冷启动→暖启动→清空记忆→漂移回退）离线 5 连成功——验收：录屏+失败点记录
- [ ] 两个干净环境+一次完全离线复现（含 `uv run synapse smoke` 兜底演练）——验收：耗时与失败点记录
- [ ] 30 题答辩题库（含：是否只是 RAG/省的是跨进程通信还是进程内计数/拷贝次数/恶意代码隔离/与竞品差异/数字口径）——验收：每题 30 秒+2 分钟两版答案
- [ ] 降级三预案（无网络/API 不可用/看板失效）——验收：演练记录
- [ ] 10-1 功能冻结、10-4 RC、10-6 后只修阻断——验收：里程碑记录
- [ ] 发布：tag+镜像 digest+离线包+回滚方案——验收：release 资产齐备
- [ ] 说明书/PPT/README 数字终对账（三处同源）——验收：脚本 diff 为零

**不建议提交**：手工改数字；演示依赖现场网络；T-5 后新增机制名。

---

## 发布操作说明

1. **里程碑**：先建 4 个里程碑（Batch1 G1 9-6 / Batch2 G2 9-20 / Batch3 G3 9-30 / Batch4 G4 10-11）。
2. **建单顺序**：Batch1 六单可全部立即建（V3-01/02/03/04/05/08）；V3-06/09 建单时标注"门控：G1 通过后启动"；V3-07/10 标注对应依赖。
3. **每单正文**：直接复制本文件对应节（标题用建单标题，Checklist 保留复选框语法，GitLink 支持 markdown 任务列表）。
4. **置顶公告**：通用规则 6 条（见文件头）作为仓库公告或 CONTRIBUTING 附加节发布。
5. **执行确认**：本发布包经用户确认后执行；API 建单路径与凭据沿用项目既有 GitLink 集成方式（不经明文凭据入仓）。

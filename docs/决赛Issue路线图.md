# SYNAPSE 决赛 Issue 路线图

本文件用于把夺冠路线图拆成可分工、可验收、可关闭的 Issue。编号是建议顺序，不是远端平台的最终 Issue 号。

## Milestone M0：工程可信基线

| 编号 | 标题 | 优先级 | 依赖 | 验收摘要 |
|---|---|---|---|---|
| M0-01 | 修复源码包复现入口 | P0 | 无 | 新环境 `uv sync --locked --extra dev`、测试、smoke、build 全通过；本轮已完成 |
| M0-02 | 建立 CI 与本地统一门禁 | P0 | M0-01 | Python 3.11/3.13 lint、test、smoke、build；openEuler Docker smoke；本轮已加入工作流 |
| M0-03 | 启用 GitLink 流水线与主分支保护 | P0 | M0-02 | 远端 PR 必须通过流水线；master 禁直推；至少一人审查 |
| M0-04 | 完成 Claim—实现—证据审计 | P0 | 无 | README/PPT/说明书每个完成态声明都有源码、测试、结果路径；超前声明降级为规划 |
| M0-05 | 规范远端资料与大文件 | P1 | M0-04 | 明确源码、研究记录、提交包、生成物边界；远端成为可复现事实来源；不误提交密钥 |

### M0-03 建议 Issue 正文

**目标**：让托管平台而非口头约定执行合并规则。  
**范围**：GitLink 流水线、分支保护、PR 审查，不包含自动部署。  
**验收**：

- push/PR 自动运行与 `scripts/ci.sh` 等价的门禁；
- 任一 lint/test/smoke/build 失败时禁止合并；
- `master` 禁止直接推送和强推；
- 至少 1 名审查者，核心协议/实验主结论至少 2 名；
- 截图或平台导出配置进入 `docs/工程化基线.md`。

### M0-04 建议 Issue 正文

**目标**：消灭“文档已完成、代码未实现”的决赛致命风险。  
**重点核对**：共享内存 CAS、faiss、Socket/eBPF、CodeAct 沙箱隔离等级、非文本状态是否真实跨 Agent 边界。  
**验收**：建立 `claim-evidence.csv`，至少含 `claim_id / 表述 / 状态 / source_path / test_path / run_path / 可用措辞 / 禁用措辞`；根 README 不再包含无证据的完成态声明。

## Milestone M1：真实操作系统数据平面

| 编号 | 标题 | 优先级 | 依赖 | 验收摘要 |
|---|---|---|---|---|
| M1-01 | 抽象 Transport 与 BlobStore 接口 | P0 | M0-02 | 现有进程内路径无回归；传输与存储后端可替换 |
| M1-02 | 实现 AF_UNIX/Socket 控制面 | P0 | M1-01 | 四 Agent 独立进程可握手、发现、路由、超时和关闭 |
| M1-03 | 实现 SharedMemoryCAS 数据面 | P0 | M1-01 | 跨进程按句柄读写；校验、世代、租约、清理与泄漏测试通过 |
| M1-04 | 完成多进程 SynapseSession | P0 | M1-02,M1-03 | 10+ 轮双模式、异常退出和重启场景稳定 |
| M1-05 | 增加 Linux/openEuler 系统观测 | P1 | M1-04 | 字节、p50/p95、CPU、RSS、上下文切换/系统调用可复现采集 |

### M1-03 建议 Issue 正文

**问题**：当前 CAS 是进程内字典，不能证明非文本状态真实跨进程交换。  
**方案边界**：先实现 Python `multiprocessing.shared_memory` 或 Linux `memfd` 后端，不同时引入分布式对象存储。  
**句柄契约**：`backend、object_id、generation、length、checksum、lease_expiry`。  
**失败测试**：句柄不存在、世代不匹配、校验失败、接收方超时、发送方崩溃、重复释放、进程退出后的资源回收。  
**验收**：两个独立进程传递 64B、4KB、1MB 状态；内容一致；无资源泄漏；基线与共享内存路径均有延迟/CPU/字节结果。

## Milestone M2：自适应可靠通信

| 编号 | 标题 | 优先级 | 依赖 | 验收摘要 |
|---|---|---|---|---|
| M2-01 | 实现可解释的三档成本控制器 | P0 | M1-04 | text/embedding/residual 选择有显式代价和质量护栏；决策可记录 |
| M2-02 | 将残差反弹接入记忆失效 | P0 | M2-01 | 漂移时自动降权旧基、重协商/回退，恢复后重新收缩 |
| M2-03 | 完善 VLC 故障注入矩阵 | P1 | M1-03,M2-01 | desync、bit flip、stale handle、超时均无静默损坏 |
| M2-04 | 加入背压、预算与取消传播 | P1 | M1-02 | 队列过载、超时和取消有确定行为与指标 |

### M2-02 建议 Issue 正文

**Claim**：残差不仅压缩通信，也能以零额外模型开销感知共享知识分布变化。  
**验收场景**：稳定任务 5 轮 → 突然切换相关但新分布 3 轮 → 新分布稳定 5 轮。  
**通过标准**：漂移后指定窗口内触发；旧基不再被继续高置信复用；VLC 无静默错误；新基形成后残差再次下降；检测阈值在实验前固定。

## Milestone M3：冠军证据链

| 编号 | 标题 | 优先级 | 依赖 | 验收摘要 |
|---|---|---|---|---|
| M3-01 | 建立实验 manifest 与 result schema | P0 | M0-04 | SHA、环境、数据版本、seed、配置、逐项结果全部自动落盘 |
| M3-02 | 运行五档通信路径消融 | P0 | M1-04,M3-01 | text→structured→embedding→residual→shared-memory 分层归因 |
| M3-03 | 扩大真实数据主实验 | P0 | M2-02,M3-01 | 关键数据集 N≥30×3 seed；报告配对 CI 与质量护栏 |
| M3-04 | 完成系统性能基准 | P0 | M1-05,M3-01 | p50/p95、CPU、RSS、系统调用/切换与字节结果可复现 |
| M3-05 | 自动生成 claim-evidence 矩阵与图表 | P1 | M3-02,M3-03,M3-04 | README/PPT 数字来自同一聚合产物，不手抄 |

### M3-02 建议 Issue 正文

**目的**：回答“收益到底来自结构化消息、检索截断、残差编码、记忆，还是共享内存”。  
**固定五档**：Text Full、Structured Full、Full Embedding、Residual、Residual + SharedMemory + Memory Prior。  
**主指标**：任务质量、LLM token、控制面字节、数据面字节、端到端 p50/p95、CPU。  
**验收**：同任务、同模型、同输入、同 seed；逐项配对；报告失败样本；禁止只挑最佳 k。

## Milestone M4：答辩产品化与发布

| 编号 | 标题 | 优先级 | 依赖 | 验收摘要 |
|---|---|---|---|---|
| M4-01 | 构建实时机制看板 | P1 | M1-05,M3-01 | 展示消息、档位、残差、命中、回退、延迟；不承担核心逻辑 |
| M4-02 | 固化五分钟黄金演示 | P0 | M2-02,M4-01 | 冷→暖→漂移→回退→恢复，连续 5 次成功 |
| M4-03 | 全新 openEuler 复现演练 | P0 | M0-03,M1-04 | 三台/三次新环境部署，记录耗时与失败点 |
| M4-04 | 统一 README/说明书/PPT/视频数据 | P0 | M3-05 | 全部数字可追溯；无矛盾、无超前表述 |
| M4-05 | 建立答辩红队问题库 | P1 | M4-04 | 至少 30 个尖锐问题，每题有 30 秒与 2 分钟答案 |
| M4-06 | 发布决赛候选版本 | P0 | M4-02,M4-03,M4-04 | tag、镜像摘要、校验和、离线包、回滚方案齐全 |

## 推荐标签

- 优先级：`P0-blocker`、`P1-high`、`P2-normal`
- 类型：`bug`、`feature`、`experiment`、`docs`、`infra`、`security`
- 赛题：`score-communication`、`score-state`、`score-memory`、`score-system`、`score-evidence`
- 状态：`needs-design`、`ready`、`in-progress`、`blocked`、`needs-evidence`

## 并行分工原则

- 传输/共享内存与实验统计可并行，但在接口和 result schema 冻结后再大规模运行；
- 看板只能消费统一事件流，不得复制核心状态或另写统计口径；
- PPT/说明书更新依赖自动聚合产物，不和主实验同时手工改数字；
- 每个 P0 Issue 指定唯一负责人和备份人，避免“大家都在看、没人关闭”。


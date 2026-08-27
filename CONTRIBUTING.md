# SYNAPSE 协作开发规范

本项目同时承担竞赛原型、系统研究和公开开源交付三种职责。开发流程的目标不是增加形式，而是确保每个合并到主分支的结论都能回答三个问题：实现在哪里、测试在哪里、证据在哪里。

## 1. 开发流程

1. 先建 Issue，明确问题、赛题维度、验收标准和不做什么。
2. 从最新 `master` 创建短生命周期分支，建议命名为 `feat/<issue>-<slug>`、`fix/<issue>-<slug>`、`exp/<issue>-<slug>` 或 `docs/<issue>-<slug>`。
3. 行为变更优先补失败测试，再提交最小实现；实验变更先锁定 Claim、样本、seed、指标和停止规则。
4. 本地执行完整门禁后发起 PR，不直接向 `master` 推送功能提交。
5. PR 至少一人审查；涉及核心协议、实验主结论、密钥/沙箱/进程间通信的改动需要两人确认。
6. 合并后删除功能分支；需要改判的实验结论通过新提交修订，不覆盖原始结果。

## 2. 本地门禁

在 `源代码及readme文档` 目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/ci.ps1
```

Linux/openEuler 执行：

```bash
sh scripts/ci.sh
```

门禁包括锁定依赖同步、Ruff、Pytest、离线 smoke 和包构建。影响 Docker/openEuler 的改动还必须执行：

```bash
docker build -t synapse:local .
docker run --rm synapse:local
```

## 3. Definition of Done

一个 Issue 只有同时满足以下条件才可关闭：

- 验收标准已由自动测试或可复现实验覆盖；
- lint、测试、smoke、构建全部通过；
- 失败路径、兼容性和回滚方式已说明；
- 用户可见行为已同步 README、设计/部署文档或 CLI 帮助；
- 若改变实验结论，原始逐项结果、配置快照、数据版本、seed、统计脚本和聚合结果均可追溯；
- 没有提交密钥、`.env`、访问令牌、私有数据或含敏感信息的日志；
- 文档没有把规划、模拟、代理基线或未验证能力写成已实现、已实测事实。

## 4. Claim 与证据纪律

所有对外结论必须标记为以下四类之一：

- **已实现且已验证**：有源码入口、自动测试或真实实验产物；
- **已实现待扩样**：机制已运行，但样本量或外部效度不足；
- **原型/代理验证**：只验证了受控代理或注入场景，必须明示边界；
- **规划中**：只能进入路线图和 Issue，不得出现在“已具备能力”列表。

主实验至少记录：代码提交 SHA、配置文件、模型与服务端版本、数据集版本、样本选择、seed、温度、运行时间、环境、逐项结果和聚合方法。禁止只保留截图或只保留最终均值。

## 5. 提交与 PR

提交信息采用 Conventional Commits，例如：

- `feat(transport): add shared-memory CAS backend`
- `fix(packaging): add package README`
- `test(protocol): cover desynchronized prediction base`
- `exp(hotpot): add three-seed transport benchmark`
- `docs(final): align claims with verified evidence`

PR 应保持单一目标。算法实现、批量实验结果和答辩材料原则上分成不同 PR，便于审查与回滚。

## 6. 分支保护建议

在托管平台启用以下规则：

- `master` 禁止直接推送；
- 合并前必须通过 CI；
- 至少 1 名审查者批准；核心协议和实验主结论至少 2 名；
- 分支必须与最新主分支同步；
- 禁止强推和删除主分支；
- 合并策略优先 squash，保留 Issue 与 PR 的决策记录。


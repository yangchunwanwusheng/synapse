# 提交规范

> 本文件适用于研究生操作系统开源大赛 SYNAPSE 项目，约束 fork→主仓库的协作流程。

## 仓库拓扑

- **origin = fork** (`yangchunwanwu/yzmxdzntxzddkxtxztcdygxjyjz`)：日常 push 目标
- **upstream = 主仓库** (`liuruifei/yzmxdzntxzddkxtxztcdygxjyjz`)：MR 提交目标（队伍作品提交地址）
- **old-origin = 旧自建仓库** (`yangchunwanwu/synapse`)：已弃用，仅备查

## 分支策略

- `master`：比赛交付稳定版。每阶段审核 Gate 通过后由 `dev` 合入，并同步推送至 fork `master`。
- `dev`：开发主线。日常 push 目标，体现赛题要求的"持续更新"。
- `exp/<实验名>`：实验分支。如 `exp/real-task-mechanism`、`exp/vs-latentmas`。
- `paper/<章节>`：论文写作分支。如 `paper/method`、`paper/results`。

## Commit 规范

格式：`<type>: <描述>`

| type | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | 修复 |
| `exp` | 实验数据/脚本 |
| `docs` | 文档 |
| `test` | 测试 |
| `refactor` | 重构（不改行为） |

示例：
- `feat: 实现 no-residual baseline 代理臂 (P2)`
- `exp: HotpotQA 真实任务机制外推 N=100 (P2)`
- `docs: 补充 vs LatentMAS 对比设计 (P2)`

## 持续提交节奏（赛题明确要求"持续更新不一次性提交"）

### Fork push 节奏
- 每完成一个 **Task** 或 TDD 循环（红-绿-重构）立即 push 到 fork `dev` 分支
- **禁止囤积**：禁止等一个 P 阶段全部做完才一次性 push
- 单次 commit 粒度 = 一个可独立解释的变更（实验脚本 / 一个模块 / 一节论文）

### 主仓库 MR 节奏
- 每个 **P 阶段结束**提 1 次 MR（`upstream master` ← `fork dev`）
- 阶段内若达到重要里程碑（实验出结果 / 模块完成 / 审核通过），追加 1 次 MR
- 预期 MR 频次：P0/P1/P2 各 1–2 次，P3/P4 各 1–2 次，P5 最终 1 次

### MR 规范
- **标题**：`[P阶段号] 简述`，如 `[P1] 撞车复审完成 + 独占点验证`
- **源分支**：`yangchunwanwu/dev`（或 `yangchunwanwu/<feature>`）
- **目标分支**：`liuruifei/master`
- **正文模板**：
  ```
  ## 本 MR 内容
  - 变更摘要（3–5 条）
  ## 审核状态
  - G? Gate 通过情况
  ## 可复现性
  - 关键命令 / 数据位置
  ## 下一步
  ```

### 禁止行为
- ❌ 阶段结束前才一次性 push 全部（会被视为"突击提交"）
- ❌ 直接 push 到 `upstream master`（必须走 MR）
- ❌ 在 `master` 上直接做实验开发（实验一律在 `dev` 或 `exp/*`）

## 安全

- **`.env` 永不提交**（包含 API key）。.gitignore 已排除 `.env` / `.env.*`，仅放行 `.env.example`。
- 大文件（PDF/视频/模型权重）走 git-lfs 或外部存储，不直接 commit。
- 凭据（gitlink token）仅放 `~/.git-credentials`（credential.helper=store），不写进任何被追踪的文件。

## 与 Obsidian KB 的关系

- 研究知识层（idea / 文献 / 实验 / 论文草稿）维护在 Obsidian vault：`D:/learnevery/Research/synapse-repositioning/`
- 代码仓库（本仓库）只放：可运行代码 + 实验脚本 + runs/ 原始数据 + 赛题交付文档（docs/）。
- 两边通过 `.claude/project-memory/registry.yaml` 绑定，通过 `experiments/` 子目录内的 `protocol.md` 引用 KB 中的预注册协议。

# SYNAPSE 状态快照（2026-07-08）

## 当前阶段
**P0 完成（G0 通过）→ P1 完成（G1 通过）→ 准备进 P2**。idea 再定位完成，新 framing = 记忆即边信息。

## 代码现状
- 2353 行，5 模块，60 真实实验（runs/）
- M1–M11 基本满足，仅演示视频待录
- LLM 后端：Paratera API Qwen3-30B-A3B-Instruct-2507 temp=0

## 仓库状态（P0 已完成）
- origin (fork): yangchunwanwu/yzmxdzntxzddkxtxztcdygxjyjz.git（日常 push）
- upstream (主仓库): liuruifei/yzmxdzntxzddkxtxztcdygxjyjz.git（MR 目标）
- old-origin (弃用): yangchunwanwu/synapse.git
- 分支：master (71871c3) + dev (71871c3)，已同步到 fork
- tag: p0-done 已推送
- credential.helper = store，token 在 .env + ~/.git-credentials
- **首个 MR**: #16478 `[P0] 仓库 migration + contribution guide`，状态 open
- MR 创建 API 已掌握并记录到 KB registry（POST `/api/{owner}/{repo}/pulls.json`，无 v1）

## 顶会 framing
- 主线 D：记忆 = Wyner-Ziv 解码端边信息 B̂
- 次贡献 C：通信成本 = 漂移传感器
- 系统验证：openEuler 原型
- 独占点（待 P1 grep 验证）：①黑盒 API 可行 ②统一边信息视角 ③通信成本反向作漂移传感器

## 待办路线图
- **P0 仓库迁移 + MR 工作流 ✅ 完成（G0 通过）**
- **P1 撞车复审 + 独占点验证 ✅ 完成（G1 通过）**
  - 3 独占点全部成立（黑盒/统一边信息/漂移传感）
  - 新增 closest work：Interlat (ACL'26)、CIPHER (ICLR'24)、Semantic R-D (2604.09521)
  - ⚠️ 关键更正：LatentMAS v3 无"black-box future work"原话（P1-3 精读确认），改用 SDE §7 真实自述
- P2 证据补强：真实任务机制外推 + vs LatentMAS 公平对比（7-10天）← 下一步
- P3 比赛交付收尾：演示视频 + openEuler 实测 + 可选系统加分项（2-3天）
- P4 论文起草（nature-writing，5-7天）
- P5 投稿前自审 + 投递（2-3天）

## P1 关键产出（KB 内）
- `Writing/foundation/01_research_canon.md` §D/§E 更新（closest-work + 3 独占点验证）
- `Writing/foundation/02_evidence_table.md` §B closest-work table 补全（13 行，6 列）
- `docs/p1-collision-audit-report.md`（完整撞车复审报告）
- `Sources/Papers/LatentMAS.md` + `Sources/Papers/SDE.md`（精读笔记 + 白盒证据）

## 关键文件位置
- Obsidian KB: D:/learnevery/Research/synapse-repositioning/
- 计划文件: .../docs/superpowers/plans/2026-07-08-synapse-repositioning.md
- foundation 5 文件: .../Writing/foundation/{00_scope,01_research_canon,02_evidence_table,03_argument_map,04_section_contracts}.md
- Zotero collection: SYNAPSE-Repositioning (CPWA24ZF)，含 10 篇撞车论文

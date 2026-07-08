# SYNAPSE 状态快照（2026-07-08）

## 当前阶段
**P0 完成（G0 通过）→ 准备进 P1**。idea 再定位完成，新 framing = 记忆即边信息。

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
- P1 撞车复审 + 独占点 grep 验证（2天）← 下一步
- P2 证据补强：真实任务机制外推 + vs LatentMAS 公平对比（7-10天）
- P3 比赛交付收尾：演示视频 + openEuler 实测 + 可选系统加分项（2-3天）
- P4 论文起草（nature-writing，5-7天）
- P5 投稿前自审 + 投递（2-3天）

## 关键文件位置
- Obsidian KB: D:/learnevery/Research/synapse-repositioning/
- 计划文件: .../docs/superpowers/plans/2026-07-08-synapse-repositioning.md
- foundation 5 文件: .../Writing/foundation/{00_scope,01_research_canon,02_evidence_table,03_argument_map,04_section_contracts}.md
- Zotero collection: SYNAPSE-Repositioning (CPWA24ZF)，含 10 篇撞车论文

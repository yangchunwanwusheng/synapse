# SYNAPSE 状态快照（2026-07-08）

## 当前阶段
P0 仓库迁移进行中。idea 再定位已完成，新 framing = 记忆即边信息。

## 代码现状
- 2353 行，5 模块，60 真实实验（runs/）
- M1–M11 基本满足，仅演示视频待录
- LLM 后端：Paratera API Qwen3-30B-A3B-Instruct-2507 temp=0

## 仓库迁移目标（P0）
- 旧 origin: yangchunwanwu/synapse.git（自建，弃用）
- 新 fork: yangchunwanwu/yzmxdzntxzddkxtxztcdygxjyjz.git（fork 自 liuruifei，日常 push）
- 主仓库: liuruifei/yzmxdzntxzddkxtxztcdygxjyjz.git（队伍提交地址，提 MR 目标）
- 认证：gitlink token 已存 .env（GITLINK_TOKEN），用 URL 嵌入方式 push
- 分支：统一用 master（适配 gitlink 默认）
- 持续更新：每 Task push fork + 每阶段提 MR 到主仓库

## 顶会 framing
- 主线 D：记忆 = Wyner-Ziv 解码端边信息 B̂
- 次贡献 C：通信成本 = 漂移传感器
- 系统验证：openEuler 原型
- 独占点（待 P1 grep 验证）：①黑盒 API 可行 ②统一边信息视角 ③通信成本反向作漂移传感器

## 待办路线图
- P0 仓库迁移 + MR 工作流（进行中）
- P1 撞车复审 + 独占点 grep 验证（2天）
- P2 证据补强：真实任务机制外推 + vs LatentMAS 公平对比（7-10天）
- P3 比赛交付收尾：演示视频 + openEuler 实测 + 可选系统加分项（2-3天）
- P4 论文起草（nature-writing，5-7天）
- P5 投稿前自审 + 投递（2-3天）

## 关键文件位置
- Obsidian KB: D:/learnevery/Research/synapse-repositioning/
- 计划文件: .../docs/superpowers/plans/2026-07-08-synapse-repositioning.md
- foundation 5 文件: .../Writing/foundation/{00_scope,01_research_canon,02_evidence_table,03_argument_map,04_section_contracts}.md
- Zotero collection: SYNAPSE-Repositioning (CPWA24ZF)，含 10 篇撞车论文

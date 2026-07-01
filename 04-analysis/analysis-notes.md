# Analysis Notes — SYNAPSE (S4 过程档案)

> 探索性分析、被否决的解读、聚合脚本说明、第一轮攻击全文。交付物见 `analysis-report.md`。

## 聚合脚本说明
- `scripts/aggregate_s4.py` 读各 run 的 `result.json`（schema 异构：signal/m7/coqa/hotpot_stats/hotpot_ksweep 各不同），抽头牌指标成 `aggregated/raw_long.csv`(90 行) + `summary.csv`。
- provenance：signal/m7 标 pre-registered（协议 C1/M7 锚定）；coqa/hotpot 标 post-hoc（判据本会话定义）。
- 抽查：coqa F1 0.733/0.748、hotpot k3-single CI[−0.173,−0.054]、bridge k3 73.5%/0.86/−0.054、signal 48.4→37.2 vs 54.7→70.0、m7 52.0/0.8→49.6/1.0 —— 全部对上源 result.json。

## 被否决/修正的解读
- ❌ "丢干扰段 → 免费省 75% token"：N=20 单次假象。N=50 single k=3 配对 ΔF1 −0.12（CI 排除 0）= 显著掉质量。改为"naive 单跳不免费；需 bridge 检索才非劣"。
- ❌ "twohop（嵌入查询扩展）能补桥接"：k=3 召回 0.75 反降，证伪。长正文稀释查询。
- ❌ 把 CoQA/HotpotQA 当 C1 收缩律证据：它们是通信效率/记忆复用（赛题 M3/M6），与 C1（合成任务上每任务跨 agent 字节随经验收缩）不同口径，不能混。

## 第一轮攻击（R1 全文）
- R1-1 完整性：协议 P0 实验 E1(地板)/E2/E4/E6 + 消融 均未跑 → 不在残缺数据上给 C1-C4 "supported"，按缺口如实降档。✓
- R1-2 valid run 集合：排除 N=20 三个 hotpot 单次 run（已被 N=50 推翻），显式写入元信息排除清单。✓
- R1-3 同源：先建 aggregated 再写报告，禁手抄日志数字。✓
- R1-4 post-hoc 识别：CoQA/HotpotQA 判据非协议预注册 → 全程标 post-hoc。✓（R2 复检通过）

## 探索性观察（未进裁决，留作 discussion 素材）
- bridge 各 k 的 ΔF1 持平 ~−0.05（召回 0.86→0.97 仍有 ~0.05 残差缺口）→ 残差或来自"多检索段引入轻微噪声"或 MoE 非确定；k=3 已是省幅最优点。
- signal 收缩曲线噪（真实 LLM 逐跳证据方差），单 seed 下"单调"不可claim，只能claim"前半>后半 + 因果对照"。

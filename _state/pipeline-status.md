# Pipeline Status — SYNAPSE

| Stage | 状态 | 产物 | 更新日期 |
|---|---|---|---|
| S1 调研选题 | backfilled | 01-idea/idea-card.md（蒸馏自 SYNAPSE.tex） | 2026-06-18 |
| S2 实验设计 | done | 02-design/experiment-protocol.md、design-notes.md（用户 06-20 认可+授权真实实验） | 2026-06-20 |
| S3 实现执行 | done | 真实 API：signal(KC-1)+m7+CoQA+HotpotQA(bridge,CI)；`runs/`、`_state/experiment-log.md` | 2026-06-21 |
| S4 结果分析 | done(停点#2) | 04-analysis/analysis-report.md+aggregated/；裁决"现 framing 证据不足"，待用户定框架路线 | 2026-06-21 |
| S5 生图制表 | — | — | — |
| S6 写作排版 | — | — | — |
| S7 润色去AI | — | — | — |
| S8 审稿红队 | — | — | — |
| S9 Rebuttal | — | — | — |
| S10 提交后 | — | — | — |

> 说明：本项目竞赛+投稿双线。S4 已诚实裁决：**以现 idea-card framing（C1 收缩律为头牌"发现" + C2/C3/C4）证据不足**——★核心 C1 仅 partial（单 seed/合成/无 oracle 地板/无漂移）、★核心 C3 未受检、C2/C4/消融未跑；**但已足以支撑改 framing 的"真实数据集通信效率(bridge 省 73.5% 非劣) + 记忆复用(0.92)"系统实证论文**（赛题对齐, CI 背书）。**S4 停点#2：待用户在【路线甲=守 C1 补 evidence 轮】与【路线乙=改 framing 走通信效率实证 + 补第二数据集/严格非劣】间定向**（详见 04-analysis/analysis-report.md 总裁决）。赛题 M1–M11 合规不受此决策影响（仅演示视频待录）。

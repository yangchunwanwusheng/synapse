"""渲染多 Agent 通信拓扑动画帧（演示视频 L3 镜头画中画用）。

4 节点（Planner / Retriever / Executor / Summarizer）按菱形排列。
每轮（round）产 1 帧 PNG；通信边按当轮 tier_residual / tier_embedding / tier_text 着色：
  residual  = 橙（残差档，最高密度）
  embedding = 蓝（embedding+text 档）
  text      = 灰（text 档，冷启动/回退）

用法：
  uv run --extra viz python scripts/render_agent_topology.py \
      --input runs/ab_YYYYmmdd_HHMMSS/result.json \
      --out docs/figs/agent_topology
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# 菱形排列：上左下右（Summarizer 留足下边距，避免标签出框）
NODES = {
    "Planner":    (0.5, 0.82),
    "Retriever":  (0.18, 0.5),
    "Executor":   (0.82, 0.5),
    "Summarizer": (0.5, 0.22),
}
# 三档对应的三条通信边（顺序：planner→retriever→executor→summarizer 的协作流水线）
EDGES = [
    ("Planner", "Retriever", "tier_residual", "#FF8C00"),   # 橙
    ("Retriever", "Executor", "tier_embedding", "#1E90FF"), # 蓝
    ("Executor", "Summarizer", "tier_text", "#808080"),     # 灰
]
# 静态底图边（虚线，永远显示，让观众一眼看出协作流水线方向）
STATIC_EDGES = [
    ("Planner", "Retriever"),
    ("Retriever", "Executor"),
    ("Executor", "Summarizer"),
]


def _latest_run(pattern: str) -> str:
    import glob
    runs = sorted(d for d in glob.glob(os.path.join("runs", pattern)) if os.path.isdir(d))
    if not runs:
        raise SystemExit(f"未找到 runs/{pattern}，请先跑相应命令")
    return runs[-1]


def _extract_traj(data: dict) -> list[dict]:
    """从多种 result.json 结构里抽出 synapse_trajectory（每轮 metrics dict 列表）。

    支持三种格式：
    - ab 命令 stdout 直接 dump（顶层即结果）：data['synapse_trajectory']
    - m7 result.json（含 config 包裹）：data['result']['synapse_trajectory']
    - 其他落盘 result.json（含 config 包裹）：data['result']['synapse_trajectory']
    """
    if "synapse_trajectory" in data:
        return data["synapse_trajectory"]
    result = data.get("result")
    if isinstance(result, dict) and "synapse_trajectory" in result:
        return result["synapse_trajectory"]
    raise SystemExit(
        "result.json 中未找到 synapse_trajectory。"
        "本脚本仅支持 ab / m7 命令的输出（含 synapse_trajectory 字段）。"
    )


def render_frame(round_idx: int, traj_metrics: dict, total_rounds: int, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    tier_r = traj_metrics.get("tier_residual", 0)
    tier_e = traj_metrics.get("tier_embedding", 0)
    tier_t = traj_metrics.get("tier_text", 0)
    msgs = traj_metrics.get("messages", 0)
    # 标题：即使 tier 全 0，也显示 messages（每轮必有消息），保证首帧信息密度
    ax.set_title(
        f"Round {round_idx + 1}/{total_rounds}   |   "
        f"messages={msgs}   residual={tier_r}  embedding={tier_e}  text={tier_t}",
        fontsize=12, fontweight="bold", pad=12,
    )
    # 1) 先画静态底图边（虚线灰），让观众看到协作流水线方向
    for src, dst in STATIC_EDGES:
        x0, y0 = NODES[src]
        x1, y1 = NODES[dst]
        ax.annotate(
            "", xy=(x1, y1), xytext=(x0, y0),
            arrowprops=dict(arrowstyle="-", color="#CCCCCC", lw=1.0,
                            alpha=0.5, linestyle="dashed"),
            zorder=1,
        )
    # 2) 画节点（半径 0.10，标签 fontsize=9 保证 Summarizer 不出框）
    for name, (x, y) in NODES.items():
        circle = plt.Circle((x, y), 0.10, color="#4A90E2", alpha=0.85, zorder=3)
        ax.add_patch(circle)
        ax.text(x, y, name, ha="center", va="center", color="white",
                fontsize=9, fontweight="bold", zorder=4)
    # 3) 画高亮的 tier 通信边（按 tier 计数着色，覆盖底图边）
    for src, dst, tier_key, color in EDGES:
        count = traj_metrics.get(tier_key, 0)
        if count > 0:
            x0, y0 = NODES[src]
            x1, y1 = NODES[dst]
            lw = 2.0 + min(count, 5) * 0.6
            ax.annotate(
                "", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw, alpha=0.85),
                zorder=2,
            )
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2 + 0.04
            ax.text(mx, my, str(count), ha="center", fontsize=9,
                    color=color, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                              edgecolor=color, alpha=0.9),
                    zorder=5)
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None,
                    help="ab/m7 result.json 路径；缺省取 runs/m7_* 最新（含落盘 result.json）")
    ap.add_argument("--out", default=os.path.join("docs", "figs", "agent_topology"))
    args = ap.parse_args()

    if args.input:
        input_path = args.input
    else:
        # 优先 m7（落盘），其次 ab（虽然 ab 不落盘，但有时会手动保存）
        try:
            input_path = os.path.join(_latest_run("m7_*"), "result.json")
        except SystemExit:
            input_path = os.path.join(_latest_run("ab_*"), "result.json")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    traj = _extract_traj(data)
    total = len(traj)
    for i, m in enumerate(traj):
        render_frame(i, m, total, out_dir / f"frame_{i+1:03d}.png")
    print(f"rendered {total} frames to {out_dir}")


if __name__ == "__main__":
    main()

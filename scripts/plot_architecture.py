"""渲染 SYNAPSE 架构图 v2（演示视频 L2 镜头用）。

按说明书 [074][140] 流水线绘制：
  Agent 执行 → Message → CAS 句柄 → ResidualCodec 残差 → Memory → Metrics
4 个 Agent（Planner/Retriever/Executor/Summarizer）菱形排列，
中间是三平面（Protocol / Stateplane / Memory），底部是 Eval，记忆反馈闭环虚线。

用法：
  uv run --extra viz python scripts/plot_architecture.py
输出 docs/figs/architecture_v2.png
"""

from __future__ import annotations

import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402


def main() -> None:
    # 加大画布（宽 15、高 10）+ 加大坐标空间，给文字留足呼吸
    fig, ax = plt.subplots(figsize=(15, 10), dpi=130)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 10)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("SYNAPSE Architecture: Coordination as Compression",
                 fontsize=17, fontweight="bold", pad=16)

    # ─────────── 顶部：4 个 Agent（菱形）───────────
    agents = {
        "Planner":    (7.5, 8.8),
        "Retriever":  (3.5, 7.2),
        "Executor":   (11.5, 7.2),
        "Summarizer": (7.5, 5.6),
    }
    for name, (x, y) in agents.items():
        box = mpatches.FancyBboxPatch(
            (x - 1.1, y - 0.38), 2.2, 0.76,
            boxstyle="round,pad=0.05", facecolor="#4A90E2",
            edgecolor="#2C5F8D", linewidth=1.5,
        )
        ax.add_patch(box)
        ax.text(x, y, name, ha="center", va="center",
                color="white", fontsize=12, fontweight="bold")

    # ─────────── 中部：三平面（Protocol 顶部居中，Stateplane/Memory 底部左右）───────────
    # Protocol 加宽（4.2）放短文字，避免字段列表压框
    planes = [
        ("Protocol Layer\n(CNR handshake, structured Message)",
         (7.5, 4.2), "#FF8C00", 4.4, 1.1),
        ("Stateplane\n(CAS content-addressed handle,\nResidualCodec rate-distortion residual)",
         (3.8, 2.2), "#1E90FF", 3.8, 1.4),
        ("Memory\n(MemoryStore, HybridRetriever,\nToMPredictor, Consolidator)",
         (11.2, 2.2), "#2ECC71", 3.8, 1.4),
    ]
    plane_centers = []
    for label, (x, y), color, w, h in planes:
        box = mpatches.FancyBboxPatch(
            (x - w / 2, y - h / 2), w, h,
            boxstyle="round,pad=0.08", facecolor=color, alpha=0.18,
            edgecolor=color, linewidth=1.8,
        )
        ax.add_patch(box)
        ax.text(x, y, label, ha="center", va="center",
                fontsize=10, color=color, fontweight="bold")
        plane_centers.append((x, y, w, h))

    # ─────────── 底部：Eval（加宽到 4.0，居中 7.5，远离 Stateplane）───────────
    eval_box = mpatches.FancyBboxPatch(
        (5.5, 0.3), 4.0, 0.8,
        boxstyle="round,pad=0.05", facecolor="#9B59B6", alpha=0.9,
        edgecolor="#6C3483", linewidth=1.5,
    )
    ax.add_patch(eval_box)
    ax.text(7.5, 0.7, "Eval  (Metrics: messages, tokens, bytes, hit_rate)",
            ha="center", va="center", color="white",
            fontsize=10.5, fontweight="bold")

    # ─────────── 箭头：Summarizer（流水线终点）→ Protocol ───────────
    sx, sy = agents["Summarizer"]
    px, py, pw, ph = plane_centers[0]
    ax.annotate("", xy=(px, py + ph / 2), xytext=(sx, sy - 0.38),
                arrowprops=dict(arrowstyle="->", color="#444444",
                                lw=1.4, alpha=0.7))
    # Planner 侧也画一条（双向协作）
    sx, sy = agents["Planner"]
    ax.annotate("", xy=(px - 1.0, py + ph / 2), xytext=(sx, sy - 0.38),
                arrowprops=dict(arrowstyle="->", color="#444444",
                                lw=1.4, alpha=0.7))

    # Protocol → Stateplane / Memory（左右分流）
    p_top = plane_centers[0]
    p_bl = plane_centers[1]
    p_br = plane_centers[2]
    ax.annotate("", xy=(p_bl[0] + p_bl[2] / 2, p_bl[1]),
                xytext=(p_top[0] - p_top[2] / 2, p_top[1] - p_top[3] / 2),
                arrowprops=dict(arrowstyle="->", color="#444444", lw=1.2, alpha=0.6))
    ax.annotate("", xy=(p_br[0] - p_br[2] / 2, p_br[1]),
                xytext=(p_top[0] + p_top[2] / 2, p_top[1] - p_top[3] / 2),
                arrowprops=dict(arrowstyle="->", color="#444444", lw=1.2, alpha=0.6))

    # Stateplane / Memory → Eval（向中央 Eval 收口）
    ax.annotate("", xy=(6.5, 1.1),
                xytext=(p_bl[0], p_bl[1] - p_bl[3] / 2),
                arrowprops=dict(arrowstyle="->", color="#444444", lw=1.2, alpha=0.6))
    ax.annotate("", xy=(8.5, 1.1),
                xytext=(p_br[0], p_br[1] - p_br[3] / 2),
                arrowprops=dict(arrowstyle="->", color="#444444", lw=1.2, alpha=0.6))

    # ─────────── 记忆反馈闭环（虚线，从 Memory 回到 Retriever）───────────
    ax.annotate(
        "", xy=(agents["Retriever"][0] - 0.3, agents["Retriever"][1] - 0.38),
        xytext=(p_br[0] - 0.8, p_br[1] + p_br[3] / 2),
        arrowprops=dict(arrowstyle="->", color="#2ECC71", lw=2.0,
                        alpha=0.75, linestyle="dashed",
                        connectionstyle="arc3,rad=-0.35"),
    )
    ax.text(1.0, 4.5, "memory\nfeedback\n(envelope\ngrows)",
            fontsize=9, color="#2ECC71", fontweight="bold", ha="center",
            style="italic")

    # ─────────── Wyner-Ziv framing 副标题（左上角，避开顶部 Agent）───────────
    ax.text(0.3, 9.7,
            "Framing:\nMulti-agent collaboration as\nWyner-Ziv source coding with\ngrowing side information",
            fontsize=9.5, color="#333333", va="top", style="italic",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFF8E1",
                      edgecolor="#FFC107", linewidth=1.0))

    # ─────────── 核心闭环箭头标注（右上角）───────────
    ax.text(14.7, 4.5,
            "Closed loop:\nMemory grows\n-> prediction strengthens\n-> residual shrinks\n-> communication drops",
            fontsize=9.5, color="#FF8C00", va="center", ha="right", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#FF8C00", linewidth=1.2))

    out_path = os.path.join("docs", "figs", "architecture_v2.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()

"""渲染三轴定位谱系图（演示视频 L2 镜头用）。

按说明书 §10 三轴定位表（WHAT / WHICH / HOW）+ §10.2 黑盒空白区，
对比 SYNAPSE 与 C2C / LatentMAS / HyLaT 三个白盒方案，
高亮 SYNAPSE 是唯一「需白盒=否 + 需训练=否」的方案。

用法：
  uv run --extra viz python scripts/plot_axis_positioning.py
输出 docs/figs/axis_positioning.png
"""

from __future__ import annotations

import os
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main() -> None:
    # 五列：方案 / WHAT / WHICH / HOW / 需白盒 / 需训练
    headers = ["Approach", "WHAT\n(granularity)", "WHICH\n(alignment)",
               "HOW\n(reconstruct)", "white-box?", "training?"]
    rows = [
        ("C2C",        "KV cache",      "cross-layer",  "nearest lookup",     "YES", "YES"),
        ("LatentMAS",  "hidden state",  "cross-layer",  "nearest lookup",     "YES", "YES"),
        ("HyLaT",      "hidden state",  "same-layer",   "adapter",            "YES", "YES"),
        ("SYNAPSE",    "embedding residual", "none needed", "predictive base + residual", "NO",  "NO"),
    ]

    fig, ax = plt.subplots(figsize=(14, 4.5), dpi=130)
    ax.axis("off")
    ax.set_title("Three-axis Positioning: SYNAPSE occupies the black-box latent gap",
                 fontsize=13, fontweight="bold", pad=12)

    # 画表格
    cell_colors = []
    for row in rows:
        is_synapse = row[0] == "SYNAPSE"
        row_colors = []
        for i, _ in enumerate(row):
            if is_synapse:
                # SYNAPSE 行高亮
                if i == 0:
                    row_colors.append("#FF8C00")  # 方案名深橙
                elif i in (4, 5):  # NO 列
                    row_colors.append("#D4EFDF")  # 浅绿（NO = 优势）
                else:
                    row_colors.append("#FDEBD0")  # 浅橙
            else:
                if i == 0:
                    row_colors.append("#4A90E2")
                elif i in (4, 5):  # YES 列
                    row_colors.append("#FADBD8")  # 浅红（YES = 劣势）
                else:
                    row_colors.append("#EBF5FB")  # 浅蓝
        cell_colors.append(row_colors)

    text_colors = [["white"] * len(headers)] + [
        [("white" if i == 0 else "#333333") for i in range(len(headers))]
        for _ in rows
    ]
    weights = [["bold"] * len(headers)] + [
        ["bold" if (i == 0 or r[0] == "SYNAPSE") else "normal" for i in range(len(headers))]
        for r in rows
    ]

    table = ax.table(
        cellText=[headers] + rows,
        cellColours=[["#34495E"] * len(headers)] + cell_colors,
        cellLoc="center",
        loc="center",
        colWidths=[0.13, 0.17, 0.14, 0.24, 0.11, 0.11],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 2.0)

    # 设置每个单元格的文字颜色和粗细
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell_text = cell.get_text()
            cell_text.set_color("white")
            cell_text.set_weight("bold")
            cell_text.set_fontsize(10.5)
        else:
            cell_text = cell.get_text()
            cell_text.set_color(text_colors[r - 1][c])
            cell_text.set_weight(weights[r - 1][c])
        cell.set_edgecolor("#888888")
        cell.set_linewidth(0.8)

    # 关键论断（底部）
    ax.text(0.5, 0.04,
            "All KV/hidden-state approaches transmit fixed/linear-growth caches;\n"
            "SYNAPSE transmits residuals that contract with collaboration experience.",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=10, color="#FF8C00", style="italic", fontweight="bold")

    out_path = os.path.join("docs", "figs", "axis_positioning.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()

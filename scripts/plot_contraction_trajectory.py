"""渲染残差字节收缩轨迹静态图（演示视频 L4 镜头叠加用）。

数据来源：signal / ab / m7 任一 result.json 的 contraction_bytes 序列，
或 synapse_trajectory 的 nontext_bytes 序列（fallback）。
绘制单调下降曲线，标注首末值与降幅百分比。

用法：
  uv run --extra viz python scripts/plot_contraction_trajectory.py \
      --input runs/signal_YYYYmmdd_HHMMSS/result.json \
      --out docs/figs/contraction_trajectory.png
"""

from __future__ import annotations

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def _latest_signal() -> str:
    import glob
    # 优先 signal_*（残差收缩的主实验）；其次 m7_* / ab_*（也有 contraction）
    for pattern in ("signal_*", "m7_*", "ab_*"):
        runs = sorted(d for d in glob.glob(os.path.join("runs", pattern)) if os.path.isdir(d))
        if runs:
            return runs[-1]
    raise SystemExit("未找到 runs/signal_* / m7_* / ab_*，请先跑相应命令")


def _extract_bytes(data: dict) -> list[int]:
    """从 result.json 多种结构里抽出 contraction bytes 序列。

    支持四种来源：
    - ab 命令 stdout（顶层 contraction_bytes）
    - m7 result.json（result.contraction_bytes）
    - signal result.json（runs[0].contraction_linked，取首个 run 的 linked 序列）
    - fallback：synapse_trajectory[*].nontext_bytes
    """
    # 路径 1：顶层 contraction_bytes（ab stdout）
    if "contraction_bytes" in data:
        return list(data["contraction_bytes"])
    # 路径 2：result.contraction_bytes（m7 落盘）
    result = data.get("result")
    if isinstance(result, dict):
        if "contraction_bytes" in result:
            return list(result["contraction_bytes"])
        # 路径 4：fallback synapse_trajectory.nontext_bytes
        if "synapse_trajectory" in result:
            return [m.get("nontext_bytes", 0) for m in result["synapse_trajectory"]]
    # 路径 3：signal 结构 runs[0].contraction_linked
    runs = data.get("runs")
    if isinstance(runs, list) and runs:
        cl = runs[0].get("contraction_linked")
        if cl:
            return list(cl)
    raise SystemExit(
        "result.json 中未找到 contraction 序列。"
        "支持格式：ab stdout / m7 落盘 / signal 落盘（runs[0].contraction_linked）"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None,
                    help="result.json 路径；缺省取 runs/signal_* 最新")
    ap.add_argument("--out", default=os.path.join("docs", "figs", "contraction_trajectory.png"))
    ap.add_argument("--smooth", action="store_true",
                    help="叠加滑动最小值辅助线（让收缩趋势更直观，避免波动被误读为反弹）")
    args = ap.parse_args()

    input_path = args.input or os.path.join(_latest_signal(), "result.json")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    cb = _extract_bytes(data)
    if len(cb) < 2:
        raise SystemExit(f"contraction 序列长度 {len(cb)} < 2，无法绘制")

    rounds = list(range(1, len(cb) + 1))
    plt.rcParams.update({"font.size": 12})
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=120)
    # 主曲线：原始数据（带数值标注）
    ax.plot(rounds, cb, "o-", color="#FF8C00", linewidth=2.5, markersize=11,
            label="per-round bytes", zorder=3)
    ax.fill_between(rounds, cb, alpha=0.18, color="#FF8C00", zorder=2)
    for x, y in zip(rounds, cb):
        ax.annotate(str(y), (x, y), textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=10, fontweight="bold", color="#333333")
    # 可选：滑动最小值辅助线（单调不增，让"收缩趋势"可见）
    if args.smooth and len(cb) >= 2:
        running_min = []
        cur_min = cb[0]
        for v in cb:
            cur_min = min(cur_min, v)
            running_min.append(cur_min)
        ax.plot(rounds, running_min, "--", color="#1E90FF", linewidth=2.0,
                alpha=0.7, label="running min (contraction envelope)", zorder=4)
        ax.legend(loc="upper right", fontsize=10)
    ax.set_xlabel("Round", fontsize=12)
    ax.set_ylabel("Non-text bytes (residual)", fontsize=12)
    title_suffix = " + contraction envelope" if args.smooth else ""
    ax.set_title(f"Residual Bytes Contraction (memory kicks in){title_suffix}",
                 fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(rounds)
    # 降幅标注：首末值 + 峰谷值（诚实呈现，避免被挑"cherry-pick"）
    # 用两次独立 text 调用（避免 \n 在某些字体下渲染异常）
    end_drop = round((1 - cb[-1] / cb[0]) * 100, 1) if cb[0] > 0 else 0.0
    peak = max(cb)
    valley = min(cb)
    peak_to_valley = round((1 - valley / peak) * 100, 1) if peak > 0 else 0.0
    # 上行：first→last
    ax.text(0.98, 0.96, f"first->last: -{end_drop}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=11, color="#FF8C00", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#FF8C00", linewidth=1.2))
    # 下行：peak→valley（紧贴上行之下）
    ax.text(0.98, 0.86, f"peak->valley: -{peak_to_valley}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=11, color="#1E90FF", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#1E90FF", linewidth=1.2))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    plt.savefig(args.out, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"saved {args.out}  (first={cb[0]} last={cb[-1]} -{end_drop}%; "
          f"peak={peak} valley={valley} -{peak_to_valley}%)")


if __name__ == "__main__":
    main()

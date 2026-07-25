"""OBS 录制时在第二个终端窗口跑，回放 A/B 双模式 ticker（演示视频 L3 镜头底部叠加用）。

读取 ab result.json，逐轮打印：
  round | text_bytes | synapse_bytes | saved_% | hit_rate
每轮间隔 --delay 秒（默认 1.5 秒，对齐 OBS 录制节奏）。

用法：
  uv run python scripts/replay_ab_ticker.py \
      --input runs/ab_YYYYmmdd_HHMMSS/result.json --delay 4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def _latest_ab() -> str:
    import glob
    # ab 命令默认不落盘；优先找 m7（结构相同，落盘），其次手动保存的 ab_*
    for pattern in ("m7_*", "ab_*"):
        runs = sorted(d for d in glob.glob(os.path.join("runs", pattern)) if os.path.isdir(d))
        if runs:
            return runs[-1]
    raise SystemExit("未找到 runs/m7_* 或 runs/ab_*，请先 `uv run synapse m7 --g1 5 --g2 5`")


def _extract_traj_pair(data: dict) -> tuple[list[dict], list[dict]]:
    """从 result.json 抽 (text_trajectory, synapse_trajectory)。

    兼容 ab stdout（顶层）和 m7 落盘（含 result 包裹）两种格式。
    """
    if "text_trajectory" in data and "synapse_trajectory" in data:
        return data["text_trajectory"], data["synapse_trajectory"]
    result = data.get("result")
    if isinstance(result, dict) and "text_trajectory" in result:
        return result["text_trajectory"], result["synapse_trajectory"]
    raise SystemExit("result.json 中未找到 text/synapse trajectory")


def _bytes_of(metrics: dict) -> int:
    """单轮总线字节 = header + text + nontext。"""
    return (
        metrics.get("header_bytes", 0)
        + metrics.get("text_bytes", 0)
        + metrics.get("nontext_bytes", 0)
    )


def _hit_rate(metrics: dict) -> float:
    q = metrics.get("memory_queries", 0)
    h = metrics.get("memory_hits", 0)
    return round(h / q, 3) if q > 0 else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None,
                    help="ab result.json 路径；缺省取 runs/ab_* 最新")
    ap.add_argument("--delay", type=float, default=1.5,
                    help="每轮间隔秒数（OBS 录制节奏，默认 1.5）")
    args = ap.parse_args()

    input_path = args.input or os.path.join(_latest_ab(), "result.json")
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    text_traj, syn_traj = _extract_traj_pair(data)
    n = min(len(text_traj), len(syn_traj))

    # 表头
    print(f"{'round':<7}{'text_bytes':<14}{'synapse_bytes':<16}{'saved_%':<10}{'hit_rate':<10}")
    print("-" * 57)
    sys.stdout.flush()

    for i in range(n):
        tb = _bytes_of(text_traj[i])
        sb = _bytes_of(syn_traj[i])
        saved = round((1 - sb / tb) * 100, 1) if tb > 0 else 0.0
        hit = _hit_rate(syn_traj[i])
        print(f"{i+1:<7}{tb:<14}{sb:<16}{saved:<10}{hit:<10}")
        sys.stdout.flush()
        if i < n - 1:  # 最后一轮不等
            time.sleep(args.delay)

    # 表尾汇总
    print("-" * 57)
    total_text = sum(_bytes_of(t) for t in text_traj)
    total_syn = sum(_bytes_of(s) for s in syn_traj)
    total_saved = round((1 - total_syn / total_text) * 100, 1) if total_text > 0 else 0.0
    print(f"{'TOTAL':<7}{total_text:<14}{total_syn:<16}{total_saved:<10}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

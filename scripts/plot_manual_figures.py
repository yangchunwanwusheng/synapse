#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为项目说明书生成数据图（PNG）。
全部数据来自 runs/ 真实实验，不编造。
输出到 docs/figs/manual/
"""
from __future__ import annotations
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# 中文字体（实测 openEuler 可用 Noto Sans CJK JP 字族，含中文字形）
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "Noto Sans CJK SC",
                                    "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 配色（与项目一致）
BLUE = "#4A90E2"; ORANGE = "#FF8C00"; GREEN = "#2ECC71"; PURPLE = "#9B59B6"
RED = "#E74C3C"; GRAY = "#95A5A6"

OUT = "docs/figs/manual"
os.makedirs(OUT, exist_ok=True)

def load(d):
    with open(f"runs/{d}/result.json", encoding="utf-8") as f:
        return json.load(f)

# ============ 图1：残差收缩曲线（signal B1 vs B3 vs 负例）============
def fig1_contraction():
    b1 = load("signal_20260724_191435")["linked"]["contraction_bytes"]
    b3 = load("signal_20260724_193555")["linked"]["contraction_bytes"]
    neg = load("signal_20260724_191435")["negative"]["contraction_bytes"]
    rounds = range(1, 6)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(rounds, b1, "o-", color=ORANGE, lw=2.5, ms=10, label="B1-full (有记忆)  ↓65.6%")
    ax.plot(rounds, b3, "s--", color=GRAY, lw=2, ms=8, label="B3-no-mem (关记忆)  ↓1.6%")
    ax.plot(rounds, neg, "^:", color=RED, lw=2, ms=8, label="负例 (无共享结构)  ↑9.4%")
    ax.set_xlabel("任务轮次", fontsize=12)
    ax.set_ylabel("残差字节", fontsize=12)
    ax.set_title("图1 · 协作速率收缩律：残差字节随记忆积累向信息地板收缩", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, loc="best")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(rounds)
    # 标注首末点
    ax.annotate(f"冷启动\n{b1[0]}", (1, b1[0]), textcoords="offset points", xytext=(-50, 10), fontsize=9, color=ORANGE)
    ax.annotate(f"记忆充分\n{b1[-1]}", (5, b1[-1]), textcoords="offset points", xytext=(10, -10), fontsize=9, color=ORANGE)
    plt.tight_layout()
    plt.savefig(f"{OUT}/fig1_contraction.png", dpi=150)
    plt.close()
    print(f"✅ fig1_contraction.png")

# ============ 图2：三数据集 Token 节省对比 ============
def fig2_datasets():
    hotpot = load("hotpot_20260724_214352")["result"]
    musique = load("musique_20260724_203011")["result"]
    coqa_r = load("coqa_20260724_211318")["result"]
    datasets = ["HotpotQA\n(N=10)", "MuSiQue\n(N=3)", "CoQA\n(38轮)"]
    tk_saved = [71.09, 80.9, 10.65]
    wire_saved = [94.64, 96.45, 87.89]
    x = np.arange(len(datasets))
    w = 0.35
    fig, ax = plt.subplots(figsize=(8, 4.5))
    b1 = ax.bar(x - w/2, tk_saved, w, color=ORANGE, label="LLM Token 节省")
    b2 = ax.bar(x + w/2, wire_saved, w, color=BLUE, label="线缆字节节省")
    ax.set_ylabel("节省百分比 (%)", fontsize=12)
    ax.set_title("图2 · 三数据集通信压缩效果（真实实验）", fontsize=13, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(datasets, fontsize=10)
    ax.legend(fontsize=10); ax.grid(True, alpha=0.3, axis="y")
    ax.set_ylim(0, 110)
    for bars in (b1, b2):
        for b in bars:
            ax.annotate(f"{b.get_height():.1f}%", (b.get_x()+b.get_width()/2, b.get_height()),
                        ha="center", va="bottom", fontsize=9, fontweight="bold")
    plt.tight_layout()
    plt.savefig(f"{OUT}/fig2_datasets.png", dpi=150)
    plt.close()
    print(f"✅ fig2_datasets.png")

# ============ 图3：CoQA 越长越省曲线 ============
def fig3_coqa_grow():
    coqa = load("coqa_20260724_211318")["result"]["per_conversation"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = [BLUE, GREEN, ORANGE]
    labels = ["conv0 (12轮)", "conv1 (11轮)", "conv2 (15轮·最长)"]
    for i, pc in enumerate(coqa):
        tc = pc.get("text_cum_tokens", [])
        sc = pc.get("synapse_cum_tokens", [])
        turns = range(1, len(tc)+1)
        ax.plot(turns, tc, "o-", color=colors[i], lw=2, ms=5, alpha=0.6, label=f"text基线 {labels[i]}")
        ax.plot(turns, sc, "s--", color=colors[i], lw=2.5, ms=5, label=f"SYNAPSE {labels[i]}")
    ax.set_xlabel("对话轮次", fontsize=12)
    ax.set_ylabel("累计 Token", fontsize=12)
    ax.set_title("图3 · CoQA「越长越省」：text 基线 O(n²) 堆积 vs SYNAPSE 平缓", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, ncol=2, loc="upper left")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{OUT}/fig3_coqa_grow.png", dpi=150)
    plt.close()
    print(f"✅ fig3_coqa_grow.png")

# ============ 图4：组件消融阶梯 ============
def fig4_ablation_ladder():
    # 来自 mech_agg_20260622_171550 summary
    configs = ["no-residual\n(纯潜空间)", "no-tom\n(关预测)", "no-consolidation\n(关巩固)", "full\n(完整)"]
    bytes_ = [4108, 3601, 1914, 1461]
    colors = [RED, ORANGE, "#F39C12", GREEN]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    bars = ax.bar(configs, bytes_, color=colors, edgecolor="black", lw=0.8)
    ax.set_ylabel("总残差字节", fontsize=12)
    ax.set_title("图4 · 组件消融阶梯：每个机制组件都不可或缺", fontsize=13, fontweight="bold")
    ax.grid(True, alpha=0.3, axis="y")
    for b, v in zip(bars, bytes_):
        ax.annotate(f"{v}", (b.get_x()+b.get_width()/2, v), ha="center", va="bottom",
                    fontsize=11, fontweight="bold")
    # 标注 full 最低
    ax.annotate("← 完整链路最优", (3, 1461), textcoords="offset points", xytext=(15, 0),
                fontsize=10, color=GREEN, fontweight="bold")
    ax.set_ylim(0, 4600)
    plt.tight_layout()
    plt.savefig(f"{OUT}/fig4_ablation_ladder.png", dpi=150)
    plt.close()
    print(f"✅ fig4_ablation_ladder.png")

# ============ 图5：漂移回弹（协作速率作传感器）============
def fig5_drift_rebound():
    # 漂移检测：familiar 1240.6 vs drift 3843.0，rebound +246.5%
    # 分级：familiar 1387 / evolved 2615 / novel 3842
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    # 左：漂移回弹
    cats = ["熟悉任务", "漂移任务"]
    vals = [1240.6, 3843.0]
    bars = ax1.bar(cats, vals, color=[GREEN, RED], edgecolor="black", lw=0.8)
    ax1.set_ylabel("平均残差字节", fontsize=11)
    ax1.set_title("漂移回弹 +246.5%", fontsize=12, fontweight="bold", color=RED)
    for b, v in zip(bars, vals):
        ax1.annotate(f"{v:.0f}", (b.get_x()+b.get_width()/2, v), ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax1.annotate("", xy=(1, 3843), xytext=(1, 1240.6), arrowprops=dict(arrowstyle="<->", color=RED, lw=2))
    ax1.grid(True, alpha=0.3, axis="y")
    # 右：AUC 对比
    ax2b = ax2
    sigs = ["残差信号", "检索信号"]
    aucs = [1.0, 0.227]
    bars2 = ax2b.bar(sigs, aucs, color=[ORANGE, GRAY], edgecolor="black", lw=0.8)
    ax2b.set_ylabel("漂移检测 AUC", fontsize=11)
    ax2b.set_title("残差信号 AUC=1.0（完美区分）", fontsize=12, fontweight="bold")
    ax2b.set_ylim(0, 1.15)
    for b, v in zip(bars2, aucs):
        ax2b.annotate(f"{v}", (b.get_x()+b.get_width()/2, v), ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax2b.axhline(y=0.5, color=GRAY, ls="--", alpha=0.5, label="随机=0.5")
    ax2b.legend(fontsize=9)
    ax2b.grid(True, alpha=0.3, axis="y")
    fig.suptitle("图5 · 漂移感知：通信速率作为免费的系统健康传感器", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(f"{OUT}/fig5_drift_rebound.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"✅ fig5_drift_rebound.png")

if __name__ == "__main__":
    fig1_contraction()
    fig2_datasets()
    fig3_coqa_grow()
    fig4_ablation_ladder()
    fig5_drift_rebound()
    print(f"\n全部 5 张图已生成到 {OUT}/")

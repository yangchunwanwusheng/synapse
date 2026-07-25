#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 matplotlib 绘制说明书流程图（mermaid M1-M5 的 PNG 版本）。
不依赖 nodejs/mermaid-cli，纯 matplotlib，中文字体与数据图一致。
输出到 docs/figs/manual/mermaid_M*.png
"""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patches as mpatches

plt.rcParams["font.sans-serif"] = ["Noto Sans CJK JP", "Noto Sans CJK SC",
                                    "WenQuanYi Zen Hei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

BLUE = "#4A90E2"; ORANGE = "#FF8C00"; GREEN = "#2ECC71"; PURPLE = "#9B59B6"
RED = "#E74C3C"; GRAY = "#95A5A6"; YELLOW = "#F39C12"; WHITE = "#FFFFFF"

OUT = "docs/figs/manual"

def box(ax, x, y, w, h, text, fc, tc=WHITE, fs=10, bold=True, rounded=0.15):
    """画一个圆角矩形框（带文字）。"""
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0.02,rounding_size={rounded}",
                       fc=fc, ec="black", lw=1.2)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontsize=fs, color=tc, fontweight="bold" if bold else "normal",
            wrap=True, zorder=5)

def diamond(ax, x, y, w, h, text, fc=YELLOW, tc="black", fs=9):
    """画一个菱形（决策）。"""
    pts = [(x+w/2, y+h), (x+w, y+h/2), (x+w/2, y), (x, y+h/2)]
    poly = plt.Polygon(pts, fc=fc, ec="black", lw=1.2)
    ax.add_patch(poly)
    ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs, color=tc, zorder=5)

def arrow(ax, x1, y1, x2, y2, text="", tc="black", fs=8):
    """画箭头（可带标签）。"""
    a = FancyArrowPatch((x1, y1), (x2, y2),
                        arrowstyle="-|>", mutation_scale=15, lw=1.5, color="#555")
    ax.add_patch(a)
    if text:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my, text, fontsize=fs, color=tc, ha="center", va="bottom",
                bbox=dict(fc="white", ec="none", alpha=0.8, pad=1), zorder=6)

def setup(title, w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100); ax.set_ylim(0, 60)
    ax.axis("off")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    return fig, ax

# ============ M1 · 核心正反馈闭环 ============
def M1():
    fig, ax = setup("图 M1 · 核心正反馈闭环（协作即压缩）", 10, 4)
    # 横向 5 个框 + 回流虚线
    boxes = [
        (2,  25, 16, 12, "① 共享记忆积累\nM↗", GREEN),
        (22, 25, 16, 12, "② 接收端状态预测\nY_pred = f(M)", BLUE),
        (42, 25, 16, 12, "③ 语义残差编码\nZ = Y − Y_pred", ORANGE),
        (62, 25, 16, 12, "④ 通信开销降低\nComm↓", GREEN),
        (82, 25, 16, 12, "⑤ 新经验沉淀\n写入记忆", PURPLE),
    ]
    for x,y,w,h,t,c in boxes:
        box(ax, x, y, w, h, t, c, fs=10)
    # 正向箭头
    for i in range(4):
        x1 = boxes[i][0]+boxes[i][2]; x2 = boxes[i+1][0]
        arrow(ax, x1, 31, x2, 31)
    # 回流虚线 ⑤ → ①
    a = FancyArrowPatch((90, 25), (10, 25), arrowstyle="-|>",
                        connectionstyle="arc3,rad=0.35", mutation_scale=15,
                        lw=1.5, ls="--", color=PURPLE)
    ax.add_patch(a)
    ax.text(50, 10, "跨任务巩固 · 回流共享记忆", ha="center", fontsize=9,
            color=PURPLE, style="italic")
    # 口诀
    ax.text(50, 50, "口诀：Memory↗ → Predict↑ → Residual↓ → Comm↓",
            ha="center", fontsize=11, fontweight="bold", color=ORANGE,
            bbox=dict(fc="#FFF8E1", ec=ORANGE, boxstyle="round,pad=0.4"))
    plt.tight_layout()
    plt.savefig(f"{OUT}/mermaid_M1_feedback.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✅ mermaid_M1_feedback.png")

# ============ M2 · 三档混合协议 ============
def M2():
    fig, ax = setup("图 M2 · 三档混合协议（发送方主动预判选档）", 10, 5.5)
    # 起点
    box(ax, 35, 50, 30, 7, "发送方准备传递非文本状态", GRAY, fs=10)
    # 决策1：有预测基？
    diamond(ax, 38, 36, 24, 10, "有预测基 $\hat{B}$ ?", YELLOW, fs=9)
    arrow(ax, 50, 50, 50, 46)
    # 无 → residual 零基
    box(ax, 2, 36, 28, 10, "residual 档·零基\n编码大残差\n（收缩序列正起点）", ORANGE, fs=9)
    arrow(ax, 38, 41, 30, 41, "无/冷启动", fs=8)
    # 有 → 决策2：相似度
    diamond(ax, 38, 22, 24, 10, "相似度 ≥ 0.97 ?", YELLOW, fs=9)
    arrow(ax, 50, 36, 50, 32, "有", fs=8)
    # 高 → residual
    box(ax, 2, 22, 28, 10, "residual 档\n仅传稀疏残差\n（字节开销最小）", ORANGE, fs=9)
    arrow(ax, 38, 27, 30, 27, "是", fs=8)
    # 低 → embedding
    box(ax, 70, 22, 28, 10, "embedding 档\n传量化向量+摘要\n（仍结构化）", BLUE, fs=9)
    arrow(ax, 62, 27, 70, 27, "否", fs=8)
    # 汇聚到 发送
    box(ax, 38, 6, 24, 10, "发送句柄+残差\n接收方 verify", PURPLE, fs=9)
    for x in [16, 84]:
        arrow(ax, x, 22, 50, 16)
    arrow(ax, 50, 22, 50, 16)
    # 校验失败 → text 回退（标注）
    ax.text(50, 2, "校验失败 → text 档回退全量文本", ha="center", fontsize=8,
            color=RED, style="italic",
            bbox=dict(fc="#FDEDEC", ec=RED, boxstyle="round,pad=0.3"))
    plt.tight_layout()
    plt.savefig(f"{OUT}/mermaid_M2_protocol.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✅ mermaid_M2_protocol.png")

# ============ M3 · Wyner-Ziv 编码示意 ============
def M3():
    fig, ax = setup("图 M3 · 带增长边信息的 Wyner-Ziv 编码", 10, 5)
    # 三列：发送端 / 共享记忆 / 接收端
    ax.text(15, 55, "发送端", ha="center", fontsize=11, fontweight="bold", color=ORANGE)
    ax.text(50, 55, "共享记忆边信息", ha="center", fontsize=11, fontweight="bold", color=GREEN)
    ax.text(85, 55, "接收端", ha="center", fontsize=11, fontweight="bold", color=BLUE)
    # 发送端
    box(ax, 5, 38, 20, 10, "目标状态\nY", ORANGE, fs=11)
    # 共享记忆增长链
    box(ax, 40, 44, 20, 6, "$M_1$", GREEN, fs=9)
    box(ax, 40, 36, 20, 6, "$M_2$", GREEN, fs=9)
    box(ax, 40, 28, 20, 6, "$M_3$ ...", GREEN, fs=9)
    arrow(ax, 50, 44, 50, 42.5)
    arrow(ax, 50, 36, 50, 34.5)
    ax.text(62, 38, "边信息\n持续增长", fontsize=8, color=GREEN, style="italic", va="center")
    # 接收端：预测器
    box(ax, 75, 38, 20, 10, "预测器 ToM\nY_pred = f(M)", BLUE, fs=10)
    # 残差（中间）
    box(ax, 38, 16, 24, 8, "惊讶残差\nZ = Y − Y_pred\n（仅传残差）", RED, fs=9)
    # 箭头：Y→Z, M→预测器, 预测器→Z, Z→接收端
    arrow(ax, 15, 38, 40, 20, "计算残差", fs=8)
    arrow(ax, 60, 32, 75, 40, "驱动预测", fs=8)
    arrow(ax, 75, 38, 62, 22, "预测基 $\hat{Y}$", fs=8)
    arrow(ax, 62, 18, 75, 16, "传输", fs=8)
    # 接收：恢复
    box(ax, 75, 8, 20, 8, "恢复状态", PURPLE, fs=10)
    arrow(ax, 85, 38, 85, 16)
    # 公式标注
    ax.text(50, 4, "$R = H(Y|\hat{B}_j) = H(Y|B_j) + \Delta$,  $\Delta = I(Y;B_j|\hat{B}_j) \geq 0$",
            ha="center", fontsize=10, color="black", style="italic",
            bbox=dict(fc="#FFFDE7", ec=YELLOW, boxstyle="round,pad=0.4"))
    plt.tight_layout()
    plt.savefig(f"{OUT}/mermaid_M3_wynerziv.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✅ mermaid_M3_wynerziv.png")

# ============ M4 · 五模块架构 ============
def M4():
    fig, ax = setup("图 M4 · 五模块系统架构（数据流 ↓ 记忆反哺 ↑）", 11, 5.5)
    # 五个模块框，按架构层次
    # ① runtime
    box(ax, 5, 44, 90, 10, "① 多Agent运行时 runtime/   ·   Planner → Retriever → Executor(CodeAct) → Summarizer", BLUE, fs=10)
    # ② protocol
    box(ax, 5, 32, 90, 9, "② 协议解析与调度 protocol/   ·   Message Schema + CNR 能力协商 + Scheduler 路由", PURPLE, fs=10)
    # ③ stateplane  ↔  ④ memory（并排，双向）
    box(ax, 5, 18, 44, 11, "③ 状态交换数据平面 stateplane/\nCAS 内容寻址 · ResidualCodec\n三档协议 · VLC 校验回退", ORANGE, fs=9)
    box(ax, 51, 18, 44, 11, "④ 共享记忆与检索 memory/\nHybridRetriever 三路混合\nToMPredictor · Consolidator", GREEN, fs=9)
    # ⑤ eval
    box(ax, 5, 6, 90, 9, "⑤ 评测与度量 eval/   ·   ABRunner A/B 双模式 + Metrics 多维统计", YELLOW, tc="black", fs=10)
    # 数据流箭头（纵向）
    arrow(ax, 30, 44, 30, 41, "结构化消息", fs=7)
    arrow(ax, 30, 32, 27, 29, "状态引用", fs=7)
    # ③↔④ 双向
    a1 = FancyArrowPatch((49, 26), (51, 26), arrowstyle="<->",
                         mutation_scale=15, lw=1.5, color="#555")
    ax.add_patch(a1)
    ax.text(50, 28.5, "预测基 ↔\n边信息", ha="center", fontsize=7, color="#555")
    # eval 横切
    arrow(ax, 70, 32, 70, 15, "统计", fs=7)
    plt.tight_layout()
    plt.savefig(f"{OUT}/mermaid_M4_architecture.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✅ mermaid_M4_architecture.png")

# ============ M5 · VLC 流程 ============
def M5():
    fig, ax = setup("图 M5 · Verified Lossy Coordination 流程", 10, 4.5)
    # 横向流程
    box(ax, 2, 25, 20, 12, "发送方\n生成预测残差 Z\n压缩传输", ORANGE, fs=9)
    box(ax, 26, 25, 22, 12, "接收方\n共享记忆同一证据\n重嵌入得真值", BLUE, fs=9)
    diamond(ax, 52, 25, 22, 12, "余弦相似度\n$D(Y,\hat{Y})$ < 阈值?", YELLOW, fs=9)
    box(ax, 78, 38, 20, 10, "接受恢复结果\n（✓ 静默损坏率 0）", GREEN, fs=9)
    box(ax, 78, 12, 20, 10, "触发校验回退\n高精度残差/\n全量文本/更新记忆", RED, fs=8)
    # 箭头
    arrow(ax, 22, 31, 26, 31)
    arrow(ax, 48, 31, 52, 31)
    arrow(ax, 74, 33, 78, 41, "是", fs=8, tc=GREEN)
    arrow(ax, 74, 29, 78, 19, "否·偏差", fs=8, tc=RED)
    # 公式/数字标注
    ax.text(50, 10, "实证：有校验 静默损坏 0  vs  无校验基线 16/16 全错",
            ha="center", fontsize=9, color="black", style="italic",
            bbox=dict(fc="#FFFDE7", ec=YELLOW, boxstyle="round,pad=0.4"))
    plt.tight_layout()
    plt.savefig(f"{OUT}/mermaid_M5_vlc.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✅ mermaid_M5_vlc.png")

if __name__ == "__main__":
    import os; os.makedirs(OUT, exist_ok=True)
    M1(); M2(); M3(); M4(); M5()
    print(f"\n全部 5 张流程图已生成到 {OUT}/")

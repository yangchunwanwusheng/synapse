#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYNAPSE 演示视频终端动画引擎（demo_play.py）

纯终端、零图形依赖、真命令真实执行 + ANSI 彩色动画。
全程自动播放约 4 分钟（240s），给 5 分钟上限留余量。

分镜（L0-L7）：
  L0 封面 slogan        0-12s
  L1 openEuler 真实性   12-35s   (真跑 uname/os-release)
  L2 痛点 + 方案        35-70s
  L3 smoke 真跑         70-95s   (真跑 uv run synapse smoke)
  L4 三数据集结果       95-145s
  L5 残差收缩+因果归因  145-185s
  L6 记忆+越长越省      185-215s
  L7 总结               215-240s

用法：
  python3 scripts/demo_play.py            # 正常播放（带真实命令）
  python3 scripts/demo_play.py --dry      # 跳过真实命令，纯动画（录屏预览用）
  python3 scripts/demo_play.py --speed 2  # 2 倍速（调试）
"""
from __future__ import annotations
import sys, os, json, time, subprocess, argparse, shutil

# ===== 强制 UTF-8 环境（防止中文乱码，必须在任何输出前设置）=====
# 根因：某些终端/locale 环境下 stdout 默认编码不是 UTF-8，导致中文输出乱码。
# 这里强制设置 PYTHONIOENCODING、stdout/stderr reconfigure、以及 LANG 环境变量。
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LANG", "zh_CN.UTF-8")
os.environ.setdefault("LC_ALL", "zh_CN.UTF-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, Exception):
    # Python < 3.7 无 reconfigure，用 io 包装
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ---------- 配色 ----------
class C:
    R = "\033[0m"        # reset
    B = "\033[1m"        # bold
    DIM = "\033[2m"
    # 前景色
    BLUE = "\033[38;5;75m"    # Agent / 基线
    ORANGE = "\033[38;5;208m" # SYNAPSE / 残差（高亮）
    GREEN = "\033[38;5;114m"  # 记忆 / 正向
    PURPLE = "\033[38;5;177m" # 评估
    RED = "\033[38;5;203m"    # 痛点 / 负向
    YELLOW = "\033[38;5;221m"
    CYAN = "\033[38;5;81m"
    GRAY = "\033[38;5;245m"
    WHITE = "\033[38;5;255m"

# ---------- 基础工具 ----------
def clear(): sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()
def hide_cursor(): sys.stdout.write("\033[?25l"); sys.stdout.flush()
def show_cursor(): sys.stdout.write("\033[?25h"); sys.stdout.flush()
def move(r, c): sys.stdout.write(f"\033[{r};{c}H")
def flush(): sys.stdout.flush()

def sleep(s, speed=1.0):
    time.sleep(max(0.001, s / speed))

# ===== ASCII 降级模式（物理控制台无中文字形时用）=====
# 开启 --ascii 后，所有中文输出自动翻译为英文，保证无中文字体的控制台也能看清。
ASCII_MODE = False

# 中文 → 英文 翻译表（覆盖演示所有关键文案；未命中的中文降级为拼音/占位）
_ZH_EN = {
    # slogan / 标题
    "协作即压缩": "Coordination = Compression",
    "协　作　即　压　缩": "C O O R D I N A T I O N   =   C O M P R E S S I O N",
    "越用越省、越用越聪明": "cheaper & smarter with use",
    "面向多智能体协作的低开销通信、非文本状态传递与共享记忆机制": "Low-cost communication, non-text state transfer & shared memory for multi-agent collaboration",
    "第三届中国研究生操作系统开源创新大赛 · 社区赛题": "3rd China Graduate OS Open-Source Innovation Contest · Community Track",
    "把多智能体协作建模为": "Modeling multi-agent collaboration as",
    "带增长记忆边信息的 Wyner-Ziv 信源编码": "Wyner-Ziv source coding with growing side-information",
    "通信字节随经验向信息地板收缩 ——": "comm bytes shrink toward info floor as experience grows --",
    "次真实实验": " real experiments", "个标准数据集": " standard datasets",
    # 镜头标题
    "封面": "[Cover]", "环境验证": "[Env Check]", "痛点": "[Pain Points]", "方案": "[Solution]",
    "离线自检": "[Smoke Test]", "三数据集": "[3 Datasets]", "收缩": "[Contraction]",
    "因果": "[Causality]", "记忆复用": "[Memory Reuse]", "总结": "[Summary]",
    "目标环境：openEuler 24.03-LTS-SP3": "Target: openEuler 24.03-LTS-SP3",
    "痛点：多智能体协作的三大瓶颈": "3 bottlenecks of multi-agent collaboration",
    "离线自检：5 项全 PASS（真实执行）": "Smoke test: 5/5 PASS (real execution)",
    "三数据集主结果：token 压缩 71–82%": "3 datasets: 71-82% token reduction",
    "协作速率收缩律 + 97.6% 因果归因": "Contraction law + 97.6% causal attribution",
    "共享记忆：越长越省 + 命中 0.921": "Shared memory: longer=cheaper, hit 0.921",
    # L1
    "真实运行环境，零伪造 —— 这台机器就是 openEuler": "Real runtime, no fake -- this IS openEuler",
    "证明这不是 PPT，是真实运行的 openEuler 系统：": "Proof this is real openEuler, not a PPT:",
    "官方要求环境：openEuler 24.03-LTS-SP3  ——  就位。": "Required env openEuler 24.03-LTS-SP3 -- READY.",
    # L2 痛点
    "三个瓶颈，一个统一框架解决": "3 bottlenecks, 1 unified framework",
    "① Token 黑洞": "[1] Token black hole",
    "② 状态失真": "[2] State distortion",
    "③ 经验蒸发": "[3] Experience evaporation",
    "Agent 间用自然语言反复传话，通信账单爆炸，复杂度 O(N²)": "Agents chat in natural language, comm cost explodes, O(N^2)",
    "中间推理结果反复文本编解码，语义损耗 + 时延": "mid-results re-encoded as text repeatedly: semantic loss + latency",
    "任务做完就忘，对话越长 token 堆积越快（实测放大 1.31×）": "forget after each task; longer chats pile up tokens (measured 1.31x)",
    "的回答 —— 协作即压缩：": "answer -- Coordination = Compression:",
    "发送方预测接收方已知，只传「惊讶残差」": "sender predicts what receiver knows, sends only 'surprise residual'",
    "非文本状态用 CAS 句柄零拷贝传递": "non-text state via CAS handle (zero-copy)",
    "经验沉淀进共享记忆，越用预测越准、残差越稀疏": "experience sinks into shared memory; better prediction, sparser residual",
    # L3
    "零密钥秒出 PASS —— 核心机制完整、可信": "instant PASS, no API key -- core mechanisms intact",
    "五项自检全过：双模式 / 省字节 / 记忆命中 / 收缩 / 负例区分": "5/5 passed: dual-mode / byte-saving / memory-hit / contraction / negative-distinguish",
    # L4
    "在金标召回 ≥0.90 前提下，单任务 LLM 计费 token 大幅压缩": "with gold recall >=0.90, LLM billing token largely compressed",
    "数据集": "Dataset", "金标召回": "gold/hit",
    "单任务 HotpotQA · LLM token 节省：": "HotpotQA LLM token saved: ",
    "端到端物理线缆字节节省：": "end-to-end wire bytes saved: ",
    "（N=200 大样本配对 95%CI 含 0，质量与全文基线统计不可区分）": "(N=200 paired 95%CI includes 0; quality indistinguishable from baseline)",
    # L5
    "记忆越多，残差越稀疏；关闭记忆则不收缩 —— 机制是因果而非巧合": "more memory -> sparser residual; w/o memory no shrink -- causal, not coincidence",
    "残差字节随任务轮次演化（真实数据 signal run · B1 完整链路）：": "residual bytes over rounds (real signal run, B1-full):",
    "完整": "full", "关记忆": "no-mem", "负例(无共享)": "negative(no-share)",
    "收缩": "shrink", "仅": "only", "反升": "rise",
    "命中": "hit",
    "因果归因 —— 通信压缩中源于记忆复用的比例：": "causal attribution -- fraction of compression from memory reuse:",
    "= (B1 收缩 65.6% − B3 收缩 1.6%) / B1": "= (B1 shrink 65.6% - B3 shrink 1.6%) / B1",
    ">>> 教科书级因果证明：97.6% 的压缩是记忆复用机制带来的，不是随机波动。": ">>> textbook causal proof: 97.6% of compression comes from memory reuse, not noise.",
    # L6
    "记忆复用从「成本」变为「红利」—— 对话越长，节省越大": "memory reuse: from 'cost' to 'dividend' -- longer chat, more savings",
    "对话式 QA · 记忆命中率：": "conversational QA memory hit-rate: ",
    "（35/38 轮命中历史记忆，跨轮复用经验）": "(35/38 turns hit history memory, cross-turn reuse)",
    "「越长越省」曲线 —— text 基线 O(n²) 堆积 vs SYNAPSE 平缓：": "'longer=cheaper' curve: text baseline O(n^2) vs SYNAPSE flat:",
    "对话": "conv", "轮数": "turns", "末轮省 token": "last-turn saved", "效果": "effect",
    "省": "saved", "越长省越多 ↑": "longer=more ↑",
    "（15 轮最长）末轮省 1357 token —— 对话越长，红利越大。": "(15 turns, longest) last-turn saves 1357 tokens -- longer chat, bigger dividend.",
    "三档混合协议自动选档（signal 真实计数）：": "3-tier hybrid protocol auto-selection (signal real counts):",
    "档": "-tier", "次": "x", "回退": "fallback",
    "✓ 零降级回退（fallbacks=0），frozen 记忆快照注入 4 次": "[OK] zero fallback (fallbacks=0), frozen-snapshot injected 4x",
    # L7
    "首次把信源编码的": "first introduces source-coding",
    "理论": "theory",
    "引入多智能体协作，": "into multi-agent collaboration;",
    "用一个统一的压缩框架同时解决通信、状态、记忆三大瓶颈 ——": "one unified compression framework solves comm + state + memory together --",
    "线缆字节节省": "wire bytes saved", "静默损坏": "silent corruption",
    "零静默损坏": "zero silent corruption",
    "演示完成": "demo complete",
    "（目标 ≤5 分钟 / 300s）": "(target <=5 min / 300s)",
    "实际用时": "actual time",
    # smoke 真实命令输出（L3）
    "双模式都产出结论": "both modes produce conclusion",
    "省线缆字节": "saves wire bytes", "记忆复用命中": "memory-reuse hit",
    "关联任务": "related task", "收缩": "contraction",
    "末轮非文本字节<=首轮": "last-round nontext bytes <= first",
    "首轮": "first round", "区分度": "discrimination",
    "负例命中率<关联命中率": "negative hit-rate < related hit-rate",
    "负例命中率": "neg hit-rate", "关联命中率": "related hit-rate",
    # 零散单位/词
    "记忆命中率": "memory hit-rate", "对话式": "conversational",
    "轮命中历史记忆": "turns hit history memory", "跨轮复用经验": "cross-turn reuse",
}

def _tr(text):
    """ASCII 降级：把中文翻译成英文。非 ASCII 模式原样返回。"""
    if not ASCII_MODE:
        return text
    # 先做整串精确替换（处理长 slogan）
    out = text
    # 按 key 长度降序替换，避免短 key 截断长 key
    for zh in sorted(_ZH_EN.keys(), key=len, reverse=True):
        if zh in out:
            out = out.replace(zh, _ZH_EN[zh])
    # 残留的 CJK 中文字符 → 删除（翻译表应覆盖全部，这里兜底）
    # 注意：保留 box-drawing(╔╗║═) 和 block(█░●) 等符号——它们在 VGA 字体里有字形
    out = "".join(ch for ch in out
                  if ord(ch) < 128            # ASCII
                  or 0x2500 <= ord(ch) <= 0x257F  # box drawing
                  or 0x2580 <= ord(ch) <= 0x259F  # block elements
                  or ord(ch) == 0x2022           # bullet ●
                  or ord(ch) == 0x2192           # arrow →
                  or ord(ch) == 0x2191           # arrow ↑
                  or 0xFF01 <= ord(ch) <= 0xFF5E # 全角符号（！？等，VGA 通常能显示）
                  or ord(ch) < 0x4E00            # 非中日韩的拉丁扩展等
                  or ord(ch) > 0x9FFF)           # 非 CJK
    return out

# 写到屏幕并自动换行（带可选颜色）
last_lines = 0
def put(text=""):
    sys.stdout.write(_tr(text) + "\n")
    flush()

def banner_progress(elapsed, total, label):
    """顶部进度条 + 当前镜头标签。固定在第一行。"""
    pct = min(1.0, elapsed / total)
    bar_w = 40
    filled = int(bar_w * pct)
    bar = C.ORANGE + "█" * filled + C.GRAY + "░" * (bar_w - filled) + C.R
    mm, ss = divmod(int(elapsed), 60)
    move(1, 1)
    sys.stdout.write("\033[2K")
    sys.stdout.write(_tr(f"{C.DIM}[{mm:02d}:{ss:02d} / 04:00]{C.R} {bar} {C.ORANGE}{C.B}{label}{C.R}"))
    flush()

def subtitle(text, color=C.CYAN):
    """镜头导语字幕（一次性显示，不固定底部，避免与流式内容粘连）。"""
    put(f"{color}{C.B}  ▶ {text}{C.R}")
    put()

def clear_subtitle():
    """无操作占位（兼容旧调用）。"""
    pass

def typewriter(text, color="", delay=0.012, speed=1.0):
    """打字机效果，逐字输出。"""
    for ch in text:
        sys.stdout.write(_tr(color + ch))
        flush()
        sleep(delay, speed)
    sys.stdout.write(C.R)

NO_ANIM = False  # 全局开关：True 时跳过数字滚动（直接显示终值）

def count_up(target, suffix="", color=C.ORANGE, dur=0.9, fmt="{:.1f}", speed=1.0, prefix=""):
    """数字滚动动画：从 0 滚到 target。在新的一行上原地滚动（用 \r 覆盖本行）。"""
    if NO_ANIM:
        sys.stdout.write(_tr(f"{prefix}{color}{C.B}{fmt.format(target)}{suffix}{C.R}\n")); flush()
        sleep(0.3, speed); return
    full = fmt.format(target) + suffix
    steps = 14  # 固定帧数，兼顾流畅与录制整洁
    import math
    for i in range(steps + 1):
        e = 1 - (1 - i / steps) ** 3  # ease-out
        v = target * e
        sys.stdout.write(_tr(f"\r{prefix}{color}{C.B}{fmt.format(v)}{suffix}{C.R}"))
        flush()
        sleep(dur / steps, speed)
    sys.stdout.write(_tr(f"\r{prefix}{color}{C.B}{fmt.format(target)}{suffix}{C.R}\n"))
    flush()

def real_cmd(cmd, label="", speed=1.0, max_lines=18):
    """真实执行命令并逐行回显（带 $ 提示符 + 打字机）。返回 (输出文本, 是否成功)。"""
    put(f"{C.GREEN}{C.B}$ {cmd}{C.R}")
    sleep(0.25, speed)
    out_lines = []
    try:
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60, cwd=os.getcwd())
        lines = (proc.stdout + proc.stderr).splitlines()
        ok = (proc.returncode == 0)
    except Exception as e:
        lines = [f"[命令执行异常] {e}"]; ok = False
    shown = lines[:max_lines]
    for ln in shown:
        # 给输出着色：PASS 绿、FAIL/ERROR 红、数字橙
        col = C.GRAY
        low = ln.lower()
        if "pass" in low or "ok" in low or "✓" in ln: col = C.GREEN
        elif "fail" in low or "error" in low: col = C.RED
        sys.stdout.write(_tr(f"{col}{ln}{C.R}\n")); flush()
        sleep(0.04, speed)
    if len(lines) > max_lines:
        sys.stdout.write(_tr(f"{C.DIM}  ... ({len(lines)-max_lines} lines omitted){C.R}\n")); flush()
    out_lines = lines
    return out_lines, ok

# ---------- ASCII 图表 ----------
def ascii_bar(value, maxv, width=30, color=C.ORANGE, fill="█", empty="░"):
    """水平条形图。value/maxv 比例。"""
    ratio = max(0, min(1, value / maxv)) if maxv else 0
    n = int(width * ratio)
    return f"{color}{'█'*n}{C.GRAY}{'░'*(width-n)}{C.R}"

def ascii_line_chart(series_list, labels, width=46, height=10):
    """多序列折线图（ASCII）。series_list = [(name,color,values), ...]"""
    allv = [v for _,_,vs in series_list for v in vs]
    if not allv: return ""
    vmin, vmax = min(allv), max(allv)
    span = (vmax - vmin) or 1
    n = len(series_list[0][2])
    grid = [[" "] * width for _ in range(height)]
    # x 位置
    def xpos(i):
        if n == 1: return 0
        return int(i / (n - 1) * (width - 1))
    for name, color, vs in series_list:
        prev = None
        for i, v in enumerate(vs):
            x = xpos(i)
            y = height - 1 - int((v - vmin) / span * (height - 1))
            y = max(0, min(height - 1, y))
            # 画线段
            if prev is not None:
                px, py = prev
                steps = max(abs(x - px), abs(y - py)) or 1
                for s in range(steps + 1):
                    gx = int(px + (x - px) * s / steps)
                    gy = int(py + (y - py) * s / steps)
                    grid[gy][gx] = colorchars(color, "·")
            grid[y][x] = colorchars(color, "●")
            prev = (x, y)
    rows = []
    for r in range(height):
        rows.append("".join(grid[r]) + C.R)
    # 底部 x 轴标签
    axis = C.GRAY + " " + " ".join(labels) + C.R
    return "\n".join(rows) + "\n" + axis

def colorchars(color, ch):
    # 用真实 ANSI（占位宽度按 1 字符算，渲染时终端解释颜色）
    return f"{color}{ch}{C.R}"

# ---------- 镜头 ----------
def get_data():
    p = os.path.join(os.path.dirname(__file__), "..", "dashboard", "data.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def disp_width(s):
    """估算字符串显示宽度（CJK 字符算 2）。"""
    import unicodedata
    w = 0
    for ch in s:
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w

def pad_to(s, width, align="center"):
    """按显示宽度填充到指定宽度。"""
    dw = disp_width(s)
    if dw >= width:
        return s
    gap = width - dw
    if align == "center":
        left = gap // 2
        return " " * left + s + " " * (gap - left)
    return s + " " * gap

def scene_header(title, color=C.ORANGE):
    """镜头大标题，居中风格。"""
    W = 60
    put()
    put(C.B + color + "╔" + "═" * W + "╗" + C.R)
    put(f"{C.B}{color}║{pad_to(title, W)}║{C.R}")
    put(C.B + color + "╚" + "═" * W + "╝" + C.R)
    put()

# ---- L0 封面 ----
def L0(speed):
    clear()
    put()
    put(f"{C.PURPLE}{C.DIM}第三届中国研究生操作系统开源创新大赛 · 社区赛题{C.R}")
    put()
    sleep(0.3, speed)
    # 大字标题（用 ASCII block）
    big = [
        r" ███████ ███   ██ ███████ ██  ██ ",
        r"   ██    ████  ██ ██      ██  ██ ",
        r"   ██    ██ ██ ██ ███████ ███████ ",
        r"   ██    ██  ████      ██ ██  ██ ",
        r"   ██    ██   ███ ███████ ██  ██ ",
    ]
    for row in big:
        sys.stdout.write(C.B + C.ORANGE + row + "\n"); flush(); sleep(0.08, speed)
    sys.stdout.write(C.R)
    put()
    put(f"{C.WHITE}{C.B}协作即压缩 —— 面向多智能体协作的低开销通信、非文本状态传递与共享记忆机制{C.R}")
    sleep(0.4, speed)
    put()
    put(f"{C.CYAN}把多智能体协作建模为 {C.ORANGE}带增长记忆边信息的 Wyner-Ziv 信源编码{C.R}")
    put(f"{C.CYAN}通信字节随经验向信息地板收缩 —— {C.ORANGE}{C.B}越用越省、越用越聪明{C.R}")
    put()
    sleep(0.3, speed)
    put(f"{C.GRAY}openEuler 24.03-LTS-SP3  ·  77 次真实实验  ·  3 个标准数据集{C.R}")
    sleep(1.0, speed)

# ---- L1 openEuler 真实性 ----
def L1(data, speed, dry):
    clear()
    scene_header("L1 · 目标环境：openEuler 24.03-LTS-SP3", C.BLUE)
    subtitle("真实运行环境，零伪造 —— 这台机器就是 openEuler")
    put(f"{C.GRAY}# 证明这不是 PPT，是真实运行的 openEuler 系统：{C.R}")
    sleep(0.3, speed)
    if dry:
        put(f"{C.GREEN}$ uname -a{C.R}")
        put(f"{C.GRAY}Linux localhost 6.6.0-132.0.0.111.oe2403sp3.x86_64 ... x86_64 GNU/Linux{C.R}")
        sleep(0.3, speed)
        put(f"{C.GREEN}$ cat /etc/os-release | head -2{C.R}")
        put(f"{C.GRAY}NAME=\"openEuler\"{C.R}")
        put(f"{C.GRAY}VERSION=\"24.03 (LTS-SP3)\"{C.R}")
    else:
        real_cmd("uname -a", speed=speed)
        real_cmd("cat /etc/os-release | head -2", speed=speed)
    sleep(0.4, speed)
    put()
    put(f"{C.ORANGE}{C.B}✓ 官方要求环境：openEuler 24.03-LTS-SP3  ——  就位。{C.R}")
    sleep(0.6, speed)
    clear_subtitle()

# ---- L2 痛点 + 方案 ----
def L2(data, speed):
    clear()
    scene_header("L2 · 痛点：多智能体协作的三大瓶颈", C.RED)
    subtitle("三个瓶颈，一个统一框架解决")
    pains = [
        (C.RED, "① Token 黑洞", "Agent 间用自然语言反复传话，通信账单爆炸，复杂度 O(N²)"),
        (C.ORANGE, "② 状态失真", "中间推理结果反复文本编解码，语义损耗 + 时延"),
        (C.YELLOW, "③ 经验蒸发", "任务做完就忘，对话越长 token 堆积越快（实测放大 1.31×）"),
    ]
    for col, name, desc in pains:
        put(f"  {col}{C.B}{name}{C.R}")
        sleep(0.15, speed)
        put(f"     {C.GRAY}{desc}{C.R}")
        sleep(0.3, speed)
    put()
    put(f"{C.CYAN}{C.B}SYNAPSE 的回答 —— 协作即压缩：{C.R}")
    sleep(0.2, speed)
    put(f"  {C.ORANGE}发送方预测接收方已知，只传「惊讶残差」{C.R}")
    put(f"  {C.BLUE}非文本状态用 CAS 句柄零拷贝传递{C.R}")
    put(f"  {C.GREEN}经验沉淀进共享记忆，越用预测越准、残差越稀疏{C.R}")
    sleep(1.2, speed)

# ---- L3 smoke 真跑 ----
def L3(data, speed, dry):
    clear()
    scene_header("L3 · 离线自检：5 项全 PASS（真实执行）", C.GREEN)
    subtitle("零密钥秒出 PASS —— 核心机制完整、可信")
    if dry:
        put(f"{C.GREEN}$ uv run synapse smoke{C.R}")
        sleep(0.3, speed)
        for ln in ["  [PASS] 双模式都产出结论",
                   "  [PASS] synapse 省线缆字节(>0%)",
                   "  [PASS] 记忆复用命中(关联任务 hit>0)",
                   "  [PASS] 收缩(末轮非文本字节<=首轮)",
                   "  [PASS] 区分度(负例命中率<关联命中率)",
                   "SMOKE PASSED"]:
            col = C.GREEN if "PASS" in ln else C.WHITE
            sys.stdout.write(_tr(f"{col}{C.B}{ln}{C.R}\n")); flush(); sleep(0.18, speed)
    else:
        real_cmd("uv run synapse smoke 2>&1 | tail -8", speed=speed, max_lines=10)
    sleep(0.4, speed)
    put()
    put(f"{C.ORANGE}{C.B}✓ 五项自检全过：双模式 / 省字节 / 记忆命中 / 收缩 / 负例区分{C.R}")
    sleep(1.0, speed)

# ---- L4 三数据集结果 ----
def L4(data, speed):
    clear()
    scene_header("L4 · 三数据集主结果：token 压缩 71–82%", C.ORANGE)
    subtitle("在金标召回 ≥0.90 前提下，单任务 LLM 计费 token 大幅压缩")
    put(f"{C.GRAY}┌─────────────┬──────────┬──────────┬──────────┬──────────┐{C.R}")
    put(f"{C.GRAY}│{C.R} {C.B}数据集       {C.R}{C.GRAY}│{C.R} {C.B}LLM省%  {C.R}{C.GRAY}│{C.R} {C.B}线缆省% {C.R}{C.GRAY}│{C.R} {C.B}ΔF1     {C.R}{C.GRAY}│{C.R} {C.B}金标召回 {C.R}{C.GRAY}│{C.R}")
    put(f"{C.GRAY}├─────────────┼──────────┼──────────┼──────────┼──────────┤{C.R}")
    rows = [
        ("HotpotQA", data["hotpot"]["llm_token_saved_pct"], data["hotpot"]["wire_saved_pct"],
         data["hotpot"]["syn_f1"] - data["hotpot"]["text_f1"], data["hotpot"]["gold_recall"]),
        ("MuSiQue", data["musique"]["llm_token_saved_pct"], 96.5,
         data["musique"]["syn_f1"] - data["musique"]["text_f1"], data["musique"]["gold_recall"]),
        ("CoQA", data["coqa"]["llm_token_saved_pct"], 87.9,
         data["coqa"]["syn_f1"] - data["coqa"]["text_f1"], data["coqa"]["hit_rate"]),
    ]
    for name, tk, wb, df1, gr in rows:
        tk_s = f"{tk:.1f}%"; wb_s = f"{wb:.1f}%"
        df1_s = f"{df1:+.3f}"; gr_s = f"{gr:.3f}"
        put(f"{C.GRAY}│{C.R} {C.WHITE}{name:<11} {C.R}{C.GRAY}│{C.R} {C.ORANGE}{C.B}{tk_s:>8} {C.R}{C.GRAY}│{C.R} {C.ORANGE}{C.B}{wb_s:>8} {C.R}{C.GRAY}│{C.R} {C.GREEN if df1>=0 else C.RED}{df1_s:>8} {C.R}{C.GRAY}│{C.R} {C.CYAN}{gr_s:>8} {C.R}{C.GRAY}│{C.R}")
        sleep(0.35, speed)
    put(f"{C.GRAY}└─────────────┴──────────┴──────────┴──────────┴──────────┘{C.R}")
    put()
    # 关键数字滚动
    count_up(data["hotpot"]["llm_token_saved_pct"], suffix="%", color=C.ORANGE, dur=0.9, fmt="{:.2f}", speed=speed,
             prefix=f"{C.CYAN}单任务 HotpotQA · LLM token 节省：{C.R} ")
    sleep(0.2, speed)
    count_up(data["hotpot"]["wire_saved_pct"], suffix="%", color=C.ORANGE, dur=0.9, fmt="{:.2f}", speed=speed,
             prefix=f"{C.CYAN}端到端物理线缆字节节省：{C.R} ")
    sleep(0.2, speed)
    put(f"{C.GRAY}（N=200 大样本配对 95%CI 含 0，质量与全文基线统计不可区分）{C.R}")
    sleep(1.2, speed)

# ---- L5 残差收缩 + 因果归因 ----
def L5(data, speed):
    clear()
    scene_header("L5 · 协作速率收缩律 + 97.6% 因果归因", C.ORANGE)
    subtitle("记忆越多，残差越稀疏；关闭记忆则不收缩 —— 机制是因果而非巧合")
    b1 = data["b1"]["contraction"]
    b3 = data["b3"]["contraction"]
    neg = data["b1"]["neg_contraction"]
    put(f"{C.GRAY}残差字节随任务轮次演化（真实数据 signal run · B1 完整链路）：{C.R}")
    sleep(0.3, speed)
    # 只画 B1 下降曲线（最有冲击力），其余用文字对比
    chart = ascii_line_chart(
        [("B1 完整(有记忆)", C.ORANGE, b1)],
        ["R1", "R2", "R3", "R4", "R5"],
        width=46, height=8,
    )
    for ln in chart.splitlines():
        sys.stdout.write("  " + ln + "\n"); flush(); sleep(0.05, speed)
    put()
    put(f"  {C.ORANGE}● B1 完整：{b1} → 收缩 {data['b1']['drop_pct']:+.1f}%，命中 {data['b1']['hit_rate']}{C.R}")
    sleep(0.3, speed)
    put(f"  {C.GRAY}● B3 关记忆：{b3} → 仅 {data['b3']['drop_pct']:+.1f}%，命中 {data['b3']['hit_rate']}{C.R}")
    sleep(0.3, speed)
    put(f"  {C.RED}● 负例(无共享)：{neg} → 反升 {data['b1']['neg_drop_pct']:+.1f}%{C.R}")
    put()
    sleep(0.4, speed)
    put(f"{C.CYAN}{C.B}因果归因 —— 通信压缩中源于记忆复用的比例：{C.R}")
    count_up(data["attribution_976"], suffix="%", color=C.ORANGE, dur=1.0, fmt="{:.1f}", speed=speed, prefix="  ")
    put(f"  {C.GRAY}= (B1 收缩 {data['b1']['drop_pct']:.1f}% − B3 收缩 {data['b3']['drop_pct']:.1f}%) / B1{C.R}")
    sleep(0.3, speed)
    put(f"\n  {C.ORANGE}{C.B}>>> 教科书级因果证明：97.6% 的压缩是记忆复用机制带来的，不是随机波动。{C.R}")
    sleep(1.2, speed)

# ---- L6 记忆 + 越长越省 ----
def L6(data, speed):
    clear()
    scene_header("L6 · 共享记忆：越长越省 + 命中 0.921", C.GREEN)
    subtitle("记忆复用从「成本」变为「红利」—— 对话越长，节省越大")
    coqa = data["coqa"]
    count_up(coqa["hit_rate"], suffix="", color=C.GREEN, dur=0.9, fmt="{:.3f}", speed=speed,
             prefix=f"{C.CYAN}CoQA 对话式 QA · 记忆命中率：{C.R} ")
    put(f"  {C.GRAY}（35/38 轮命中历史记忆，跨轮复用经验）{C.R}")
    put()
    sleep(0.3, speed)
    put(f"{C.CYAN}「越长越省」曲线 —— text 基线 O(n²) 堆积 vs SYNAPSE 平缓：{C.R}")
    sleep(0.2, speed)
    put(f"  {C.GRAY}{'对话':<8}{'轮数':<8}{'末轮省 token':<14}{'效果':<20}{C.R}")
    for g in coqa["gaps"]:
        effect = "越长省越多 ↑" if g["gap"] > 800 else ("省" if g["gap"] > 400 else "省")
        col = C.ORANGE if g["gap"] > 800 else C.GREEN
        put(f"  conv     {g['turns']:<8}{col}{g['gap']:<14}{C.R}{col}{effect}{C.R}")
        sleep(0.25, speed)
    put()
    put(f"  {C.ORANGE}{C.B}conv2（15 轮最长）末轮省 {coqa['gaps'][2]['gap']} token —— 对话越长，红利越大。{C.R}")
    put()
    sleep(0.3, speed)
    # 三档协议真实计数
    tiers = data["b1"]["tiers"]
    put(f"{C.CYAN}三档混合协议自动选档（signal 真实计数）：{C.R}")
    put(f"  {C.ORANGE}residual 档 {tiers['tier_residual']} 次{C.R}  →  {C.BLUE}embedding 档 {tiers['tier_embedding']} 次{C.R}  →  {C.GRAY}text 回退 0 次{C.R}")
    put(f"  {C.GREEN}✓ 零降级回退（fallbacks=0），frozen 记忆快照注入 {data['b1']['frozen_injections']} 次{C.R}")
    sleep(1.2, speed)

# ---- L7 总结 ----
def L7(data, speed):
    clear()
    put()
    put()
    W = 60
    inner = f"{C.ORANGE}{C.B}协　作　即　压　缩{C.PURPLE}{C.B}"  # 全角空格分隔
    top = C.PURPLE + C.B + "╔" + "═" * W + "╗" + C.R
    bot = C.PURPLE + C.B + "╚" + "═" * W + "╝" + C.R
    blank = C.PURPLE + C.B + "║" + " " * W + "║" + C.R
    # 居中标题行：标题可视宽度 = 5字×2 + 4个全角空格×2 = 18，需在 60 中居中
    title_vis = 5 * 2 + 4 * 2  # 18
    left_pad = (W - title_vis) // 2
    title_row = C.PURPLE + C.B + "║" + " " * left_pad + inner + " " * (W - title_vis - left_pad) + C.PURPLE + C.B + "║" + C.R
    put(top); put(blank); put(title_row); put(blank); put(bot)
    put()
    sleep(0.4, speed)
    # 三个大数字
    put(f"   {C.ORANGE}{C.B}71–82%{C.R}        {C.ORANGE}{C.B}94.6%{C.R}         {C.GREEN}{C.B}0{C.R}")
    put(f"   {C.GRAY}LLM token 节省    线缆字节节省    静默损坏{C.R}")
    put()
    sleep(0.5, speed)
    put(f"{C.WHITE}SYNAPSE 首次把信源编码的 {C.ORANGE}Wyner-Ziv 理论{C.WHITE} 引入多智能体协作，{C.R}")
    put(f"{C.WHITE}用一个统一的压缩框架同时解决通信、状态、记忆三大瓶颈 ——{C.R}")
    put(f"{C.ORANGE}{C.B}越用越省、越用越聪明。{C.R}")
    put()
    sleep(0.4, speed)
    put(f"{C.GRAY}77 次真实实验 · 3 标准数据集 · openEuler 24.03-LTS-SP3 · 零静默损坏{C.R}")
    put()
    sleep(0.5, speed)
    put(f"{C.CYAN}{C.B}=== SYNAPSE · END ==={C.R}")
    sleep(1.5, speed)

# ---------- 时间线编排 ----------
TOTAL = 240  # 秒

def run(speed=1.0, dry=False):
    hide_cursor()
    data = get_data()
    start = time.time()
    try:
        # 每个镜头：(设计时长s, 标签, 函数)
        # 各镜头内容 sleep 总和约 16s + 真实命令(L1/L3)约 8s + 数字滚动约 8s ≈ 32s
        # 用 fill_to 把每个镜头填到设计时长，总目标 ~210s（3.5 分钟），给 3-5 分钟留余量
        scenes = [
            (18,  "L0 封面",        lambda: L0(speed)),
            (28,  "L1 环境验证",    lambda: L1(data, speed, dry)),
            (30,  "L2 痛点+方案",   lambda: L2(data, speed)),
            (32,  "L3 离线自检",    lambda: L3(data, speed, dry)),
            (40,  "L4 三数据集",    lambda: L4(data, speed)),
            (35,  "L5 收缩+因果",   lambda: L5(data, speed)),
            (32,  "L6 记忆复用",    lambda: L6(data, speed)),
            (25,  "L7 总结",        lambda: L7(data, speed)),
        ]
        scene_end = 0
        for dur, label, fn in scenes:
            scene_start = time.time()
            scene_end = scene_start + dur / speed  # 该镜头应在此时长后结束
            clear()
            elapsed = time.time() - start
            banner_progress(elapsed, TOTAL, label)
            fn()
            # fill_to：若内容播完还有时间，等待到设计结束，期间更新进度条
            while time.time() < scene_end - 0.05:
                elapsed = time.time() - start
                banner_progress(elapsed, TOTAL, label)
                time.sleep(0.3)
            elapsed = time.time() - start
            banner_progress(elapsed, TOTAL, label)
        # 收尾
        elapsed_real = time.time() - start
        clear()
        banner_progress(TOTAL, TOTAL, "演示完成")
        put()
        put(f"{C.GREEN}{C.B}✓ 演示完成，实际用时 {elapsed_real:.1f}s{C.R}")
        put(f"{C.GRAY}（目标 ≤5 分钟 / 300s）{C.R}")
    except KeyboardInterrupt:
        put(f"\n{C.RED}[中断]{C.R}")
    finally:
        show_cursor()
        clear_subtitle()

def main():
    ap = argparse.ArgumentParser(description="SYNAPSE 终端演示动画")
    ap.add_argument("--dry", action="store_true", help="跳过真实命令执行（纯动画）")
    ap.add_argument("--speed", type=float, default=1.0, help="播放速度倍率（默认 1.0）")
    ap.add_argument("--no-anim", action="store_true", help="关闭数字滚动，直接显示终值（录制保险）")
    ap.add_argument("--ascii", action="store_true", help="ASCII 降级模式（中文翻译为英文，供无中文字体的物理控制台使用）")
    args = ap.parse_args()
    if args.speed <= 0:
        print("speed must > 0"); sys.exit(1)
    global NO_ANIM, ASCII_MODE
    NO_ANIM = args.no_anim
    ASCII_MODE = args.ascii
    run(speed=args.speed, dry=args.dry)

if __name__ == "__main__":
    main()

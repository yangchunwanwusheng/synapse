# -*- coding: utf-8 -*-
"""SYNAPSE 作品介绍 PPT 旧强数字物理替换（Issue #1 / V3-01）。

依据：docs/决赛T45总执行方案-v3.md §三 改口表 + docs/claim-evidence.csv 台账。
纪律：不手改二进制——本脚本为 docs/final/ 构建链的一环，声明式替换、
从 master 版本一次性重放（非幂等：重放前须 git checkout master -- 本文件）。

用法：
    cd synapse && git checkout master -- "SYNAPSE作品介绍PPT.pptx" \
        && python -X utf8 docs/final/retarget_pptx_claims.py

依赖：python-pptx（仓库源码目录 `uv sync --extra dev` 即含，
或裸环境 `pip install python-pptx`）。

改动范围（逐条对应台账 claim_id）：
  s6  竞品对比行标签改三类对照（潜空间通信/记忆系统 MemOS）并同步矩阵值与图标
  s8  "执行沙箱"→"受限执行"；多进程/分布式部署形态与 CAS 跨进程层标注（规划）
  s9  无溯源 AUC=0.942/0.812 替换为可溯源口径（残差 1.0 / 检索 0.227，见
      runs/drift_graded_20260622_175400）；"模型漂移降低"→漂移残差信号表述；
      "共享内存驱动"表述统一为"共享状态"（SHM 跨进程为路线项）
  s13 跨进程 CAS 协同标签标注（规划）
  s16 四项点名旧数字替换；MuSiQue ΔF1 与并排 F1 点估计撤下（重评中）；
      脚注补 N=10/N=3 与 wire bytes 口径说明
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "SYNAPSE作品介绍PPT.pptx"

# (slide_no, 段落旧文本, 新文本, 期望命中次数, 台账claim_id)
PARA_REPLACEMENTS = [
    # ── s6 竞品对比：三类对照行标签（含 MemOS 划界）与 SHM 边界 ──
    (6, "KV/隐状态", "潜空间通信（白盒）", 1, "REL-WORK-DEMARCTION"),
    (6, "传统向量压缩", "记忆系统（MemOS）", 1, "REL-WORK-DEMARCTION"),
    (6, "工程上分成 Runtime、Protocol、Stateplane、Memory、Eval 五层，外加 CAS / 共享内存 CAS 保证一致性。",
        "工程上分成 Runtime、Protocol、Stateplane、Memory、Eval 五层，外加进程内 CAS 内容寻址保证一致性（跨进程共享内存为决赛路线项）。",
        1, "TRANSPORT-SHM"),
    (6, "CAS / SharedMemoryCAS", "CAS（进程内）", 1, "TRANSPORT-SHM"),
    # ── s8 系统架构：能力边界如实化 ──────────────────────────────
    (8, "执行沙箱", "受限执行", 1, "CODEACT-EXEC"),
    (8, "共享内存通信", "共享内存通信（规划）", 1, "TRANSPORT-SHM"),
    (8, "跨节点通信（句柄+差异）", "跨节点通信（规划）", 1, "TRANSPORT-SHM"),
    (8, "共享内存通道", "句柄引用通道", 1, "TRANSPORT-SHM"),
    (8, "（跨进程 一致性）", "（跨进程一致性·规划）", 1, "TRANSPORT-SHM"),
    (8, "SharedMemoryCAS", "SharedMemoryCAS（规划）", 1, "TRANSPORT-SHM"),
    # ── s9 自适应协议：口径换可溯源 run，共享内存→共享状态 ────────
    (9, "以共享内存为中枢，预测通信状态并仅交换残差差异，自适应调节通信粒度与频率，实现带宽–精度自平衡。",
        "以共享状态为中枢，预测通信状态并仅交换残差差异，自适应调节通信粒度与频率，实现带宽–精度自平衡。",
        1, "TRANSPORT-SHM"),
    (9, "机制：三层共享内存驱动", "机制：共享状态预测驱动", 1, "TRANSPORT-SHM"),
    (9, "共享内存", "共享状态", 2, "TRANSPORT-SHM"),   # 覆盖"读/写↵共享内存"与"共享内存↵（全局状态）"两处
    (9, "（全局状态）", "（全局）", 1, "TRANSPORT-SHM"),
    (9, "共享内存（全局）", "共享状态（全局）", 1, "TRANSPORT-SHM"),
    (9, "共享内存更新", "共享状态更新", 1, "TRANSPORT-SHM"),
    (9, "2.2 基于共享内存驱动的自适应通信协议", "2.2 基于共享状态驱动的自适应通信协议", 1, "TRANSPORT-SHM"),
    (9, "自适应协议（共享内存驱动）", "自适应协议（机制验证）", 1, "TRANSPORT-SHM"),
    (9, "带宽消耗（MB/轮）", "残差载荷（B/轮）", 1, "RESID-2787-960"),
    (9, "带宽消耗显著下降", "残差载荷显著下降", 1, "RESID-2787-960"),
    (9, "漂移抑制与回弹对比", "漂移信号区分度", 1, "DRIFT-AUC-1"),
    (9, "模型漂移（越低越好）", "残差信号（字节）", 1, "DRIFT-AUC-1"),
    (9, "自适应协议", "残差信号", 2, "DRIFT-AUC-1"),
    (9, "基线协议", "检索相似度", 2, "DRIFT-AUC-1"),
    (9, "AUC=0.942", "AUC=1.0", 1, "DRIFT-AUC-1"),
    (9, "AUC=0.812", "AUC=0.227", 1, "DRIFT-AUC-1"),
    (9, "✓ 模型漂移降低 3.10×", "✓ 漂移残差信号 3.10×", 1, "DRIFT-AUC-1"),
    (9, "✓ ROC-AUC 提升 0.130", "✓ ROC-AUC 1.0 vs 0.227", 1, "DRIFT-AUC-1"),
    # ── s13 共享记忆：跨进程 CAS 协同标注规划（与 s8 口径一致） ────
    (13, "跨进程一致性（CAS 协同）", "跨进程一致性（CAS 协同·规划）", 1, "TRANSPORT-SHM"),
    (13, "共享内存句柄（Handle）", "共享内存句柄（Handle·规划）", 1, "TRANSPORT-SHM"),
    # ── s16 实验结果：四项点名旧强数字物理替换 ────────────────────
    (16, "71.09%", "71.1%", 1, "TOKEN-HOTPOT-71"),
    (16, "94.64%", "94.6%", 1, "WIRE-BYTES-94"),
    (16, "80.90%", "80.9%", 1, "TOKEN-MUSIQUE-80"),
    (16, "96.45%", "96.5%", 1, "WIRE-BYTES-94"),
    (16, "+0.333", "重评中", 1, "QUAL-MUSIQUE-DF1"),
    (16, "0.857", "—", 1, "QUAL-MUSIQUE-DF1"),   # 撤回并排 F1 点估计（0.857−0.524 即被撤下的 +0.333）
    (16, "0.524", "—", 1, "QUAL-MUSIQUE-DF1"),
    (16, "•  Token衡量语义层输出；wire bytes衡量端到端传输开销。",
        "•  Token 衡量语义层输出；wire bytes 为进程内 CAS 逻辑消息口径（HotpotQA N=10 点估计、MuSiQue N=3 探索性）。",
        1, "WIRE-BYTES-94"),
    (16, "•  CoQA的Token节省较低，但传输层仍下降。",
        "•  CoQA 的 Token 节省较低（10.65%），但传输层仍下降 87.89%。", 1, "COQA-TOKEN-10"),
    (16, "在当前实验设置下，质量变化具有任务依赖性；HotpotQA需关注桥接检索匹配。",
        "在当前实验设置下，质量变化具有任务依赖性；MuSiQue 为 N=3 探索性，多参考重评与扩样进行中，Δ 值不具结论性。",
        1, "QUAL-MUSIQUE-DF1"),
]

# s6 矩阵值几何重定位：行标签 → 列头 → 旧值 → 新值（记忆系统行的事实修正：
# MemOS/Mem0 具备记忆管理 → 共享记忆 ×→✓；无残差编码与校验恢复 → 可恢复残差 !→×）
MATRIX_FIXES = [
    {"row": "记忆系统（MemOS）", "col": "共享记忆", "old": "×", "new": "✓"},
    {"row": "记忆系统（MemOS）", "col": "可恢复残差", "old": "!", "new": "×"},
]


def iter_shapes(shapes):
    for shape in shapes:
        if shape.shape_type == 6:  # GROUP
            yield from iter_shapes(shape.shapes)
        else:
            yield shape


def replace_para(tf, old: str, new: str) -> bool:
    """段落级替换：段内多 run 时把整段文本写入首 run、清空其余 run（保首 run 格式）。"""
    for para in tf.paragraphs:
        if not para.runs:
            continue
        full = "".join(r.text for r in para.runs)
        if full == old:
            para.runs[0].text = new
            for r in para.runs[1:]:
                r.text = ""
            return True
    return False


def center_of(shape):
    return (shape.left + shape.width / 2, shape.top + shape.height / 2)


# ── s6 矩阵图标级修正 ─────────────────────────────────────────────
# 每个矩阵格 = 底层 AUTO_SHAPE（椭圆/三角，定颜色）+ 顶层文本字符。段落替换只改了
# 顶层字符；行标签改为"记忆系统（MemOS）"后，底层图标语义也须同步：
#   共享记忆格：红椭圆 → 绿椭圆（MemOS/Mem0 具备记忆管理）
#   可恢复残差格：黄三角(部分) → 红椭圆（无残差编码与校验恢复）
# 实现方式：深拷贝同表内既有模板格的 spPr 整体替换，保持视觉家族一致。


def _replace_sppr(target, tmpl, keep_center: bool):
    """用 tmpl 的 spPr 替换 target 的 spPr；keep_center=True 时保持目标中心对齐。"""
    from copy import deepcopy
    from pptx.oxml.ns import qn as _qn

    el, tel = target._element, tmpl._element
    old_sppr = el.spPr
    new_sppr = deepcopy(tel.spPr)
    old_xfrm = old_sppr.find(_qn("a:xfrm"))
    new_xfrm = new_sppr.find(_qn("a:xfrm"))
    if old_xfrm is not None and new_xfrm is not None:
        if keep_center:
            off, ext = old_xfrm.find(_qn("a:off")), old_xfrm.find(_qn("a:ext"))
            new_off, new_ext = new_xfrm.find(_qn("a:off")), new_xfrm.find(_qn("a:ext"))
            dx = (int(ext.get("cx")) - int(new_ext.get("cx"))) // 2
            dy = (int(ext.get("cy")) - int(new_ext.get("cy"))) // 2
            new_off.set("x", str(int(off.get("x")) + dx))
            new_off.set("y", str(int(off.get("y")) + dy))
        else:
            new_sppr.replace(new_xfrm, deepcopy(old_xfrm))
    el.replace(old_sppr, new_sppr)


def fix_matrix_icons(slide6) -> list[str]:
    from pptx.oxml.ns import qn as _qn

    shapes = list(slide6.shapes)
    by_text = lambda t: next((s for s in shapes if s.has_text_frame and s.text_frame.text == t), None)

    row_mem, row_prompt = by_text("记忆系统（MemOS）"), by_text("Prompt摘要")
    col_black, col_mem, col_res = by_text("黑盒兼容"), by_text("共享记忆"), by_text("可恢复残差")
    if not all([row_mem, row_prompt, col_black, col_mem, col_res]):
        return []
    tol_x, tol_y = 914400 * 0.55, 914400 * 0.35

    def plain_icon_near(cx_in, cy_in):
        for s in shapes:
            if not getattr(s, "has_text_frame", False) or s.text_frame.text.strip():
                continue
            geom = s._element.spPr.find(_qn("a:prstGeom"))
            if geom is None:
                continue
            sx, sy = center_of(s)
            if abs(sx - cx_in) < tol_x and abs(sy - cy_in) < tol_y:
                return s
        return None

    bx, _ = center_of(col_black)
    py = center_of(row_prompt)[1]
    green_tmpl = plain_icon_near(bx, py)                    # Prompt摘要行×黑格 = 绿椭圆模板
    red_tmpl = plain_icon_near(center_of(col_mem)[0], py)   # 同行×共享记忆格 = 红椭圆模板
    my = center_of(row_mem)[1]
    target_green = plain_icon_near(center_of(col_mem)[0], my)   # 记忆系统×共享记忆
    target_red = plain_icon_near(center_of(col_res)[0], my)     # 记忆系统×可恢复残差

    done = []
    if green_tmpl is not None and target_green is not None:
        _replace_sppr(target_green, green_tmpl, keep_center=False)
        done.append("共享记忆×→✓（红椭圆→绿椭圆）")
    if red_tmpl is not None and target_red is not None:
        _replace_sppr(target_red, red_tmpl, keep_center=True)
        done.append("可恢复残差!→×（黄三角→红椭圆）")
    return done


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    prs = Presentation(str(SRC))
    slides = list(prs.slides)
    counters: dict[int, int] = {}
    errors = []

    for si, slide in enumerate(slides, 1):
        todo = {ri: rule for ri, rule in enumerate(PARA_REPLACEMENTS) if rule[0] == si}
        if not todo:
            continue
        for shape in iter_shapes(slide.shapes):
            if not shape.has_text_frame:
                continue
            for ri, (_sn, old, new, expect, cid) in list(todo.items()):
                if replace_para(shape.text_frame, old, new):
                    counters[ri] = counters.get(ri, 0) + 1

    hits = sum(counters.values())
    print(f"段落替换 {hits} 处（{len(counters)} 条规则命中）")
    for ri, rule in enumerate(PARA_REPLACEMENTS):
        got = counters.get(ri, 0)
        if got != rule[3]:
            errors.append(f"s{rule[0]} [{rule[4]}] {rule[1][:24]!r}… 期望 {rule[3]} 处，实际 {got} 处")

    # s6 矩阵值几何修正（行标签替换成功后执行）
    matrix_done, icon_fixes = [], []
    if any(r[0] == 6 and r[2].startswith("记忆系统") and counters.get(i, 0)
           for i, r in enumerate(PARA_REPLACEMENTS)):
        slide6 = slides[5]
        shapes6 = [s for s in iter_shapes(slide6.shapes) if s.has_text_frame]
        for fix in MATRIX_FIXES:
            row_shape = next((s for s in shapes6 if s.text_frame.text == fix["row"]), None)
            col_shape = next((s for s in shapes6 if s.text_frame.text == fix["col"]), None)
            if not row_shape or not col_shape:
                errors.append(f"s6 matrix-locate({fix['row']}×{fix['col']}) 定位失败")
                continue
            rx, ry = center_of(row_shape)
            cx, cy = center_of(col_shape)
            tol_x, tol_y = 914400 * 1.1, 914400 * 0.4
            for s in shapes6:
                if s.text_frame.text != fix["old"]:
                    continue
                sx, sy = center_of(s)
                if abs(sx - cx) < tol_x and abs(sy - ry) < tol_y:
                    s.text_frame.paragraphs[0].runs[0].text = fix["new"]
                    matrix_done.append(fix)
                    break
            else:
                errors.append(f"s6 matrix-value({fix['old']}@{fix['row']}×{fix['col']}) 未找到")
        icon_fixes = fix_matrix_icons(slide6)
        if len(icon_fixes) != len(MATRIX_FIXES):
            errors.append(f"s6 图标级修正仅完成 {len(icon_fixes)}/{len(MATRIX_FIXES)} 处"
                          f"（模板或目标格定位失败）：{icon_fixes}")

    print(f"矩阵值修正 {len(matrix_done)} 处：{[f['row'] + '×' + f['col'] for f in matrix_done]}")
    print(f"图标级修正 {len(icon_fixes)} 处：{icon_fixes}")
    if errors:
        print("!! 未命中/异常：")
        for e in errors:
            print("  " + e)
        return 1

    prs.save(str(SRC))
    print(f"Saved: {SRC}")

    # 自校验：全片扫描禁用旧口径
    prs2 = Presentation(str(SRC))
    banned = ["71.09", "94.64", "80.90", "96.45", "+0.333", "0.857", "0.524",
              "AUC=0.942", "AUC=0.812", "模型漂移降低", "执行沙箱", "KV/隐状态",
              "传统向量压缩", "共享内存驱动", "共享内存更新", "三层共享内存"]
    residual = []
    for si, slide in enumerate(prs2.slides, 1):
        for shape in iter_shapes(slide.shapes):
            if shape.has_text_frame:
                t = shape.text_frame.text
                residual += [f"s{si}:{b}" for b in banned if b in t]
            elif getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    for c in row.cells:
                        residual += [f"s{si}:{b}" for b in banned if b in c.text]
    if residual:
        print("!! 禁用口径残留：", residual)
        return 1
    print("自校验通过：旧口径全片无残留。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

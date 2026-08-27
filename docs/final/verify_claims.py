# -*- coding: utf-8 -*-
"""claim-evidence 台账对账与材料残留终检（Issue #1 / V3-01 验收器）。

两项验收（可执行）：
  1. 三跳可达：docs/claim-evidence.csv 中引用的仓库相对路径（source/test/run）全部存在；
  2. 全文检索无残留：四项点名旧口径（ΔF1+0.333 / MuSiQue 80.90% 强主张 / “统计不可区分”
     / 沙箱安全表述）在对外材料（README + 说明书 + PPT）中无命中。

用法：
    cd synapse && python -X utf8 docs/final/verify_claims.py

依赖：python-docx 与 python-pptx（仓库源码目录 `uv sync --extra dev` 即含，
或裸环境 `pip install python-docx python-pptx`）。

已知边界：文本提取覆盖 docx 段落/表格与 pptx 文本框/表格；不覆盖 PPT 图表
part（chart XML 轴标签/数据标签）、SmartArt、演讲者备注，以及 docx 页眉/
页脚/脚注。已知替换点由 retarget 脚本的「期望命中次数精确匹配」兜底。
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import docx
from pptx import Presentation

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "docs" / "claim-evidence.csv"

# 残留扫描目标 = 评委可见的对外材料（研究性规划文档不在其列）
MATERIALS = {
    "README.md": REPO_ROOT / "README.md",
    "SYNAPSE项目说明书.docx": REPO_ROOT / "SYNAPSE项目说明书.docx",
    "SYNAPSE作品介绍PPT.pptx": REPO_ROOT / "SYNAPSE作品介绍PPT.pptx",
}

# 四项点名 + 台账禁用口径（对外材料不得出现）；含 PPT 旧图无溯源数字与未标规划的措辞
BANNED = ["71.09", "94.64", "80.90", "96.45", "+0.333", "0.857", "0.524", "统计不可区分",
          "零拷贝", "沙箱安全", "执行沙箱", "安全沙箱", "AUC=0.942", "AUC=0.812",
          "模型漂移降低", "共享内存驱动"]


def extract_pptx_text(path: Path) -> str:
    prs = Presentation(str(path))
    parts = []

    def walk(shapes):
        for sh in shapes:
            if sh.shape_type == 6:
                walk(sh.shapes)
                continue
            if sh.has_text_frame:
                parts.append(sh.text_frame.text)
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    parts.extend(c.text for c in row.cells)

    for slide in prs.slides:
        walk(slide.shapes)
    return "\n".join(parts)


def extract_docx_text(path: Path) -> str:
    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts.extend(c.text for c in row.cells)
    return "\n".join(parts)


SRC_DIR = REPO_ROOT / "源代码及readme文档"

# 台账中的材料简称 → 仓库文件（便于人读，校验器负责规范化）
ALIAS = {"说明书": "SYNAPSE项目说明书.docx", "PPT": "SYNAPSE作品介绍PPT.pptx"}


# 无扩展名的合法裸文件名
BARE_FILES = {"Dockerfile", "docker-compose.yml", "uv.lock"}
PATH_TOKEN = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff\-./\\]*[./][A-Za-z0-9_\u4e00-\u9fff\-./\\]*")


def normalize_ref(item: str) -> str | None:
    """把台账引用规范化为仓库相对路径；非路径引用（命令/章节注）返回 None。"""
    item = item.strip()
    # 命令与描述性引用不是路径
    if item.startswith(("uv ", "python ", "powershell", "sh ", "scripts/ 逐命令")):
        return None
    for short, full in ALIAS.items():
        if item.startswith(short):
            item = full + item[len(short):]
    # 剥离「章节」引注与圆括号注
    item = re.sub(r"[「『][^」』]*[」』]", "", item)
    item = re.sub(r"（[^）]*）|\([^)]*\)", "", item)
    item = item.replace("§", " ")
    if item.strip() in BARE_FILES:
        return item.strip()
    m = PATH_TOKEN.search(item)
    if not m:
        return None
    ref = m.group(0).rstrip(".,;:：，；")
    ref = re.sub(r"[\u4e00-\u9fff]+$", "", ref)  # 剥掉粘连的中文连接词（如"README.md与"）
    return ref or None


def ref_exists(item: str) -> bool:
    return (REPO_ROOT / item).exists() or (SRC_DIR / item).exists()


def check_paths() -> tuple[list[str], list[str]]:
    """三跳可达：台账引用的仓库相对路径必须存在。

    runs/ 与 04-analysis/ 为本地全量实验存档（是否入库由 V3-09 另行裁决）；
    克隆环境缺失时降级为警告，不算对账失败，但会在输出中明示。
    """
    errors, warnings = [], []
    runs_available = (REPO_ROOT / "runs").is_dir()
    analysis_available = (REPO_ROOT / "04-analysis").is_dir()

    def archive_missing(ref: str) -> bool:
        """引用指向未入库存档目录（V3-09 待裁决）时降级，两类目录分别判断。"""
        if ref.startswith("runs/"):
            return not runs_available
        if ref.startswith("04-analysis/"):
            return not analysis_available
        return False
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return ["claim-evidence.csv 为空或表头不符"], []
    warned = False
    for r in rows:
        cid = r.get("claim_id", "?")
        for col in ("source_path", "test_path", "run_path"):
            raw = (r.get(col) or "").strip()
            if not raw or raw == "—":
                continue
            for entry in raw.split(";"):
                ref = normalize_ref(entry)
                if ref is None:
                    continue
                if not ref_exists(ref):
                    if archive_missing(ref):
                        if not warned:
                            warnings.append("runs/ 与 04-analysis/ 本地存档未随仓库分发（V3-09 待裁决）："
                                            "run 级溯源需在本地全量存档环境执行，克隆环境跳过该类路径")
                            warned = True
                        continue
                    errors.append(f"[{cid}] {col}: {ref} 不存在")
    return errors, warnings


def check_residual() -> list[str]:
    errors = []
    texts = {
        "README.md": MATERIALS["README.md"].read_text(encoding="utf-8"),
        "SYNAPSE项目说明书.docx": extract_docx_text(MATERIALS["SYNAPSE项目说明书.docx"]),
        "SYNAPSE作品介绍PPT.pptx": extract_pptx_text(MATERIALS["SYNAPSE作品介绍PPT.pptx"]),
    }
    for name, text in texts.items():
        for b in BANNED:
            if b in text:
                idx = text.find(b)
                ctx = text[max(0, idx - 20): idx + 30].replace("\n", " ")
                errors.append(f"[{name}] 残留 {b!r}：…{ctx}…")
    return errors


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    e1, w1 = check_paths()
    e2 = check_residual()
    path_verdict = "通过（全部路径可达）" if not e1 else f"{len(e1)} 处不可达"
    if not e1 and w1:
        path_verdict = "通过（run 级路径降级跳过）"
    print(f"台账三跳对账：{path_verdict}")
    for e in e1:
        print("  " + e)
    for w in w1:
        print(f"  [警告] {w}")
    print(f"材料残留终检：{'通过（四项点名旧口径无残留）' if not e2 else f'{len(e2)} 处残留'}")
    for e in e2:
        print("  " + e)
    if not (e1 or e2):
        print("边界说明：文本提取覆盖 docx 段落/表格与 pptx 文本框/表格，不含图表 part/SmartArt/备注/页眉脚注。")
    return 1 if (e1 or e2) else 0


if __name__ == "__main__":
    sys.exit(main())

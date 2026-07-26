#!/bin/bash
# SYNAPSE 演示视频录制脚本（demo_record.sh）
#
# 用途：在 openEuler 终端一键播放 4 分钟演示动画，配合 OBS 录屏即可生成演示视频。
#
# 用法：
#   bash scripts/demo_record.sh             # 标准播放（真命令 + 动画，约 4 分钟）
#   bash scripts/demo_record.sh --no-anim   # 关闭数字滚动（录制保险，更干净）
#   bash scripts/demo_record.sh --dry       # 跳过真实命令（纯动画，快速预览）
#   bash scripts/demo_record.sh --speed 1.2 # 调整播放速度
#
# 录制流程（用户操作）：
#   1. 打开 openEuler 终端，字体调大（推荐 16-18pt，等宽字体如 DejaVu Sans Mono）
#   2. 开 OBS，新建场景，录制源选「屏幕捕获」或「窗口捕获」（选终端窗口）
#   3. cd ~/synapse && bash scripts/demo_record.sh
#   4. 看到提示后，回到 OBS 点「开始录制」
#   5. 回终端按回车，动画自动播放约 4 分钟，结束后回 OBS 停止录制
#
set -e

# ---------- 路径与依赖 ----------
cd "$(dirname "$0")/.."   # 切到项目根目录 ~/synapse
PROJ_ROOT="$(pwd)"
PLAY_SCRIPT="$PROJ_ROOT/scripts/demo_play.py"
DATA_FILE="$PROJ_ROOT/dashboard/data.json"

# ===== 强制 UTF-8 环境（防止中文乱码，必须在任何输出前设置）=====
# 某些终端/locale 默认非 UTF-8，会导致中文输出乱码。这里强制设为 UTF-8。
export LANG="${LANG:-zh_CN.UTF-8}"
export LC_ALL="${LC_ALL:-zh_CN.UTF-8}"
export PYTHONIOENCODING="utf-8"
# 兜底：若 zh_CN.UTF-8 locale 未安装，回退到 C.UTF-8（任何系统都有）
if ! locale -a 2>/dev/null | grep -qi "^zh_CN\.utf8$\|^zh_CN\.UTF-8$"; then
    export LANG="C.UTF-8"
    export LC_ALL="C.UTF-8"
fi

# 颜色
G="\033[32m"; Y="\033[33m"; C="\033[36m"; R="\033[0m"; B="\033[1m"; RED="\033[31m"

echo -e "${C}${B}╔════════════════════════════════════════════════╗${R}"
echo -e "${C}${B}║   SYNAPSE 演示视频录制脚本                      ║${R}"
echo -e "${C}${B}║   协作即压缩 · 越用越省、越用越聪明              ║${R}"
echo -e "${C}${B}╚════════════════════════════════════════════════╝${R}"
echo

# ---------- 环境自检 ----------
echo -e "${Y}[1/4] 环境自检...${R}"

# 检查 openEuler
if ! grep -q "openEuler" /etc/os-release 2>/dev/null; then
    echo -e "${RED}  ✗ 未检测到 openEuler。本脚本设计在 openEuler 上运行。${R}"
    echo -e "    （若需在其它系统预览，可直接：python3 scripts/demo_play.py --dry）"
    exit 1
fi
OE_VER=$(grep -oP 'VERSION="\K[^"]+' /etc/os-release 2>/dev/null || echo "未知")
echo -e "${G}  ✓ 系统：$(grep -oP 'PRETTY_NAME="\K[^"]+' /etc/os-release)${R}"

# 检查 python3
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}  ✗ 未找到 python3。请安装：dnf install -y python3${R}"
    exit 1
fi
echo -e "${G}  ✓ Python: $(python3 --version 2>&1)${R}"

# 检查 uv（真命令模式需要）
if ! command -v uv >/dev/null 2>&1; then
    if [ -x "$HOME/.local/bin/uv" ]; then
        export PATH="$HOME/.local/bin:$PATH"
    else
        echo -e "${Y}  ⚠ 未找到 uv。真命令模式（L3 smoke）将失败。${R}"
        echo -e "    安装：curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo -e "    或用 --dry 模式跳过真命令：bash scripts/demo_record.sh --dry"
        DRY_FALLBACK=1
    fi
fi
if command -v uv >/dev/null 2>&1 || [ -x "$HOME/.local/bin/uv" ]; then
    echo -e "${G}  ✓ uv: $(uv --version 2>&1 || $HOME/.local/bin/uv --version 2>&1)${R}"
fi

# 检查 data.json
if [ ! -f "$DATA_FILE" ]; then
    echo -e "${Y}  ⚠ 缺少 $DATA_FILE，正在从真实 run 重新生成...${R}"
    python3 scripts/_gen_demo_data.py 2>/dev/null || {
        echo -e "${RED}    ✗ 无法生成数据。请确认 runs/ 下有实验结果。${R}"
        exit 1
    }
    echo -e "${G}  ✓ data.json 已生成${R}"
else
    echo -e "${G}  ✓ 演示数据就绪：dashboard/data.json${R}"
fi

# 检查 play 脚本
if [ ! -f "$PLAY_SCRIPT" ]; then
    echo -e "${RED}  ✗ 缺少 $PLAY_SCRIPT${R}"
    exit 1
fi
echo -e "${G}  ✓ 演示引擎就绪：scripts/demo_play.py${R}"
echo

# ---------- 终端尺寸建议 ----------
echo -e "${Y}[2/4] 终端尺寸检查...${R}"
COLS=$(tput cols 2>/dev/null || echo 80)
LINES=$(tput lines 2>/dev/null || echo 24)
if [ "$COLS" -lt 100 ] || [ "$LINES" -lt 30 ]; then
    echo -e "${Y}  ⚠ 当前终端 ${COLS}x${LINES}，建议至少 100x30（全屏 + 大字体）${R}"
    echo -e "    本演示最宽表格约 90 列（L7 五评分维度表），低于 100 列可能折行。"
    echo -e "    录制效果最佳分辨率：1920x1080，终端全屏，字体 16-18pt 等宽。"
else
    echo -e "${G}  ✓ 终端尺寸 ${COLS}x${LINES}，OK（最宽表格约 90 列，不会折行）${R}"
fi
echo

# ---------- 模式确认 ----------
echo -e "${Y}[3/4] 播放模式确认...${R}"
PASS_ARGS="$@"
if [ "${DRY_FALLBACK:-0}" = "1" ] && [[ "$@" != *"--dry"* ]]; then
    echo -e "${Y}  uv 不可用，自动切到 --dry 模式（跳过真实命令）${R}"
    PASS_ARGS="--dry $@"
fi
echo -e "  附加参数：${C}${PASS_ARGS:-（无，标准模式）}${R}"

# ---------- 中文显示能力检测（物理控制台不支持中文，自动建议 --ascii）----------
TTY_NOW=$(tty 2>/dev/null || echo "")
if echo "$TTY_NOW" | grep -qE "/tty[0-9]"; then
    # 在物理控制台 text-mode tty 上，内核不支持中文显示
    if [[ "$PASS_ARGS" != *"--ascii"* ]]; then
        echo -e "${Y}  ⚠ 检测到物理控制台($TTY_NOW)：text-mode 不支持中文显示（会显示方块）${R}"
        echo -e "${Y}    已自动加 --ascii（中文翻译为英文）。如需中文请改用 SSH 远程客户端录制。${R}"
        PASS_ARGS="$PASS_ARGS --ascii"
    fi
fi
echo

# ---------- 录制提示 + 倒计时 ----------
echo -e "${Y}[4/4] 准备录制...${R}"
echo
echo -e "${B}═══════════════════════════════════════════════════════${R}"
echo -e "${B}  录制步骤：${R}"
echo -e "${B}  1. 现在打开 OBS，选屏幕/窗口捕获源${R}"
echo -e "${B}  2. 在 OBS 点「开始录制」${R}"
echo -e "${B}  3. 回到这里，按 ${G}回车${R}${B} 开始播放（5 秒后自动开始）${R}"
echo -e "${B}  4. 动画约 4 分钟，结束后回 OBS 停止录制${R}"
echo -e "${B}═══════════════════════════════════════════════════════${R}"
echo
echo -e "${C}按回车立即开始，或等待 30 秒自动开始...${R}"

# 读取回车（带超时 30 秒）
read -t 30 -r -p "" || true
echo

# 3-2-1 倒计时（给用户切到 OBS 的时间）
for i in 3 2 1; do
    echo -ne "\r${G}${B}  ${i} 秒后开始...${R}    "
    sleep 1
done
echo -e "\r${G}${B}  开始！${R}          "
echo

# ---------- 播放 ----------
export TERM=xterm-256color
python3 "$PLAY_SCRIPT" $PASS_ARGS

echo
echo -e "${G}${B}✓ 演示播放完成！${R}"
echo -e "${C}  如果 OBS 还在录，现在可以停止录制了。${R}"
echo -e "${C}  视频文件请在 OBS 设置的输出目录查看。${R}"

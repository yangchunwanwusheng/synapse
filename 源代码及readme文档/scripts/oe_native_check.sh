#!/usr/bin/env sh
# SYNAPSE 原生 openEuler 24.03-LTS-SP3 环境自检 + 等价门禁（Issue #149016，M10 红线）。
#
# 用法：
#   sh scripts/oe_native_check.sh                # 环境自检（无 FAIL 时）+ 复用 scripts/ci.sh 的等价门禁
#   sh scripts/oe_native_check.sh --env-only     # 仅环境自检（秒级，不装依赖、不跑门禁）
#   sh scripts/oe_native_check.sh --allow-container
#                                                # 容器内做脚本机制验证：容器形态降为 WARN 但输出
#                                                # 醒目标记 NOT NATIVE EVIDENCE（不构成原生证明）
#
# 退出码：0=无 FAIL（WARN 不阻塞）；1=存在 FAIL 或门禁失败；2=参数错误。
#
# 留档（防 tee 掩盖退出码——POSIX sh 管道退出码取最后一个命令，直接 tee 会把失败吞成成功）：
#   log="oe_native_$(date +%Y%m%d_%H%M%S).log"
#   sh scripts/oe_native_check.sh >"$log" 2>&1
#   rc=$?
#   cat "$log"
#   printf '\nCHECK_EXIT_CODE=%s\n' "$rc" | tee -a "$log"
#   test "$rc" -eq 0
#
# 红线（统筹红线，#149016）：仅容器证据不得写"原生已验证"。默认模式下检出容器环境即 FAIL；
# 虚拟机（KVM/VMware/Hyper-V 等）内原生安装的 openEuler 属原生 OS 轨，不计为容器。

set -u

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
pkg_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)

ENV_ONLY=0
ALLOW_CONTAINER=0
for arg in "$@"; do
  case "$arg" in
    --env-only) ENV_ONLY=1 ;;
    --allow-container) ALLOW_CONTAINER=1 ;;
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf '未知参数: %s（--env-only | --allow-container | --help）\n' "$arg" >&2; exit 2 ;;
  esac
done

PASS=0
WARN=0
FAIL=0
result() { # result <PASS|WARN|FAIL> <项目> <详情>
  case "$1" in
    PASS) PASS=$((PASS + 1)) ;;
    WARN) WARN=$((WARN + 1)) ;;
    FAIL) FAIL=$((FAIL + 1)) ;;
  esac
  printf '[%s] %s: %s\n' "$1" "$2" "$3"
}

printf '== SYNAPSE 原生 openEuler 环境自检（#149016） ==\n'
printf 'date.utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date)"
printf 'uname=%s\n' "$(uname -a 2>/dev/null || echo unknown)"
printf 'pkg.dir=%s\n' "$pkg_dir"
[ "${ALLOW_CONTAINER}" -eq 1 ] && printf '>>> --allow-container 模式：本输出仅为脚本机制验证，NOT NATIVE EVIDENCE <<<\n'

# ---- 1. OS 版本（/etc/os-release）----
if [ -r /etc/os-release ]; then
  # POSIX sh 用 . 不用 source；变量可能缺失，一律 ${VAR:-} 防 set -u 中断
  . /etc/os-release
  os_id=$(printf '%s' "${ID:-}" | tr '[:upper:]' '[:lower:]')
  os_ver="${VERSION_ID:-}"
  os_name="${PRETTY_NAME:-${VERSION:-}}"
  if [ "$os_id" = "openeuler" ] && [ "$os_ver" = "24.03" ]; then
    case "$os_name" in
      *[Ss][Pp]3*) result PASS os "openEuler 24.03（${os_name}）" ;;
      *) result WARN os "openEuler 24.03 但版本串未见 SP3 标识（${os_name}）；精确 SP3 证据要求见 docs/oe-native-verification.md" ;;
    esac
  else
    result FAIL os "非 openEuler 24.03（ID=${ID:-?} VERSION_ID=${VERSION_ID:-?}）"
  fi
else
  result FAIL os "/etc/os-release 不可读"
fi

# ---- 2. 执行形态（容器 ≠ 原生证据；VM ≠ 容器）----
detect_container=unknown
detect_vm=unknown
if command -v systemd-detect-virt >/dev/null 2>&1; then
  if systemd-detect-virt --container >/dev/null 2>&1; then
    detect_container=$(systemd-detect-virt --container 2>/dev/null || echo container)
  else
    detect_container=none
  fi
  if systemd-detect-virt --vm >/dev/null 2>&1; then
    detect_vm=$(systemd-detect-virt --vm 2>/dev/null || echo vm)
  else
    detect_vm=none
  fi
fi
container_hints=""
[ -f /.dockerenv ] && container_hints="${container_hints} /.dockerenv"
[ -f /run/.containerenv ] && container_hints="${container_hints} /run/.containerenv"
cg1=$(tr '\n' ' ' 2>/dev/null < /proc/1/cgroup || true)
pid1=$(ps -p 1 -o comm= 2>/dev/null || true)
is_container=0
case "$detect_container" in
  none) : ;;
  unknown)
    case "$cg1" in *docker*|*containerd*|*kubepods*|*lxc*) is_container=1 ;; esac
    [ -n "$container_hints" ] && is_container=1
    ;;
  *) is_container=1 ;;
esac
form_detail="detect-virt.container=${detect_container} detect-virt.vm=${detect_vm} hints=${container_hints:-none} pid1=${pid1:-?}"
if [ "$is_container" -eq 1 ]; then
  if [ "$ALLOW_CONTAINER" -eq 1 ]; then
    result WARN form "容器环境（${form_detail}）——仅脚本机制验证，NOT NATIVE EVIDENCE"
  else
    result FAIL form "容器环境（${form_detail}）：默认拒绝为原生证据（统筹红线）；如仅需验证脚本机制请加 --allow-container"
  fi
elif [ "$detect_vm" != "none" ] && [ "$detect_vm" != "unknown" ]; then
  result PASS form "虚拟机形态（${detect_vm}；${form_detail}）——VM 内原生安装的 openEuler 属原生 OS 轨"
elif [ "$detect_container" = "unknown" ]; then
  result WARN form "执行形态无法确认（无 systemd-detect-virt 且无容器特征；${form_detail}）；留档须人工补自证字段（见模板）"
else
  result PASS form "未检出容器/虚拟化（${form_detail}）"
fi

# ---- 3. python3 >= 3.11 ----
if command -v python3 >/dev/null 2>&1; then
  pyv=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "")
  py_path=$(command -v python3)
  if [ -n "$pyv" ]; then
    py_major=${pyv%.*}
    py_minor=${pyv#*.}
    if [ "$py_major" -gt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -ge 11 ]; }; then
      result PASS python "python3 ${pyv}（${py_path}）；建议同步设 UV_PYTHON=python3 UV_PYTHON_PREFERENCE=only-system 使门禁用同一解释器"
    else
      result FAIL python "python3 ${pyv} < 3.11（${py_path}）"
    fi
  else
    result FAIL python "python3 存在但版本探测失败"
  fi
else
  result FAIL python "python3 未安装（dnf install -y python3 python3-pip）"
fi

# ---- 4. uv ----
if command -v uv >/dev/null 2>&1; then
  result PASS uv "$(uv --version 2>/dev/null || echo uv)；GitHub CI 验证版本为 0.9.5（setup-uv pin），留档须记录实际版本"
else
  result FAIL uv "uv 未安装（python3 -m pip install --user uv==0.9.5；装后确认 ~/.local/bin 在 PATH）"
fi

# ---- 5. /dev/shm：类型（findmnt → /proc/self/mountinfo 兜底）+ 容量 + 可写实证 ----
shm_type=""
if command -v findmnt >/dev/null 2>&1 && findmnt -n -T /dev/shm >/dev/null 2>&1; then
  shm_type=$(findmnt -n -T /dev/shm -o FSTYPE 2>/dev/null || echo "")
fi
if [ -z "$shm_type" ] && [ -r /proc/self/mountinfo ]; then
  # mountinfo 列：ID parent major:minor root mountpoint options [可选字段...] - fstype source superopts
  # fstype 在可选字段结束标记 "-" 之后（取错列会把 major:minor 当类型，实测踩坑）
  shm_type=$(awk '$5 == "/dev/shm" { for (i = 7; i <= NF; i++) if ($i == "-") { print $(i + 1); exit } }' /proc/self/mountinfo 2>/dev/null || echo "")
fi
if [ -d /dev/shm ] && command -v python3 >/dev/null 2>&1; then
  shm_probe=$(python3 - <<'PYEOF' 2>&1 || true
import os, tempfile

try:
    s = os.statvfs("/dev/shm")
    total_mib = int(s.f_bsize * s.f_blocks / (1024 * 1024))
    with tempfile.NamedTemporaryFile(prefix="oechk", dir="/dev/shm") as f:
        f.write(b"probe")
    print("total_mib=%d writable=1" % total_mib)
except OSError as e:
    print("error=%s" % e)
PYEOF
  )
  case "$shm_probe" in
    error=*)
      result FAIL shm "/dev/shm 不可用（${shm_probe#error=}）"
      ;;
    total_mib=*writable=1)
      shm_mib=${shm_probe#total_mib=}
      shm_mib=${shm_mib% writable=1}
      if [ -n "$shm_type" ] && [ "$shm_type" != "tmpfs" ]; then
        result WARN shm "可写但非 tmpfs（fstype=${shm_type}，${shm_mib}MiB）——多进程共享内存语义不符"
      elif [ "$shm_mib" -lt 64 ]; then
        result WARN shm "tmpfs 仅 ${shm_mib}MiB（<64MiB）——多进程共享内存预留不足"
      elif [ "$shm_mib" -lt 1024 ]; then
        result WARN shm "tmpfs ${shm_mib}MiB：满足当前单进程自检，低于多进程推荐 1GiB（docker-compose 预置 shm_size=1gb）"
      else
        result PASS shm "tmpfs ${shm_mib}MiB（fstype=${shm_type:-unknown}，可写）"
      fi
      ;;
    *)
      result WARN shm "/dev/shm 探测异常（${shm_probe:-空输出}；fstype=${shm_type:-unknown}）"
      ;;
  esac
else
  result FAIL shm "/dev/shm 不存在或 python3 不可用，无法探测"
fi

# ---- 6. RLIMIT 快照（逐项独立探测，unlimited 合法，不支持不炸）----
lim_v=$(ulimit -v 2>/dev/null || echo unsupported)
lim_n=$(ulimit -n 2>/dev/null || echo unsupported)
lim_u=$(ulimit -u 2>/dev/null || echo unsupported)
cg_pids=""
for p in /sys/fs/cgroup/pids.max /sys/fs/cgroup/pids/pids.max; do
  if [ -r "$p" ]; then cg_pids=$(cat "$p"); break; fi
done
nofile_low=0
case "$lim_n" in
  ""|unlimited|unsupported) : ;;
  *[!0-9]*) : ;;
  *) [ "$lim_n" -lt 1024 ] && nofile_low=1 ;;
esac
if [ "$nofile_low" -eq 1 ]; then
  result WARN rlimit "nofile=${lim_n} 低于 1024（多进程/socket 密集场景建议提高：ulimit -n 或 systemd LimitNOFILE）"
else
  result PASS rlimit "as=${lim_v} nofile=${lim_n} nproc=${lim_u} cgroup.pids.max=${cg_pids:-n/a}"
fi

# ---- 7. AF_UNIX 内核支持（bind/listen/connect/accept + 字节往返实证，Python 临时目录自清理）----
if command -v python3 >/dev/null 2>&1; then
  af_probe=$(python3 - <<'PYEOF' 2>&1 || true
import os
import socket
import tempfile

marker = b"synapse-oe-check"
try:
    with tempfile.TemporaryDirectory(prefix="oechk") as d:
        path = os.path.join(d, "s.sock")  # 短前缀：规避 sun_path 长度上限
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            srv.bind(path)
            srv.listen(1)
            cli = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                cli.connect(path)
                conn, _ = srv.accept()
                try:
                    cli.sendall(marker)
                    if conn.recv(len(marker)) != marker:
                        raise OSError("marker mismatch")
                finally:
                    conn.close()
            finally:
                cli.close()
        finally:
            srv.close()
    print("ok")
except OSError as e:
    print("error=%s" % e)
PYEOF
  )
  case "$af_probe" in
    ok) result PASS af_unix "AF_UNIX SOCK_STREAM bind/listen/connect/accept + 字节往返成功" ;;
    error=*) result FAIL af_unix "AF_UNIX 实证失败（${af_probe#error=}）" ;;
    *) result FAIL af_unix "AF_UNIX 探针异常输出（${af_probe:-空}）" ;;
  esac
else
  result FAIL af_unix "python3 不可用，无法实证"
fi

# ---- 8. 包根磁盘余量（按脚本位置解析，不依赖调用者 cwd）----
disk_kb=$(df -Pk "$pkg_dir" 2>/dev/null | awk 'NR == 2 {print $4}')
case "$disk_kb" in
  ""|*[!0-9]*) result WARN disk "磁盘余量探测失败（df -Pk 输出异常）" ;;
  *)
    if [ "$disk_kb" -lt 1048576 ]; then
      result WARN disk "包根剩余 $((disk_kb / 1024))MiB（<1GiB）：uv sync/dev 依赖/dist 构建可能不足"
    else
      result PASS disk "包根剩余 $((disk_kb / 1024))MiB"
    fi
    ;;
esac

# ---- 汇总与门禁 ----
printf '\n== 自检汇总：%d PASS / %d WARN / %d FAIL ==\n' "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf '自检存在 FAIL，跳过门禁（scripts/ci.sh）。退出码 1。\n'
  exit 1
fi
if [ "$ENV_ONLY" -eq 1 ]; then
  printf -- '--env-only：未运行门禁（WARN 不阻塞）。退出码 0。\n'
  exit 0
fi

printf '\n== 门禁：复用 scripts/ci.sh（locked 同步 + ruff + pytest + smoke + build） ==\n'
if sh "$script_dir/ci.sh"; then
  result PASS gate "ci.sh 全链通过"
  printf '== 最终：%d PASS / %d WARN / %d FAIL ==\n' "$PASS" "$WARN" "$FAIL"
  exit 0
else
  gate_rc=$?
  result FAIL gate "ci.sh 退出码 ${gate_rc}"
  printf '== 最终：门禁失败。退出码 1。 ==\n'
  exit 1
fi

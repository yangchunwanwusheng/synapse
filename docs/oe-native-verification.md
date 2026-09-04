# openEuler 24.03-LTS-SP3 原生验证轨（M10 红线，Issue #149016）

> **状态声明（四档纪律）**：本文档交付时（2026-09-04），**原生 openEuler 环境的首轮验证结果尚未取得**。
> 本轨道交付的是：环境自检脚本、原生轨部署说明、用户侧执行核验清单与留档模板。
> 原生执行与证据回填由项目方在真实环境完成（见 §5–§6）。**在原生日志回填前，任何材料不得写"原生
> openEuler 已验证"**——现有全部系统证据为容器轨（Docker Desktop/WSL2 宿主内核，见
> `docs/工程化基线.md` §2）。统筹红线：仅容器证据不得写原生已验证；**最晚 2026-09-28** 须取得首轮
> 原生结果，逾期该 Claim 降档为"容器已验证 + 原生待验证"。

## 1. 环境要求

| 项 | 要求 | 说明 |
|---|---|---|
| 操作系统 | openEuler 24.03-LTS-SP3（原生安装或**完整 VM** 内安装均可；**容器与 WSL2 不算**） | `/etc/os-release` 须含 SP3 标识；完整 VM（KVM/VMware/Hyper-V 等，openEuler 自带内核启动）属原生 OS 轨；**WSL2 共享宿主微软定制内核（microsoft-standard-WSL2），不构成 openEuler 原生内核证据**——自检脚本对此显式 FAIL |
| Python | ≥ 3.11（openEuler 24.03 自带） | 与 CI 矩阵（3.11/3.13）一致；建议 `UV_PYTHON=python3 UV_PYTHON_PREFERENCE=only-system` 锁定系统解释器 |
| uv | GitHub CI 验证版本 **0.9.5** | `python3 -m pip install --user uv==0.9.5`；装后确认 `~/.local/bin` 在 PATH |
| 磁盘 | ≥ 1 GiB 空闲（uv sync/dev 依赖/dist） | aarch64 机器另需编译工具链余量 |
| 网络 | dnf 源 + PyPI 可达 | `uv sync` 需拉包；离线环境另议（超本轨道范围） |

## 2. 原生轨部署（依赖安装）

```bash
# 1) 系统依赖
sudo dnf install -y python3 python3-pip

# 2) uv（固定到 CI 验证版本；--user 装机后确认 PATH 含 ~/.local/bin）
python3 -m pip install --user uv==0.9.5
export PATH="$HOME/.local/bin:$PATH"   # 建议写入 ~/.bashrc

# 3) 环境解释器锁定（防 uv 另拉托管解释器，与自检口径一致）
export UV_PYTHON=python3
export UV_PYTHON_PREFERENCE=only-system

# 4) 进入源码包目录，同步依赖（锁定口径，与 CI/ci.sh 一致）
cd synapse/源代码及readme文档
uv sync --locked --extra dev --no-editable   # 门禁全量口径（dev=pytest+ruff）
# 或最小运行口径：uv sync --locked --no-editable（核心 smolagents，离线 mock）

# 5) 离线自检（零网络/零密钥）
uv run --no-sync synapse smoke
```

## 3. 常见坑（原生轨）

- **SELinux**：enforcing 下非标准路径的 Unix socket 文件可能被拒。处置：优先在 `/tmp` 或用户主目录等标签正常路径创建 socket；用审计日志（`ausearch -m avc`）确认；用 `restorecon` 修复标签。**不要以关闭 SELinux 为解决方案**。
- **`~/.local/bin` 不在 PATH**：`pip --user` 安装 uv 后 `command not found`，见 §2 第 2 步。
- **dnf 源 metalink 间歇失败**：BuildKit 对 openEuler `update` 源偶发协商失败有历史记录（2026-08-31，见工程化基线）；原生环境遇 dnf 报错先重试/换镜像源，勿改 canonical Dockerfile。
- **socket 路径长度上限**：AF_UNIX `sun_path` 约 108 字节上限——深层目录/长中文名路径下创建 socket 可能失败；探针用短前缀临时目录规避。
- **所有权与身份**：先以 root 跑过一次再切普通用户，`.venv/`、`dist/` 属主混杂会引发权限错；统一用同一非 root 用户执行全流程。
- **系统时间不准**：影响日志时间戳追溯与 TLS 握手（uv 拉包失败的一种假象）；先 `timedatectl` 校时。
- **证书/代理/DNS**：`uv sync` 失败先查 `ca-certificates`、`HTTP(S)_PROXY`、DNS。
- **aarch64**：部分依赖可能无预编译 wheel，需 `dnf install -y gcc python3-devel` 后源码构建。
- **在发布镜像内跑全量门禁不可行（设计而非缺陷）**：镜像不 COPY `data/`（数据集样本）也不含 `.git`（code_sha 锚定需要），镜像定位是 smoke 复现；**全量门禁（ci.sh）必须在 git checkout 中执行**（checkout 内 data 样本与 .git 天然在场）。
- **留档脱敏**：日志/截图不得包含 `.env` 内容、API key、内网主机名/IP。

## 4. 环境自检脚本用法

`scripts/oe_native_check.sh`（POSIX sh；退出码 0=无 FAIL，1=有 FAIL 或门禁失败，2=参数错）：

```bash
sh scripts/oe_native_check.sh --env-only          # 仅环境自检（秒级）
sh scripts/oe_native_check.sh                     # 自检（无 FAIL 时）+ ci.sh 等价门禁
sh scripts/oe_native_check.sh --allow-container   # 仅限容器内做脚本机制验证（输出标 NOT NATIVE EVIDENCE）
```

自检项与输出解读：

| 项 | PASS 条件 | WARN/FAIL 含义与处置 |
|---|---|---|
| os | openEuler 24.03 且版本串含 SP3 | WARN=24.03 无 SP3 标识（查 `/etc/os-release`，交付要求精确 SP3）；FAIL=非 openEuler 24.03 |
| form | 未检出容器与 WSL2 内核（完整 VM 属原生 OS 轨） | FAIL=检出容器（`.dockerenv`/cgroup/pid1 特征，默认拒绝为原生证据，仅机制验证用 `--allow-container`）**或检出 WSL2**（uname -r 含 microsoft / detect-virt 报 wsl——共享宿主定制内核，与容器轨同源，不构成原生证据）；WARN=无 systemd-detect-virt 且特征不明，留档须人工补自证 |
| python | python3 ≥ 3.11 | FAIL=<3.11 或探测失败（dnf 装 python3） |
| uv | uv 可用 | FAIL=未安装（§2 第 2 步；注意 PATH） |
| shm | tmpfs ≥ 1 GiB 且可写 | WARN=<64 MiB（多进程共享内存预留不足）或 64MiB–1GiB（满足当前单进程自检、低于多进程推荐；docker-compose 预置 1gb）或非 tmpfs/类型未能确认（两级探测均失败时保守按非 tmpfs）；FAIL=不可用 |
| rlimit | nofile ≥ 1024（as/nproc/pids.max 快照） | WARN=nofile<1024（`ulimit -n` 或 systemd `LimitNOFILE`） |
| af_unix | bind/listen/connect/accept + 字节往返成功 | FAIL=内核或环境不支持（SELinux/路径权限时查 §3） |
| disk | 包根 ≥ 1 GiB | WARN=不足（清理或扩容） |
| gate | ci.sh 全链（locked 同步+ruff+pytest+smoke+build）通过 | FAIL=链上任一步失败，输出定位到具体步 |

## 5. 用户侧执行核验清单

在原生 openEuler 24.03-LTS-SP3 环境（物理机或 VM，非容器）逐项执行并勾选：

- [ ] **0. 自证环境形态**：`cat /etc/os-release`（含 SP3）；`systemd-detect-virt --vm`（或无该命令时记录 `uname -a`、`ps -p 1 -o comm=`、`ls /.dockerenv /run/.containerenv 2>&1`）；确认非容器**且非 WSL2**（`uname -r` 不得含 microsoft——WSL2 共享宿主内核不算原生）。
- [ ] **1. 干净检出**：`git clone`（或 `git status --short` 确认无已跟踪文件改动）；记录 `git rev-parse HEAD` 与分支。
- [ ] **2. 依赖安装**：按 §2 完成；记录 `python3 --version`、`uv --version`。
- [ ] **3. 环境自检**：`--env-only` 模式，0 FAIL；按 §4 处置 WARN。
- [ ] **4. 全量门禁**：完整模式（含 ci.sh：uv sync --locked --extra dev --no-editable → ruff → pytest → smoke → uv build）退出码 0。
- [ ] **5. 留档**：按 §6 模板归档至 `docs/oe-native-evidence-<日期>.md`（日志全文 + 退出码 + 截图[脱敏可选]）。

## 6. 留档模板

复制以下模板创建 `docs/oe-native-evidence-YYYYMMDD.md`（占位 `<>` 处如实填写；**`/etc/os-release` 全文必填**）：

```markdown
# 原生 openEuler 验证留档（#149016）

- 执行日期（本地时区）：<YYYY-MM-DD HH:MM TZ>
- 配置口径：门禁=离线 mock（default.yaml，零密钥零网络）
- 执行人：<姓名/账号>　环境提供方式：<物理机 | KVM/VMware/Hyper-V VM | 其他（说明）>
- 架构：`uname -m` = <x86_64/aarch64>

## 环境自证（必填）
- `/etc/os-release` 全文：
  <完整粘贴——含 ID/VERSION_ID/PRETTY_NAME 的 SP3 标识>
- `uname -a`：<完整输出>
- `systemd-detect-virt --vm` / `--container`：<输出；无该命令则注明，并附 `ps -p 1 -o comm=` 与 `ls /.dockerenv /run/.containerenv` 结果>
- 容器特征核对：/.dockerenv=<存在/不存在>　/run/.containerenv=<存在/不存在>

## 代码身份
- `git rev-parse HEAD`：<SHA>　分支：<名>　`git status --short`：<空=clean；非空须注明 dirty，dirty 不能作为最终提交级证据>

## 工具版本
- `python3 --version`：<>　`python3 -c 'import sys;print(sys.executable)'`：<>
- `uv --version`：<>　UV_PYTHON=<值> UV_PYTHON_PREFERENCE=<值>

## 自检（--env-only）
<完整日志粘贴；末尾含 CHECK_EXIT_CODE=0>

## 全量门禁（含 ci.sh）
<完整日志粘贴；须含 uv sync/ruff/pytest/smoke/build 各段结果；末尾 CHECK_EXIT_CODE=0>

## 佐证（可选，脱敏后）
- 终端截图：<链接/嵌入；不得含密钥/内网信息>
```

留档命令（防 tee 吞退出码——POSIX 管道退出码取末命令）：

```bash
log="oe_native_$(date +%Y%m%d_%H%M%S).log"
sh scripts/oe_native_check.sh >"$log" 2>&1
rc=$?
cat "$log"
printf '\nCHECK_EXIT_CODE=%s\n' "$rc" | tee -a "$log"
test "$rc" -eq 0
```

## 7. 与容器轨的关系

容器轨证据（镜像 digest/构建/运行，见 `docs/工程化基线.md` §2）与原生轨证据**分列不可互替**：容器轨证明"openEuler 24.03-LTS-SP3 用户态可编译运行测试"，原生轨证明"原生内核/系统环境同样成立"。两轨证据齐全后，M10 的 openEuler 可复现声明才完整。

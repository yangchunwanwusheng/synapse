# 环境验证状态与证据边界（诚实红线）

- **日期**：2026-07-25
- **目的**：明确说明 SYNAPSE 在哪些环境、用什么方式、验证到什么程度，避免赛题评审时混淆"代码验证"与"赛题红线验证"。
- **关联**：`docs/superpowers/specs/2026-07-25-demo-video-design.md` §1.1 / §7

---

## 1. 赛题硬要求

> 「最终交付的代码需在 **openEuler 24.03-LTS-SP3** 操作系统版本上能够正常编译、运行和测试。」

注意：
- **版本精确**：是 **SP3**（24.03 LTS 的第三个 spin patch），不是 SP1/SP2，也不是无 SP 后缀的滚动 24.03 LTS。
- **形态**：原生 openEuler 操作系统（非其他发行版的容器）。
- **行为**：编译、运行、测试三件套都要在 SP3 上完成。

## 2. 当前验证矩阵

| 环境 | openEuler 版本标识 | 已验证内容 | 未验证 / 风险 |
|---|---|---|---|
| **Windows Docker Desktop** | `openeuler/openeuler:24.03-lts` 滚动标签；`/etc/os-release` 仅显示 `VERSION="24.03 (LTS)"`，**无 SP 标识** | ① `docker build` 成功（镜像 597 MB）<br>② `docker run synapse:test` → SMOKE PASSED（5 项全过）<br>③ 4 个可视化脚本（拓扑动画 / ticker / contraction / 架构图 / 谱系图）在容器内运行通过<br>④ matplotlib + viz extra 装包成功 | ❌ **不能证明是 SP3**（滚动标签 ≠ SP3）<br>❌ 不能证明原生部署（Docker 隔离层 ≠ 原生）<br>❌ 未跑真实 VectorEngine 实验（待 .env 配置） |
| **原生 openEuler SSH 服务器** | **未部署**（用户当前为腾讯云 Ubuntu 服务器，待重装为 openEuler SP3） | — | ❌ 全部未验证 |

## 3. 当前已完成的「代码逻辑层」证据

以下证据在 Docker 容器（24.03-lts，非显式 SP3）中跑通，**只证明代码逻辑正确，不构成赛题 M10 红线证据**：

| 项 | 证据 |
|---|---|
| 镜像可构建 | `docker build -t synapse:test .` 成功（2026-07-25 实测） |
| 离线 smoke 自检 | `docker run --rm synapse:test` → 5 项 PASS + SMOKE PASSED |
| 可视化脚本 | `render_agent_topology.py` / `replay_ab_ticker.py` / `plot_contraction_trajectory.py` / `plot_architecture.py` / `plot_axis_positioning.py` 在容器内运行通过（用历史 result.json 数据） |
| 现有实验数据可复现 | 77 个 `runs/*/result.json` 可被脚本读取、渲染为图 |

## 4. 赛题 M10 红线「未完成」的诚实清单

以下必须在**原生 openEuler 24.03-LTS-SP3** 服务器上完成后才能声称满足赛题 M10：

- [ ] 服务器 `cat /etc/os-release` 显示 `VERSION="24.03 (LTS SP3)"`（或等价 SP3 标识）
- [ ] `sudo dnf install -y python3 python3-pip` 原生安装成功
- [ ] `pip install --user uv` 原生安装成功
- [ ] `uv sync --extra api` 原生同步成功
- [ ] `uv run synapse smoke` 原生 SMOKE PASSED
- [ ] `uv run synapse probe --config configs/vectorengine.yaml` 原生真实 API 探针通过
- [ ] 至少一组真实 LLM 实验（ab / hotpot / m7）在原生环境跑通，存 `runs/`
- [ ] 在 `docs/部署文档.md` §F 追加原生 SP3 实测记录

## 5. 取得原生 SP3 环境的路径

### 路径 A（推荐）：腾讯云轻量服务器重装为 SP3

1. 登录 [腾讯云轻量应用服务器控制台](https://console.cloud.tencent.com/lighthouse)
2. 找到当前 Ubuntu 实例 → 更多 → **重装系统**
3. 镜像选择界面找「镜像市场」或「openEuler」分类
4. 搜索 "openEuler 24.03"：
   - 若有 **SP3** → 直接重装
   - 若只有 **SP1/SP2** → 重装后用 `sudo dnf update --releasever=24.03LTS_SP3 && sudo dnf upgrade` 升级
   - 若都没有 → 走路径 B

### 路径 B：从 openEuler 官网下载 QCOW2 自定义导入

1. 从 [openEuler 官网下载页](https://www.openeuler.openatom.cn/zh/download/) 下载 24.03 LTS SP3 通用 x86_64 云镜像（qcow2）
2. 上传到腾讯云对象存储 COS
3. 在 CVM 控制台「自定义镜像导入」（⚠️ 轻量服务器对自定义镜像支持有限，可能需改用 CVM）

### 路径 C：临时开腾讯云 CVM（云镜像市场）

1. 在 [腾讯云 CVM 控制台](https://console.cloud.tencent.com/cvm) 新建实例
2. 镜像选「云镜像市场」→ 搜索 "openEuler 24.03"
3. 选择带 SP3 的版本创建

### 路径 D：换用华为云（openEuler 原生支持最好）

华为云是 openEuler 的原厂平台，镜像支持最完整。若有华为云账号，可直接选 openEuler 24.03 LTS SP3 公共镜像。

### 路径 E（当前已就绪）：本地 ISO 安装虚拟机 / 自定义镜像导入

**用户已下载官方 ISO**：`D:\镜像包\openEuler-24.03-LTS-SP3-x86_64-dvd.iso`（4.7 GB，DVD 完整版）

这是赛题精确要求的 SP3 官方 ISO，**最强证据**。两条用法：

1. **本地虚拟机**（VMware/VirtualBox/Hyper-V）：
   - 用 ISO 创建 openEuler 24.03-LTS-SP3 x86_64 虚拟机
   - 装完 `cat /etc/os-release` 应显示 `VERSION="24.03 (LTS SP3)"`
   - 适合：录制时画面清晰可控、可反复重装
   - 注意：虚拟机需联网调 VectorEngine API（真实 LLM 走远程）

2. **腾讯云轻量服务器自定义镜像导入**：
   - 用 ISO 在本地装一台虚拟机 → 用 `virt-builder` 或 `qemu-img` 转 qcow2
   - 上传到腾讯云 COS → CVM 自定义镜像导入
   - ⚠️ 轻量服务器对自定义镜像支持有限，可能需改用 CVM

---

## 6. 录制演示视频前的硬性前置条件

**在未取得原生 openEuler 24.03-LTS-SP3 环境之前，不应录制最终演示视频**。

若强行用 Docker 内录制作最终交付：
- ⚠️ 视频画面里 `/etc/os-release` 显示的是 `24.03 (LTS)` 而非 `24.03 (LTS SP3)`，评委一眼可识别
- ⚠️ 赛题 M10 红线不满足，可能直接扣分或淘汰
- ⚠️ 项目说明书 §F「原生 SP3 实测记录」会留空，与赛题要求矛盾

**降级方案**（仅当实在拿不到 SP3）：在视频里**诚实说明**「实测于 openEuler 24.03 LTS 容器（滚动标签，SP 版本未显式核验），代码层零平台依赖，原生 SP3 部署等价」——但这不是赛题要求的标准答案。

## 7. API key 安全处理

- 已知风险：曾有一次 API key 在聊天中明文暴露，已建议在 VectorEngine 平台轮换
- 正确配置：在服务器/容器的 `.env` 文件直接配置（`.env` 已在 `.gitignore` 和 `.dockerignore`），**不在任何代码、文档、commit、聊天里硬编码或粘贴**
- 本次执行：本会话不接触 key 内容，仅验证 `.env` 配置机制

---

**结论**：当前完成度约 **60%**（代码逻辑层 + 可视化资产层全部就绪），原生 SP3 部署层 **0%**（待用户提供环境）。在拿到原生 SP3 环境后，预计还需 **0.5-1 天**完成 Task 1（环境部署）+ Task 2（预跑真实实验）+ Task 7-8（录制剪辑）。

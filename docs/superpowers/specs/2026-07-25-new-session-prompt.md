# 任务：SYNAPSE 演示视频全流程 + 创新点包装（openEuler 24.03-LTS-SP3）

> **给新对话的完整提示词（v4，2026-07-25）**
> 直接复制本文件全文贴入新对话即可启动。
>
> **v3 → v4 变更**（务必先读）：
> - **主工作目录翻面**：从「Windows 主 + scp 推 SP3」改为「**SP3 `/root` 主战场**」。新会话的 Bash 工具**已经登录 SP3**（`whoami=root`、`cat /etc/os-release` 显示 `24.03 (LTS SP3)`、`pwd` 在 `/root`）。所有代码工作、依赖安装、预跑、可视化、dashboard、录制脚本**直接在 SP3 本地完成**。
> - **删除 SSH 工具节**：不再需要 sshpass/paramiko/SSH 命令，远程操作 = 直接 `cd ~/synapse && ...`。
> - **首次代码同步改为单向一次性推送**：见 §4。Windows 侧的未提交改动一次性 scp 到 SP3 后，Windows 只剩 PPT/说明书/docx 这类 Windows-only 资产。
> - **PPT/说明书改动落地策略**：见 §3 末尾「PPT/说明书改动落地」——优先产出 `docs/创新点包装清单.md`（文案升级表 + 代码依据），用户在 Windows PowerPoint/Word 手动改，避免破坏原排版。
> - **plan 与新规格不符的处理**：现有 `docs/superpowers/plans/2026-07-25-demo-video.md`（OBS 多窗口实时录制方案）**不重写**，把本 v4 当作已批准的最新规格，直接按 §11 工作流 TodoWrite 拆任务执行；现有 plan 仅在「OBS 录制当日 checklist + 镜头叙事脚本」部分作为参考。
> - **其余任务内容（包装方向 A/B/C、6 项预跑实验、可视化资产、HTML dashboard、demo_record.sh、录制指南）全部保留**。

---

## 0. 一句话目标

在官方要求的 openEuler 24.03-LTS-SP3 虚拟机上（**新会话 Bash 已在 SP3 `/root`**），跑通 SYNAPSE 全流程，**完成创新点包装 + 轻量补代码**，并准备一份**自动化录制脚本**，让用户启动 OBS 后一键跑完 5 分钟演示视频（全程无音，严格 ≤5 分钟）。

---

## 1. 背景与身份

- 你是 ZCode 助手，遵循 `~/.zcode/AGENTS.md` 全部规则（求真务实、外科手术式修改、Skill 纪律等）
- 项目：SYNAPSE，参加"第三届中国研究生操作系统开源创新大赛"社区赛题
- 赛题：一种面向多智能体协作的低开销通信、非文本状态传递与共享记忆机制
- **主工作目录：SP3 虚拟机 `/root/synapse`**（新会话 Bash 已在此）
- Windows 备用目录：`D:\操作系统开源大赛\synapse`（仅用于 Windows-only 资产：PPT/说明书/docx）
- 目标执行环境：openEuler 24.03-LTS-SP3（**已就位**）

---

## 2. 环境验证（开局第一步，必做）

> 不再需要 SSH 工具节。直接在当前 Bash 里跑以下命令验证 SP3 环境：

```bash
# === 开局自检（30 秒）===
whoami                                       # 必须 root
pwd                                          # 应在 /root 或可 cd 到 /root
uname -a                                     # Linux ... x86_64
cat /etc/os-release | head -5                # 必须看到 NAME="openEuler" VERSION="24.03 (LTS SP3)"
python3 --version                            # 应 3.11.x（openEuler 24.03 自带）
which python3 pip3 uv git dnf firefox        # 探查已有工具
df -h /root /tmp                             # 剩余空间（需 >20GB 跑实验 + 录制）
```

**硬性验收**：
- `whoami` = `root` ✅
- `/etc/os-release` 显示 `24.03 (LTS SP3)`（注意是 **SP3**，不是无 SP 后缀的滚动 LTS）✅
- 任意一项不符 → **停下来问用户**（不要瞎猜环境）

### API key（安全红线）

- VectorEngine API key：**用户私有，不在本文档中明文写出**
- 后端：`https://api.vectorengine.cn/v1`
- 模型：`qwen3-235b-a22b-instruct-2507`（temp=0）；embedding：`text-embedding-3-small`
- **配置方式**：在 SP3 `~/synapse/.env` 写入 `VECTORENGINE_API_KEY=<用户私有的真实 key>`
- **绝不**写入代码/commit/聊天/文档（包括本提示词文件），只放 .env（.gitignore 已忽略 .env）
- **本仓库已 push 到 gitlink 公开仓库**：若需在新会话用到 key，从用户私有渠道（密码管理器 / 本地未跟踪副本）获取，不要从 git 历史里翻

---

## 3. ★ 核心任务一：创新点包装 + 轻量补代码（用户最关心，最先做）

### 背景与判断

- 项目自评"创新点不够，残差这种老掉牙"——但真实情况是**多个有料的点被低估/没突出**
- 用户决策："**包装 + 轻量补代码**"，让 PPT/文档的表述都能在代码中找到对应（合法技术营销）
- 用户已明确不考虑后续复赛/抽查影响，**但仍坚守"表述必须能落到代码"这条底线**——这是技术营销与造假的分界
- **不允许做**：写代码里完全没有的功能到 PPT 里（如声称用了 faiss 但代码无 import）

### 必读文件（三方比对，确认每项真实状态）

> **SP3 上读代码**；PPT/说明书在 Windows 上读（见下方「Windows-only 资产读取」）。

1. **Windows-only**：`D:\操作系统开源大赛\项目文档\SYNAPSE答辩PPT_v6.pptx`（PPT v6，必读）
   - PPT 是 zip 格式，**在 Windows Git Bash 用 python 解析提取文本**：
   ```bash
   # 在 Windows 备用目录执行（不在 SP3）
   cd "D:/操作系统开源大赛"
   python <<'EOF'
   import zipfile, re, sys, html
   sys.stdout.reconfigure(encoding='utf-8')
   with zipfile.ZipFile(r'D:\操作系统开源大赛\项目文档\SYNAPSE答辩PPT_v6.pptx') as z:
       slide_files = sorted([n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)],
                            key=lambda x: int(re.search(r'\d+', x).group()))
       for i, sf in enumerate(slide_files, 1):
           xml = z.read(sf).decode('utf-8', errors='ignore')
           text = xml.replace('</a:p>', '\n').replace('</a:br>', '\n')
           text = re.sub(r'<[^>]+>', '', text)
           text = html.unescape(text)
           lines = [l.strip() for l in text.split('\n') if l.strip()]
           print(f"\n===== Slide {i} =====")
           for l in lines: print(l)
   EOF
   ```
2. **Windows-only**：`D:\操作系统开源大赛\项目文档\项目说明书(1).docx`（说明书，必读）
   - 提取方法同上，按 `<w:p>` 分段（用 `python-docx` 或 zipfile + 正则）
3. **SP3 上读代码**：`~/synapse/src/synapse/` 下核心模块（确认代码现状，重点核实方向 B 的字段是否被实际填充）

> **跨会话协作提示**：本会话 Bash 在 SP3，读不到 Windows 的 PPT/说明书。两种方案：
> - **方案 A（推荐）**：在 Windows 备用会话里先把 PPT/说明书文本 dump 成 `docs/superpowers/specs/ppt_v6_text.md` + `docs/superpowers/specs/说明书_text.md`，scp 到 SP3 `~/synapse/docs/` 后本会话直接读
> - **方案 B**：本会话只做代码侧核实 + 补码，PPT/说明书文案改动产出清单文档，由用户在 Windows 手动落地

### 方向 A：合法包装（代码已实现，仅需升级表述，0 工作量）

| 当前表述 | 升级表述 | 代码依据 |
|---|---|---|
| "残差编码" | "**Verified Wyner-Ziv Coordination**：首次将信源编码的率失真理论引入多 agent 通信，带语义校验的有损协作" | `residual.py` 率失真贪心 + `SYNAPSE.tex` 信息论框架 |
| "CAS 句柄" | "**内容寻址的语义路由 + 自适应协议降级**（residual→embedding→text 三档）" | `cas.py` hash 寻址 + metrics.tier_* 字段 |
| "HybridRetriever" | "**Theory-of-Mind 预测驱动的记忆检索**：发送方预测接收方已知，只传 surprise residual" | `tom.py` ToMPredictor + `retrieval.py` 三路融合 |
| 散落实验数字 | "**教科书级因果证明**：B3 消融实验证明 97.6% 通信压缩源于记忆复用" | `signal_20260724_191435` vs `193555` 对照 |
| 谱系图占位 | "**首个黑盒、免训练、免层对齐**的多 agent 潜空间通信方案" | `docs/系统设计文档.md` §10.2 |

### 方向 B：轻量补代码（让表述成立，每项 ≤4h，按优先级）

读代码时**重点核实**这些字段是否被实际填充，未填充的补上：

1. **能力探测 + TTL 缓存**（说明书 [107] 已声称"附带实际探测 + TTL 缓存"）
   - 现状：`team.py:46-47` 的 check_fn 直接 `return set(cap.probe)`，没探测
   - 补强：让 check_fn 真跑一次 CodeAct 沙箱试执行，结果带 TTL dict 缓存（约 30 行）
   - 文件：`src/synapse/protocol/handshake.py` + `runtime/team.py`

2. **frozen-snapshot 记忆注入**（总结 [282] 已声称"借鉴 hermes"）
   - 现状：`metrics.frozen_snapshot_injections` 字段在 modes 里没填充
   - 补强：在 `synapse_mode.py` 跨任务复用时，注入上一次任务的"冻结快照"作为预测基，计数 +1（约 20 行）
   - 文件：`src/synapse/modes/synapse_mode.py` + `memory/store.py`

3. **result spill 降级**（metrics.result_spills 字段已存在但未填充）
   - 现状：`messages.py:78` 有 `spill_result(result, cas, budget)` 函数，但 modes 未调用
   - 补强：在 `synapse_mode.py` Executor→Summarizer 通信时，超阈值 result 走 spill（约 15 行）
   - 文件：`src/synapse/modes/synapse_mode.py`

4. **记忆取代链 superseded_by**（说明书 [141] 提到"借鉴 A-MEM"）
   - 现状：`MemoryUnit` 可能有字段，但 `consolidate.py` 是否真更新需核实
   - 补强：consolidate 时检测语义重复，标记 superseded_by 链（约 25 行）
   - 文件：`src/synapse/memory/{store,consolidate}.py`

5. **CodeAct 轻量沙箱**（赛题鼓励项）
   - 现状：用 smolagents 默认 LocalPythonExecutor，无模块禁用
   - 补强：传入 `authorized_imports` 白名单 + 禁用 os.system/subprocess/Popen（约 10 行配置）
   - 文件：`src/synapse/runtime/team.py`

6. **CAS backend 抽象**（为"支持 Socket/共享内存后端"表述铺路）
   - 现状：CAS 是 dict
   - 补强：抽出 `BaseCASBackend` 抽象类，dict 是默认实现，文档说"接口已隔离，可切换 Socket/SHM 后端"（约 20 行抽象 + 文档）
   - 文件：`src/synapse/stateplane/cas.py`

### 方向 C：明确不做（红线）

- ❌ 不接入 faiss（用户已决定保持原口径"语义向量余弦相似度"）
- ❌ 不真实现 eBPF/WASM（声明依赖即可，不补实现）
- ❌ 不写代码里完全没有的功能到 PPT/说明书

### 执行顺序

1. 读 PPT v6 + 说明书 + 代码核心模块（三方比对，确认每项真实状态）
2. **方向 A：产出 `docs/创新点包装清单.md`**（每张幻灯片/每段说明书的「原句→升级句→代码依据」，0 代码工作量，最先做）
3. **方向 B：按优先级补代码**（建议顺序：5沙箱 → 1能力探测 → 2frozen-snapshot → 4取代链 → 3spill → 6backend 抽象）
4. 每补一项，**同步更新 `docs/创新点包装清单.md` 相应条目的「代码依据」字段**（指向新补的代码行）
5. 全部补完后，跑 `uv run pytest tests/` 确保未破坏现有测试
6. 重新跑 `uv run synapse smoke` 确认核心功能未坏

### 包装的度（关键判断标准）

每个表述升级必须通过这个测试：
> "**如果评委截图这一行代码，能不能支持 PPT 的表述？**"
- 能 → 合法包装，通过
- 勉强（代码有占位但没逻辑）→ 触发方向 B 补码
- 完全不能 → 越线，删表述

### PPT/说明书改动落地策略（避免破坏原排版）

**优先方案（推荐）**：产出 `docs/创新点包装清单.md`，结构如下，**用户在 Windows PowerPoint/Word 里手动改**：

```markdown
# 创新点包装清单（2026-07-25）

## PPT v6 改动

### Slide N: <slide 标题>
- **原句**（slide 上的文字）：<引用>
- **升级句**：<新表述>
- **代码依据**：<文件:行号 或 字段名>
- **包装度自检**：✅ 能 / ⚠️ 勉强（已触发补码 #X）/ ❌ 越线（已删）

## 项目说明书改动
（同上结构，按段落引用原句）

## dashboard 字幕改动
（按镜头 L1-L7 列字幕升级前后）
```

**理由**：
- `.pptx`/`.docx` 是二进制 zip，python-pptx/python-docx 直接改有破坏原排版风险（字体/动画/母版），回滚难
- 清单方式可控可逆，用户改完还能再核一轮
- 包装清单本身也是赛题答辩的"创新点说明"附件，一举两得

**备选方案**（用户明确要求时才用）：python-pptx 批量改文字（保留格式），python-docx 改段落。仍要先有清单确认。

---

## 4. 首次代码同步（Windows → SP3，单向一次性推送）

> **本节是 v3「部署」的简化版**。新会话 Bash 已在 SP3，代码搬运只需做一次。

### Windows 侧已有未提交改动（必须同步到 SP3）

在 Windows 备用目录 `D:\操作系统开源大赛\synapse` 下确认以下改动存在：

- `src/synapse/modes/synapse_mode.py`：token bug 修复（`ti0, to0 = team.token_io()` + `m.llm_input_tokens = ti - ti0`）
- `src/synapse/modes/text_mode.py`：同样 token bug 修复
- `scripts/render_agent_topology.py`（新）：拓扑动画帧
- `scripts/replay_ab_ticker.py`（新）：A/B ticker 回放
- `scripts/plot_contraction_trajectory.py`（新）：残差轨迹（含 --smooth）
- `scripts/plot_architecture.py`（新）：架构图（已通过视觉 MCP 验证）
- `scripts/plot_axis_positioning.py`（新）：谱系图（已通过视觉 MCP 验证）
- `docs/figs/architecture_v2.png` + `axis_positioning.png`（生成产物）
- `docs/superpowers/specs/*.md`（design doc / environment-evidence / 本 v4 提示词）
- `docs/superpowers/plans/2026-07-25-demo-video.md`（OBS 录制参考）
- `docs/superpowers/specs/2026-07-25-new-session-prompt-v3-archive.md`（v3 归档）
- 加上**任务一补强的代码改动**（方向 B 的 6 项，在 SP3 上做完后无须再同步）

### 推送策略（二选一）

**策略 A（推荐）：git push + SP3 git pull**
```bash
# Windows 备用目录
cd "D:/操作系统开源大赛/synapse"
git add -A && git commit -m "feat: token bug fix + 可视化脚本 + 架构/谱系图 + 包装清单"
git push origin master

# SP3（本会话）
cd ~
git clone <synapse-remote-url> synapse    # remote: gitlink.org.cn（见 Windows git remote -v）
# 或若已 clone 过：cd ~/synapse && git pull
```

**策略 B：scp 直接覆盖**（git 不通时用）
```bash
# 在 Windows 备用会话执行（不是本 SP3 会话）
scp -r "D:/操作系统开源大赛/synapse/src/synapse/" \
       "D:/操作系统开源大赛/synapse/scripts/" \
       "D:/操作系统开源大赛/synapse/docs/figs/architecture_v2.png" \
       "D:/操作系统开源大赛/synapse/docs/figs/axis_positioning.png" \
       "D:/操作系统开源大赛/synapse/docs/superpowers/" \
       "D:/操作系统开源大赛/synapse/runs/demo_2026-07-25/" \
       root@192.168.190.147:~/synapse/
```

### SP3 侧初始化（推送完成后在 SP3 跑）

```bash
cd ~/synapse
uv sync --extra api --extra viz        # viz 为 matplotlib 等绘图依赖

# 配置 API key（.env 已在 .gitignore，安全；key 从用户私有渠道获取，不在本仓库）
cat > ~/synapse/.env <<'EOF'
VECTORENGINE_API_KEY=<用户私有的真实 key，从密码管理器或本地未跟踪副本获取>
EOF
chmod 600 ~/synapse/.env

# 验证
uv run synapse smoke                                                    # 必须 SMOKE PASSED
uv run synapse probe --config configs/vectorengine.yaml                 # 必须端到端跑通
```

**验收门**：smoke PASSED + probe 端到端通 = 部署完成。

---

## 5. 核心任务二：在 SP3 上预跑全部演示数据

### 预跑目录

`~/synapse/runs/demo_2026-07-25/`

### 实验清单（按优先级）

| 实验 | 命令 | 验证门 |
|---|---|---|
| HotpotQA | `uv run synapse hotpot --n 10 --k 3 --retrieval single --config configs/vectorengine.yaml` | `improvement.llm_token_saved_pct > 60` |
| MuSiQue | `uv run synapse musique --n 3 --k 3 --retrieval twohop --config configs/vectorengine.yaml` | `> 60` |
| m7 跨组 | `uv run synapse m7 --g1 5 --g2 5 --config configs/vectorengine.yaml` | G2 bytes ≤ G1 且 G2 hit ≥ G1 |
| signal 残差 | `uv run synapse signal --rounds 5 --config configs/vectorengine.yaml` | contraction 单调下降趋势 |
| ab 双模式 | `uv run synapse ab --rounds 5 --config configs/vectorengine.yaml` | `llm_token_saved_pct > 0` |
| coqa | `uv run synapse coqa --convs 3 --config configs/vectorengine.yaml` | `hit_rate > 0.8` |

每个跑完拷贝最新 result.json 到 `~/synapse/runs/demo_2026-07-25/<name>_result.json`：
```bash
cp $(ls -t runs/<cmd>_* /result.json | head -1) runs/demo_2026-07-25/<name>_result.json
```

跑完写 `~/synapse/runs/demo_2026-07-25/SUMMARY.md`（数字对照表）。

### 降级策略

- API 抖动 → 重试 1-2 次
- 实在不行 → 引用 Windows 侧 `D:\操作系统开源大赛\synapse\runs\` 历史 run（07-24 真实数据：hotpot_20260724_214352 / musique_20260724_203011 / coqa_20260724_211318 / signal_20260724_191435 / m7_20260620_214354），scp 到 SP3 后标注 "数据来自历史 run"
- 用 `tmux` 跑长任务，断连不影响

---

## 6. 核心任务三：生成全部可视化资产

```bash
cd ~/synapse
uv run python scripts/render_agent_topology.py --input runs/demo_2026-07-25/ab_result.json --out docs/figs/agent_topology
uv run python scripts/plot_contraction_trajectory.py --input runs/demo_2026-07-25/signal_result.json --out docs/figs/contraction_trajectory.png --smooth
uv run python scripts/plot_architecture.py
uv run python scripts/plot_axis_positioning.py
```

**视觉验证**：每张图生成后，**必须用 `zai-mcp-server` 或 `MiniMax.understand_image` 走视觉 MCP 诊断**（你是纯文本模型，看图必走 MCP，禁止凭描述猜）。

---

## 7. 核心任务四：构建 HTML dashboard（学长建议的核心）

### 录制架构（混合方案，已定）

不是纯终端，也不是纯 HTML，而是**混合**：
- **真终端镜头**（L1 落地、L3 A/B 命令）：用真实 SSH/桌面终端录，体现 openEuler 真实性
- **HTML dashboard 镜头**（L2/L4/L5/L6/L7）：用浏览器全屏 + 自动播放，体现指标可视化（学长建议核心）
- 用户启动 OBS 后，bash 脚本自动按时间表切换"终端窗口"和"浏览器窗口"

### 路径与结构

`~/synapse/dashboard/`：
```
dashboard/
├── index.html          # 主页面，7 镜头自动切换
├── style.css           # 暗色主题，SYNAPSE 配色（蓝/橙/绿）
├── app.js              # 时间表驱动的镜头切换 + 数据动画
├── data.json           # 从 runs/demo_2026-07-25/ 预生成的数据
└── assets/             # 架构图/谱系图/contraction 图等 PNG（从 docs/figs/ 复制）
```

### 7 镜头设计（严格 5:00 = 300s）

| 镜头 | 时长 | 内容（HTML 实现） |
|---|---|---|
| L1 落地 | 0-30s | 不用 HTML，用真终端（见任务六） |
| L2 痛点+Wyner-Ziv | 30-90s | 痛点 CSS 动画（逐条浮现）+ 架构图 + 谱系图轮播 |
| L3 A/B 启动 | 90-150s | 真终端跑命令 + HTML 同步显示指标卡（tokens/bytes 实时跳动） |
| L4 结果+记忆+消融 | 150-210s | 三数据集柱状图（Chart.js）+ contraction 动画 + 97.6% 饼图 |
| L5 共享记忆 | 210-240s | retrieval.py 代码高亮 + coqa "越长越省" 曲线 |
| L6 CodeAgents 对照 | 240-270s | 三行对照表（NL/CodeAgents/SYNAPSE），SYNAPSE 行高亮 |
| L7 总结 | 270-300s | frontier 图 + "协作即压缩" 大字 + openEuler logo |

### 关键技术决策

- 用纯前端 + 预生成 `data.json`，**不写 Python 后端**（避免 WebSocket 复杂度）
- Chart.js 走 CDN：`<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`
- 用 CSS keyframes 做数字滚动动画（tokens 从 0 滚到真实值）
- 用 `setTimeout` 控制镜头切换，主时间表在 `app.js`

### 配色（与已有 PNG 一致）

- 蓝 `#4A90E2`（Agent / 默认）
- 橙 `#FF8C00`（residual / SYNAPSE 高亮）
- 绿 `#2ECC71`（memory / NO 列）
- 紫 `#9B59B6`（Eval）
- 背景 `#1a1a1a`（暗色）

### HTML dashboard 关键要点

**不要做**：
- 不要用 React/Vue（CDN 复杂、构建麻烦）
- 不要用 Python 后端 + WebSocket
- 不要追求产品级 UI

**要做**：
- 单文件 `index.html` + `style.css` + `app.js`
- 数据预 dump 到 `data.json`，`app.js` fetch 后按时间表渲染
- 镜头切换用 `display: none/block` + setTimeout 控制
- 字幕条在底部固定位置，每镜头一段文字
- 进度条在顶部，显示当前镜头进度

### 字幕文案来源（必须用包装后的措辞）

dashboard 的字幕、指标卡标题、总结大字**必须**与 `docs/创新点包装清单.md` 里的"升级句"一字不差，杜绝两套口径。

### 时间表（app.js 核心）

```javascript
const TIMELINE = [
  { id: 'L1', start: 0, end: 30 },
  { id: 'L2', start: 30, end: 90 },
  { id: 'L3', start: 90, end: 150 },
  { id: 'L4', start: 150, end: 210 },
  { id: 'L5', start: 210, end: 240 },
  { id: 'L6', start: 240, end: 270 },
  { id: 'L7', start: 270, end: 300 },
];
```

### 视觉验证（前端 skill 纪律）

写前端 UI / dashboard 命中**前端类 skill 硬触发**（AGENTS.md Rules §1.B）：
1. 先调 `frontend-design` 或 `ui-ux-pro-max` skill 读正文
2. 用 `playwright` MCP 打开 `file:///root/synapse/dashboard/index.html` 截图
3. 截图交 `zai-mcp-server.ui_diff_check` 或 `MiniMax.understand_image` 诊断（信息层级 / 配色 / 三态 / 暗色可读性）
4. 禁止只靠 console 验证 UI

---

## 8. 核心任务五：写自动化录制脚本 + 录制指南

### 录制脚本 demo_record.sh

路径：`~/synapse/scripts/demo_record.sh`（bash，全程无音）

**脚本行为**：
1. 开头 `#!/bin/bash + set -e + 起始 sleep 3`（让用户切到 OBS）
2. **L1（真终端）**：在脚本所在终端真实执行 `uname -a` / `cat /etc/os-release` / `uv run synapse smoke`，每条 sleep 2-3s
3. **L2-L7（HTML dashboard）**：自动打开浏览器全屏到 `file:///root/synapse/dashboard/index.html`
   - 用 `xdg-open` 或 `firefox --kiosk` 启动
   - dashboard 的 `app.js` 自动按时间表播放
4. 总时长精确 300s，最后显示 "=== END ==="
5. 自动关闭浏览器

**两种执行模式**：
- **模式 A（推荐）**：全部 HTML，L1 用 xterm.js 嵌入预录终端输出。一键 `bash demo_record.sh` → 浏览器自动播 300s → 完成
- **模式 B**：L1 真终端录 + L2-L7 浏览器录，后期拼接

**测试**：写完后空跑（不录），`time bash demo_record.sh` 验证 ≤300s。

### 录制指南 录制指南.md

路径：`~/synapse/docs/录制指南.md`，含：

1. **OBS 设置**：
   - openEuler SP3 上装 OBS（`dnf install obs-studio` 或 AppImage）
   - 分辨率 1920×1080，30fps，录制路径 `~/recordings/`
   - 录制源：浏览器窗口（kiosk 全屏）或 X11 root

2. **用户操作步骤（≤5 步）**：
   ```
   1. 开 OBS，新建场景，选浏览器/屏幕源
   2. 启动 firefox --kiosk file:///root/synapse/dashboard/index.html
   3. 回到 OBS，点"开始录制"
   4. 切回浏览器（dashboard 自动开始播放）
   5. 5 分钟后自动结束，回 OBS 点"停止录制"
   ```

3. **预期画面时间线**（按镜头列）

4. **应急预案**：
   - OBS 装不上 → 用 ffmpeg 录屏
   - dashboard JS 报错 → 切到降级方案（纯终端 bash）
   - 总时长超 5 分钟 → 调 `app.js` 的 setTimeout
   - LLM 调用超时 → 用预跑数据，不实时跑

---

## 9. 关键约束（红线）

### 诚实红线（视频/字幕/dashboard 里不能说）

- ❌ 不说"使用了向量数据库/faiss"（代码未真用）
- ❌ 不说"延迟降低/更快"（实测为负）
- ❌ 不说"跨进程 IPC/共享内存/Socket"（同进程 dict）
- ❌ 不说"WASM/eBPF"（未实现）
- ❌ 不说"105 个实验"（实际 77）
- 沙箱表述：明确说 "smolagents LocalPythonExecutor 子进程级沙箱"

**红线放宽（用户已确认）**：
"包装 + 轻量补代码"路线下，以下表述在补完方向 B 对应代码后**可以使用**：
- "可验证的能力探测 + TTL 缓存"（补 check_fn 真探测后可用）
- "frozen-snapshot 记忆注入"（补 modes 调用后可用）
- "result spill 降级"（补 modes 调用后可用）
- "记忆取代链 superseded_by"（补 consolidate 后可用）
- "轻量 CodeAct 沙箱（模块禁用）"（补 authorized_imports 后可用）
- "支持 Socket/SHM 后端切换"（补 backend 抽象后可用）

**红线仍坚守**：
- ❌ faiss/向量数据库（用户决定保持原口径）
- ❌ eBPF/WASM（未实现）
- ❌ 延迟降低（实测为负）
- ❌ "105 个实验"（实际 77）

### 数字口径（必须用 SP3 真实数据）

- 跑完任务二后 `~/synapse/runs/demo_2026-07-25/SUMMARY.md` 是唯一数据源
- CodeAgents L6 镜头：引用论文 Table 4 数字，不实际复现（之前发现 CodeAgents 用 web 搜索，与 synapse distractor 设置不可比）

### 必须保留的诚信负数

- HotpotQA ΔF1 可能是负数（小样本）—— 保留，标注"集中 hard 题答案表达差异"
- 包装后升级措辞：「在不牺牲金标召回（0.9）的前提下节省 71% Token，ΔF1 波动集中在 hard 题答案表达差异，不影响通信压缩的核心结论」

### 与项目说明书对齐（关键术语一字不差）

- 作品代号：SYNAPSE（全大写）
- 核心 framing："带增长边信息的 Wyner-Ziv 条件率失真编码"
- 三重机制顺序：结构化通信协议 → 句向量预测残差编码 → 内容寻址共享记忆
- 三大瓶颈顺序：Token 消耗 / 编解码时延 / 经验沉淀
- 残差措辞："惊讶残差"
- 总结 framing："协作即压缩 / 越用越省、越用越聪明"

---

## 10. 现成资产（直接用，不重做）

### 必读文档

- `docs/superpowers/specs/2026-07-25-demo-video-design.md`：design doc（7 镜头骨架、赛题对应表、风险矩阵）
- `docs/superpowers/plans/2026-07-25-demo-video.md`：旧实施计划（仅「OBS 录制当日 checklist + 镜头叙事脚本」部分作参考，**任务编排以本 v4 为准**）
- `docs/superpowers/specs/2026-07-25-environment-evidence.md`：环境诚实红线

### 已验证的可视化脚本（不要改逻辑）

- `scripts/render_agent_topology.py`（拓扑动画，已修 Summarize 标签出框）
- `scripts/replay_ab_ticker.py`（A/B ticker，已支持多格式 result.json）
- `scripts/plot_contraction_trajectory.py`（残差轨迹，已加 --smooth + 双标注框）
- `scripts/plot_architecture.py`（架构图，已修文字溢出，15×10 加宽版）
- `scripts/plot_axis_positioning.py`（谱系图）

### 已生成图（视觉 MCP 已验证）

- `docs/figs/architecture_v2.png`、`docs/figs/axis_positioning.png`
- `docs/figs/coqa_tokens.png`、`docs/figs/hotpot_frontier.png` 等 6 张历史图

### 历史 run（07-24 VectorEngine 真实，降级用，在 Windows 侧）

> SP3 上跑不出时，从 Windows 备用目录 scp 这几个目录到 SP3 `~/synapse/runs/`：

- `runs/hotpot_20260724_214352/`（HotpotQA N=10 省 71.09%）
- `runs/musique_20260724_203011/`（MuSiQue N=3 省 80.9%）
- `runs/coqa_20260724_211318/`（CoQA hit 0.921）
- `runs/signal_20260724_191435/`（残差收缩轨迹）
- `runs/m7_20260620_214354/`（跨组记忆，旧 Paratera）

### CodeAgents 复现资料

- `external/CodeAgents.zip`（4.2MB，已下载在 Windows，论文 anonymous 代码，不入 git）
- 已确认：Qwen3Model 适配器存在，codified prompt YAML 存在
- 之前调研发现 CodeAgents 用 web 搜索 agent，与 synapse distractor 不可比 → **不实际复现，引用论文数字**

---

## 11. 工作流（按优先级，建议执行顺序）

1. **开局自检**（§2）：验证 SP3 环境 + 配 .env + smoke/probe 通过
2. **首次代码同步**（§4）：Windows → SP3 推送代码（git push 或 scp）
3. **★ 任务一：创新点包装工作流**（最先做，影响后续所有表述）：
   - 读 PPT v6 + 说明书 + 代码核心模块（三方比对）
   - 产出 `docs/创新点包装清单.md`（方向 A，0 工作量）
   - 按优先级补 6 项代码（方向 B，每项 ≤4h）
   - 每补一项更新清单的「代码依据」字段
4. **任务二：预跑**（§5，用补强后的代码跑数据）
5. **任务三：生成图**（§6，视觉 MCP 验证每张图）+ **任务四 HTML dashboard**（§7，dashboard 字幕用包装后措辞）
6. **任务五：录制脚本 + 录制指南**（§8）
7. 空跑测试，确认 ≤300s
8. 三段式收尾，给用户完整录制指南

---

## 12. 风险预案

| 风险 | 对策 |
|---|---|
| SP3 上装包失败 | openEuler 24.03 + Python 3.11 + uv；matplotlib 单独装；faiss 不装 |
| API 限额/抖动 | 分批跑，失败重试，降级到 07-24 历史 run（scp 过来） |
| LLM 输出不稳定 | temp=0 应稳定；数字离谱重跑 |
| tmux 断连 | 用 `tmux new -s demo` 跑长任务，`tmux attach -t demo` 重连 |
| openEuler OBS 装不上 | ffmpeg + x11grab 降级 |
| HTML dashboard JS 报错 | 降级纯终端方案（已有 bash 脚本基础） |
| 总时长超 5 分钟 | 调 setTimeout；砍 L5（合并到 L4） |
| 任务一补码破坏现有测试 | 每补一项跑 `uv run pytest tests/`；破坏则回滚该项 |
| SP3 无桌面环境（headless） | ffmpeg 录屏需 Xvfb 虚拟显示；或退回 Windows OBS 内录降级 |
| 跨会话上下文丢失（用户开新会话切 SP3） | 本文件 v4 是新会话的完整启动提示词，直接贴入即可恢复全部上下文 |

---

## 13. 开始工作前先做的事

1. **开局自检**（§2）：在当前 Bash 跑 `whoami && cat /etc/os-release | head -5`
   - 必须看到 `openEuler 24.03 (LTS SP3)` 字样 + `whoami=root`
   - 如果不是 SP3 或不是 root，停下来问用户

2. **读 3 个文档**（§10）确认 design 和已知资产，不要重新设计

3. **建立 TodoWrite** 跟踪 5 个核心任务（任务一包装是最高优先级）

4. **遇模糊点先问用户**（≤3 个问题），不要瞎猜

---

## 14. 完成标志

用户拿到一份**完整的录制指南**，包含：
1. `~/synapse/dashboard/` 完整 HTML dashboard（7 镜头自动播放，全程无音）
2. `~/synapse/scripts/demo_record.sh` 自动化脚本（一键播放）
3. `~/synapse/docs/录制指南.md` 操作清单（≤5 步）
4. 全部预跑数据 + 可视化资产
5. **创新点包装清单 `~/synapse/docs/创新点包装清单.md`**（表述都能落到代码）
6. （可选）用户在 Windows 手动改完后的 PPT v7 + 说明书 v2

用户操作 ≤5 步即可录完 5 分钟视频。

---

**END OF PROMPT (v4)**

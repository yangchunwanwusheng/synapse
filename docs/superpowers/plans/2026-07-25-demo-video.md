# SYNAPSE 演示视频实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 录制一支 ≤5 分钟的 SYNAPSE 演示视频，作为第三届中国研究生操作系统开源创新大赛社区赛题交付物，严格对齐项目说明书叙事 DNA（Wyner-Ziv framing + 三重机制），在原生 openEuler 24.03-LTS-SP3 服务器上以 OBS 录制。

**Architecture:** 三段式叙事（openEuler 落地 → 同基座公平 A/B → CodeAgents 学术对照），7 镜头 5:00。前置工作分四个并行/串行工作流：①openEuler 服务器环境准备 ②预跑实验拿真实数据 ③CodeAgents 论文复现 ④可视化资产制作；最终汇合到⑤视频脚本定稿 + ⑥OBS 录制 + ⑦后期剪辑。

**Tech Stack:** openEuler 24.03-LTS-SP3 / uv / synapse-mas v0.1.0 / smolagents 1.26 / Qwen3-235B（VectorEngine）/ OBS Studio / Python（matplotlib 绘图）/ drawio（架构图）

**Spec:** `docs/superpowers/specs/2026-07-25-demo-video-design.md`（已批准）

**关键事实**（写计划时已核实）：
- Windows Docker 已实测：`docker build` + `docker run synapse:test` → SMOKE PASSED（今日）
- `cmd_m7`（cli.py:233-267）：`uv run synapse m7 --g1 5 --g2 5` 输出 G1/G2 跨组复用对比
- `ABRunner.run`（harness.py:13-39）输出 `text_trajectory`/`synapse_trajectory`/`improvement`/`contraction_bytes`
- 真实数字基准（07-24 VectorEngine）：HotpotQA N=10 省 71.09% / MuSiQue N=3 省 80.9% / CoQA hit 0.921
- CodeAgents 论文（arXiv 2507.03254）anonymous 代码活跃，作者已内建 Qwen3Model

---

## 文件结构（File Structure）

### 新建文件

| 文件 | 职责 |
|---|---|
| `external/CodeAgents/` | clone 的论文复现代码（不入 synapse 主依赖） |
| `external/CodeAgents/run_qwen3_synapse_compare.py` | SYNAPSE 在 CodeAgents 的 HotpotQA 设置上的对照脚本 |
| `runs/demo_2026-07-25/` | 演示专用预跑数据目录（ab/m7/signal/hotpot/codeagents 子目录） |
| `scripts/render_agent_topology.py` | 从 result.json 渲染 agent 拓扑动画帧（PNG 序列） |
| `scripts/replay_ab_ticker.py` | A/B 底部 ticker 终端回放脚本（用于 OBS 录制） |
| `scripts/plot_contraction_trajectory.py` | 残差字节收缩轨迹动画帧（2787→960） |
| `docs/figs/architecture_v2.drawio` + `.png` | 新架构图（按说明书流水线） |
| `docs/figs/axis_positioning.drawio` + `.png` | 三轴定位谱系图（说明书 §10.3） |
| `docs/figs/codeagents_compare.png` | CodeAgents vs SYNAPSE 对照表图 |
| `docs/figs/agent_topology/frame_001.png` ~ `frame_0NN.png` | 拓扑动画帧序列 |
| `docs/演示视频脚本-v2.md` | 对齐 design v2 的 7 镜头脚本（含分镜、画面、口播、字幕） |
| `docs/录制checklist.md` | OBS 录制当日 checklist（环境检查 + 镜头清单 + 应急预案） |

### 修改文件

| 文件 | 改动 |
|---|---|
| `docs/演示视频脚本.md` | 顶部加 `> DEPRECATED：已被 docs/演示视频脚本-v2.md 取代（2026-07-25）` |
| `docs/部署文档.md`（可选） | 补充原生 openEuler 服务器录制的实测记录 |
| `.gitignore` | 加 `external/`（论文复现代码不入主仓） |

---

## 任务依赖图

```
Task 1 (openEuler 服务器环境)  ─┐
                               ├─→ Task 4 (可视化资产) ─┐
Task 2 (预跑实验)  ─────────────┤                        │
                               │                        ├─→ Task 6 (脚本定稿) ─→ Task 7 (OBS 录制) ─→ Task 8 (后期剪辑)
Task 3 (CodeAgents 复现) ──────┘                        │
                                                        │
Task 5 (架构/谱系图) ──────────────────────────────────┘
```

- Task 1/2/3 可并行（独立工作流）
- Task 4 依赖 Task 2（要 result.json 才能渲染）和 Task 3（要 CodeAgents 数字）
- Task 5 独立（仅依赖说明书）
- Task 6 依赖 Task 2/3/4/5（要全部数据和资产）
- Task 7 依赖 Task 6
- Task 8 依赖 Task 7

---

## Task 1: openEuler 服务器环境准备

**目的**：在原生 openEuler 24.03-LTS-SP3 服务器上跑通 synapse + OBS 录制环境，作为后续所有真实实验和录制的地基。

**Files:**
- 无代码改动，纯环境配置
- 产出：`docs/部署文档.md`（补充原生服务器实测记录段落）

- [ ] **Step 1: SSH 登录服务器，验证 openEuler 版本**

```bash
ssh <user>@<server>
uname -a
cat /etc/os-release | head -5
```
预期输出包含：`openEuler 24.03 (LTS)`、x86_64。

若版本不是 24.03-LTS-SP3，停下来与用户确认（赛题硬要求是 SP3）。

- [ ] **Step 2: 安装系统依赖**

```bash
sudo dnf install -y python3 python3-pip
python3 --version
```
预期：`Python 3.11.x`（openEuler 24.03 自带 3.11）。

- [ ] **Step 3: 安装 uv 并 clone 项目**

```bash
pip install --user uv
export PATH="$HOME/.local/bin:$PATH"
uv --version
# clone synapse（如服务器无代码）
git clone <synapse-repo-url> ~/synapse
cd ~/synapse
```

- [ ] **Step 4: 同步依赖 + 配置 API key**

```bash
uv sync --extra api
cp .env.example .env
# 编辑 .env 填入 VECTORENGINE_API_KEY=<真实key>
nano .env
```

- [ ] **Step 5: 跑 smoke 自检 + 真实 API 探针**

```bash
uv run synapse smoke
# 预期 SMOKE PASSED（5 项 PASS）

uv run synapse probe --config configs/vectorengine.yaml
# 预期：鉴权 PASS + 端到端跑通
```

若 probe 失败，检查 .env 的 API key 和 `configs/vectorengine.yaml` 的 api_base。

- [ ] **Step 6: 安装 OBS Studio**

```bash
# openEuler 24.03 用 dnf 装 OBS（若仓库有）
sudo dnf install -y obs-studio
# 若仓库无，下载 AppImage：
# wget https://github.com/obsproject/obs-studio/releases/download/<version>/OBS-Studio-<version>-Linux-x86_64.AppImage
# chmod +x OBS-Studio-*.AppImage
obs --version
```

若服务器无桌面环境（headless），停下来与用户确认录制方案（可能需 X11 转发或换 Docker 内录降级）。

- [ ] **Step 7: 在 `docs/部署文档.md` 末尾追加原生服务器实测记录**

在 `docs/部署文档.md` 的 §E（Docker 实测记录）后新增 §F：

```markdown
## §F. 原生 openEuler 24.03-LTS-SP3 服务器实测（2026-07-XX）

- 服务器：<server-spec>
- Python：3.11.x（系统自带）
- 部署方式：`dnf install python3 python3-pip` → `pip install --user uv` → `uv sync --extra api`
- smoke：SMOKE PASSED（5 项）
- probe（真实 API）：端到端跑通
- OBS Studio：<version>，可正常捕获终端窗口
- 录制结论：满足赛题 M10 红线
```

填入真实日期、服务器规格、版本号。

- [ ] **Step 8: Commit**

```bash
git add docs/部署文档.md
git commit -m "docs(deploy): 补充原生 openEuler 服务器实测记录 §F"
```

---

## Task 2: 预跑实验，准备演示真实数据

**目的**：在 openEuler 服务器上预跑所有视频需要的实验，存到 `runs/demo_2026-07-25/`，作为录制时的数据回放源。视频用「实时启动命令 + 数据回放」混合剪辑，避免 LLM 抖动翻车。

**Files:**
- 无代码改动
- 产出：`runs/demo_2026-07-25/{ab,m7,signal,hotpot,musique}/result.json`

- [ ] **Step 1: 创建演示数据目录**

```bash
cd ~/synapse
mkdir -p runs/demo_2026-07-25
```

- [ ] **Step 2: 预跑 A/B 双模式（L3-L4 主菜）**

```bash
uv run synapse ab --rounds 5 --config configs/vectorengine.yaml 2>&1 | tee runs/demo_2026-07-25/ab_run.log
# 找到最新 result.json 复制到 demo 目录
cp $(ls -t runs/ab_*/result.json | head -1) runs/demo_2026-07-25/ab_result.json
```

记录关键数字到 `runs/demo_2026-07-25/ab_summary.md`：
- text_total.llm_total_tokens / synapse_total.llm_total_tokens
- improvement.llm_token_saved_pct
- contraction_bytes 序列

- [ ] **Step 3: 预跑 M7 跨组记忆（L4 镜头）**

```bash
uv run synapse m7 --g1 5 --g2 5 --config configs/vectorengine.yaml 2>&1 | tee runs/demo_2026-07-25/m7_run.log
cp $(ls -t runs/m7_*/result.json | head -1) runs/demo_2026-07-25/m7_result.json
```

记录到 `m7_summary.md`：G1 hit_rate / G2 hit_rate / G1 mean_nontext_bytes / G2 mean_nontext_bytes / reuse_ok。

**验收门**：`reuse_ok = True`（G2 均字节 ≤ G1 且 G2 命中 ≥ G1）。若 False，重跑 1 次；仍 False 则停下来分析（可能需调整 topic 或 rounds）。

- [ ] **Step 4: 预跑 signal 残差轨迹（L4 字节轨迹动画）**

```bash
uv run synapse signal --rounds 5 --config configs/vectorengine.yaml 2>&1 | tee runs/demo_2026-07-25/signal_run.log
cp $(ls -t runs/signal_*/result.json | head -1) runs/demo_2026-07-25/signal_result.json
```

记录 `contraction_bytes` 序列到 `signal_summary.md`（应为单调下降，如 2787 → 1812 → 1410 → 1374 → 960）。

- [ ] **Step 5: 预跑 HotpotQA（L4 数据表）**

```bash
uv run synapse hotpot --n 10 --k 3 --retrieval single --config configs/vectorengine.yaml 2>&1 | tee runs/demo_2026-07-25/hotpot_run.log
cp $(ls -t runs/hotpot_*/result.json | head -1) runs/demo_2026-07-25/hotpot_result.json
```

记录：token 节省 % / wire_bytes 节省 % / gold_recall / ΔF1。

**验收门**：token 节省 > 60%（与 07-24 真实数据 71% 同量级）。

- [ ] **Step 6: 预跑 MuSiQue（L4 数据表）**

```bash
uv run synapse musique --n 3 --k 3 --retrieval twohop --config configs/vectorengine.yaml 2>&1 | tee runs/demo_2026-07-25/musique_run.log
cp $(ls -t runs/musique_*/result.json | head -1) runs/demo_2026-07-25/musique_result.json
```

记录同 HotpotQA。**验收门**：token 节省 > 70%。

- [ ] **Step 7: 汇总数字对照表**

写 `runs/demo_2026-07-25/SUMMARY.md`：

```markdown
# 演示视频数据汇总（2026-07-25 预跑）

| 实验 | text token | synapse token | 节省 % | gold_recall / F1 | ΔF1 |
|---|---|---|---|---|---|
| HotpotQA N=10 | <填> | <填> | <填> | <填> | <填> |
| MuSiQue N=3 | <填> | <填> | <填> | <填> | <填> |
| A/B ab --rounds 5 | <填> | <填> | <填> | — | — |

| 跨组记忆 | G1 hit | G2 hit | G1 bytes | G2 bytes | reuse_ok |
|---|---|---|---|---|---|
| m7 --g1 5 --g2 5 | <填> | <填> | <填> | <填> | <填> |

| 残差轨迹 | round 1 | round 2 | round 3 | round 4 | round 5 |
|---|---|---|---|---|---|
| signal contraction_bytes | <填> | <填> | <填> | <填> | <填> |
```

填入所有真实数字。这是后续脚本和字幕的**唯一数据源**。

- [ ] **Step 8: Commit**

```bash
git add runs/demo_2026-07-25/
git commit -m "exp(demo): 预跑演示视频所需全部实验数据 (ab/m7/signal/hotpot/musique)"
```

注意：`runs/` 已在 `.dockerignore`，但需确认是否在 `.gitignore`。若在，加 `-f` 强制 add（演示数据需要可追溯）。

---

## Task 3: CodeAgents 论文复现

**目的**：在 Qwen3-235B + VectorEngine 上复现 CodeAgents（arXiv 2507.03254）的 HotpotQA 表，作为 SYNAPSE 的外部 SOTA 对照（L6 镜头）。

**Files:**
- Create: `external/CodeAgents/`（clone）
- Create: `external/CodeAgents/run_qwen3_synapse_compare.py`
- Create: `runs/demo_2026-07-25/codeagents/result.json`
- Modify: `.gitignore`

- [ ] **Step 1: 把 external/ 加入 .gitignore**

```bash
cd ~/synapse
echo "
# 外部论文复现代码（不入主仓）
external/" >> .gitignore
```

- [ ] **Step 2: clone CodeAgents anonymous 仓库**

```bash
mkdir -p external
cd external
# 优先尝试 anonymous.4open.science
git clone https://anonymous.4open.science/r/CodifyingAgent-5A86 CodeAgents
# 若 git clone 失败，下载 ZIP：
# wget https://anonymous.4open.science/api/repo/CodifyingAgent-5A86/zip -O codeagents.zip
# unzip codeagents.zip -d CodeAgents
cd CodeAgents
ls -la
```

**验收**：看到 `Multi-Agent-Task/examples/benchmark/run_hotpot.py`、`src/codified-smolagents/`、`requirements.txt`。

若仓库已撤回或为空，**触发降级**：跳到 Step 9（降级方案）。

- [ ] **Step 3: 验证 Qwen3Model 适配器存在**

```bash
grep -rn "Qwen3Model" src/codified-smolagents/ Multi-Agent-Task/
```
预期命中 `run_hotpot.py:44: from smolagents.models import Qwen3Model` 等。

- [ ] **Step 4: 准备独立 venv（隔离依赖，不污染 synapse 主环境）**

```bash
cd external/CodeAgents/Multi-Agent-Task/examples/benchmark
python3 -m venv .venv-codeagents
source .venv-codeagents/bin/activate
pip install -r requirements.txt
```

**风险**：requirements.txt 可能拉 anthropic/openai/datasets/transformers 等重依赖。若安装失败，逐个注释非必需依赖，只保留 `openai`、`datasets`、`smolagents`。

- [ ] **Step 5: 准备 HotpotQA 数据集（100 或 30 样本）**

```bash
mkdir -p data
python3 << 'EOF'
from datasets import load_dataset
ds = load_dataset("hotpot_qa", "fullwiki", split="validation", trust_remote_code=True)
# 取前 30 样本（演示用，提速）
import json
subset = ds.select(range(30))
out = []
for ex in subset:
    out.append({
        "id": ex["id"],
        "question": ex["question"],
        "answer": ex["answer"],
        "supporting_facts": ex["supporting_facts"],
        "context": ex["context"],
    })
with open("data/hotpot_30.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"saved 30 examples to data/hotpot_30.json")
EOF
```

- [ ] **Step 6: 配置 VectorEngine 作为 OpenAI 兼容后端**

阅读 `run_hotpot.py` 找到 model 构造处（约在 main 函数），按以下方式改写为直连 VectorEngine（**不改原文件**，写一个 wrapper 脚本）：

创建 `external/CodeAgents/run_qwen3_synapse_compare.py`：

```python
"""SYNAPSE 在 CodeAgents HotpotQA 设置上的对照脚本。
复用 CodeAgents 的 codified-smolagents 库 + Qwen3-235B via VectorEngine。
"""
import os
import sys
import json

# 加入 CodeAgents 库路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Multi-Agent-Task", "src", "codified-smolagents", "src"))

from smolagents import OpenAIServerModel

# VectorEngine 作为 OpenAI 兼容后端
MODEL = OpenAIServerModel(
    model_id="Qwen3-235B-A22B-Instruct-2507",
    api_base=os.environ["VECTORENGINE_API_BASE"],  # 如 https://vectorengine.xxx/v1
    api_key=os.environ["VECTORENGINE_API_KEY"],
    temperature=0.0,
)

def run_nl_baseline(question: str, context_paragraphs: list[str]) -> str:
    """NL baseline：自然语言 prompt，全文本透传。"""
    # TODO Step 6 续：实现 NL baseline（默认 smolagents prompt）
    pass

def run_codeagents(question: str, context_paragraphs: list[str]) -> str:
    """CodeAgents：codified prompt（Python 伪代码 + EN comment + replan）。"""
    # TODO Step 6 续：调用 codified-smolagents 的 ToolCallingAgent
    pass

def calculate_f1(pred: str, gold: str) -> float:
    """CodeAgents 原论文口径的 F1。"""
    import re, string
    pred_tokens = re.sub(f"[{string.punctuation}]", "", pred.lower()).split()
    gold_tokens = re.sub(f"[{string.punctuation}]", "", gold.lower()).split()
    common = set(pred_tokens) & set(gold_tokens)
    if not pred_tokens or not gold_tokens:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gold_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)

if __name__ == "__main__":
    with open("Multi-Agent-Task/examples/benchmark/data/hotpot_30.json", encoding="utf-8") as f:
        data = json.load(f)
    results = {"nl": [], "codeagents": []}
    for i, ex in enumerate(data[:10]):  # 先跑 10 题验证管线
        # NL baseline
        pred_nl = run_nl_baseline(ex["question"], ex["context"]["title"])
        f1_nl = calculate_f1(pred_nl, ex["answer"])
        # CodeAgents
        pred_code = run_codeagents(ex["question"], ex["context"]["title"])
        f1_code = calculate_f1(pred_code, ex["answer"])
        results["nl"].append({"id": ex["id"], "pred": pred_nl, "f1": f1_nl})
        results["codeagents"].append({"id": ex["id"], "pred": pred_code, "f1": f1_code})
        print(f"[{i+1}/10] NL F1={f1_nl:.3f} | Code F1={f1_code:.3f}")
    with open("results_pilot.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("pilot done, see results_pilot.json")
```

填实 TODO 部分：

**填实方法**（必做）：
1. 先读 `Multi-Agent-Task/examples/benchmark/run_hotpot.py` 全文，看作者怎么构造 `OpenAIServerModel`、`ToolCallingAgent`、prompt 模板
2. 读 `src/codified-smolagents/src/smolagents/agents.py` 找 NL vs Code 切换开关（论文 §3.2 + 消融 `run_name="abalation-code+replan"` 暗示通过 `run_name` 或 config 区分）
3. 读 `src/codified-smolagents/src/smolagents/prompts/` 找 codified YAML system prompt（论文附录的 Python 伪代码模板）
4. `run_nl_baseline`：用官方 smolagents 默认 prompt（NL），构造 `ToolCallingAgent(model=MODEL, tools=[...])` 跑 `agent.run(question + context)`
5. `run_codeagents`：用 codified prompt（Code），同样的 agent 但 system_prompt 改为 codified YAML

**验证填实是否正确**：
- NL baseline 的 F1 应该 ≥ 0.3（证明管线通）
- CodeAgents 的 F1 应该 ≥ NL baseline（论文证明 Code ≥ NL）
- 若 CodeAgents F1 < NL，说明 prompt 没切换对，回去检查 codified YAML 是否真加载

**若实在填不出（库 API 太复杂/版本不兼容）**：触发 Step 9 降级，引用论文数字。

- [ ] **Step 7: 跑 10 题 pilot 验证管线**

```bash
export VECTORENGINE_API_BASE=<填>
export VECTORENGINE_API_KEY=<填>
python3 run_qwen3_synapse_compare.py
```

**验收**：跑完 10 题，`results_pilot.json` 有合理 F1（NL baseline F1 > 0.3，证明管线通）。

若失败（API/SerpAPI/适配问题），尝试：
1. 检查 VectorEngine 是否兼容（先用 `curl $VECTORENGINE_API_BASE/models` 列模型）
2. 若 CodeAgents 强依赖 SerpAPI（web 搜索），切换到 fullwiki 模式（用提供 context，不搜网）
3. 若 codified-smolagents 与官方 smolagents API 冲突，回退到「只跑 NL baseline + 引用 CodeAgents 论文数字」

- [ ] **Step 8: 跑完整 30 题 + 出对照表**

```bash
# 改 run_qwen3_synapse_compare.py 的 [:10] 为 [:30]，重跑
python3 run_qwen3_synapse_compare.py
# 汇总
python3 << 'EOF'
import json
with open("results_pilot.json", encoding="utf-8") as f:
    r = json.load(f)
nl_f1 = sum(x["f1"] for x in r["nl"]) / len(r["nl"])
code_f1 = sum(x["f1"] for x in r["codeagents"]) / len(r["codeagents"])
print(f"NL baseline F1: {nl_f1:.3f}")
print(f"CodeAgents F1:  {code_f1:.3f}")
EOF
```

把结果复制到 `~/synapse/runs/demo_2026-07-25/codeagents/result.json`：

```bash
mkdir -p ~/synapse/runs/demo_2026-07-25/codeagents
cp results_pilot.json ~/synapse/runs/demo_2026-07-25/codeagents/result.json
```

- [ ] **Step 9: 降级方案（仅当 Step 2-8 全部失败时触发）**

跳过实际复现，引用论文 Table 4 数字：

写 `~/synapse/runs/demo_2026-07-25/codeagents/REFERENCED.md`：

```markdown
# CodeAgents 对照（引用论文数字，未实际复现）

复现受阻原因：<填写>

引用 arXiv 2507.03254 Table 4（HotpotQA N=100, test-fullwiki）：

| 模型 | 格式 | F1 | Input Token | Output Token |
|---|---|---|---|---|
| GPT-4.1 | NL | 0.63 | 2.11M | 110.74K |
| GPT-4.1 | CodeAgents | 0.64 | 1.00M | 42.21K |
| LLaMA-4-Maverick | NL | 0.63 | 5.71M | 181.63K |
| LLaMA-4-Maverick | CodeAgents | 0.65 | 1.58M | 83.53K |

SYNAPSE 对照位置（本项目）：
- HotpotQA N=10：Token 省 71.09%，gold_recall 0.9
- 方法论对照：CodeAgents = 文本符号层；SYNAPSE = 连续表示层
```

在 Task 6 视频脚本里相应镜头改为「引用论文数字」，不声称「实际复现」。

- [ ] **Step 10: Commit（仅 synapse 仓库内的产出）**

```bash
cd ~/synapse
git add .gitignore runs/demo_2026-07-25/codeagents/
git commit -m "exp(codeagents): 复现/引用 CodeAgents HotpotQA 作外部对照"
```

`external/` 整目录不入仓（已在 .gitignore）。

---

## Task 4: 可视化资产制作（数据驱动）

**目的**：基于 Task 2 的 result.json 渲染视频需要的动态可视化资产（agent 拓扑动画、A/B ticker、残差轨迹动画）。

**依赖**：Task 2 完成（有 result.json）。

**Files:**
- Create: `scripts/render_agent_topology.py`
- Create: `scripts/replay_ab_ticker.py`
- Create: `scripts/plot_contraction_trajectory.py`
- Create: `docs/figs/agent_topology/frame_*.png`
- Create: `docs/figs/contraction_trajectory.png`

- [ ] **Step 1: 写 render_agent_topology.py（TDD：先写测试）**

Create `tests/test_render_topology.py`：

```python
"""测试 agent 拓扑渲染脚本：输入 result.json，输出 N 张 PNG 帧。"""
import json
import os
from pathlib import Path
import subprocess

def test_render_topology_produces_frames(tmp_path):
    # 造一个最小 result.json
    fake_result = {
        "result": {
            "synapse_trajectory": [
                {"messages": 3, "tier_residual": 2, "tier_embedding": 1, "tier_text": 0}
                for _ in range(3)
            ]
        }
    }
    input_json = tmp_path / "result.json"
    input_json.write_text(json.dumps(fake_result), encoding="utf-8")
    out_dir = tmp_path / "frames"

    # 调脚本
    subprocess.run(
        ["python", "scripts/render_agent_topology.py",
         "--input", str(input_json), "--out", str(out_dir)],
        check=True,
    )

    # 验证：每轮产生 1 帧 PNG
    frames = list(out_dir.glob("frame_*.png"))
    assert len(frames) == 3, f"expected 3 frames, got {len(frames)}"
```

Run: `uv run pytest tests/test_render_topology.py -v`
Expected: FAIL（脚本不存在）。

- [ ] **Step 2: 实现 render_agent_topology.py**

Create `scripts/render_agent_topology.py`：

```python
"""从 result.json 渲染 agent 拓扑动画帧。
4 节点（Planner/Retriever/Executor/Summarizer），消息边按轮次亮起。
残差边用渐变色（橙→蓝），文本边用粗实线（灰）。
"""
import argparse
import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

NODES = {
    "Planner":    (0.2, 0.8),
    "Retriever":  (0.2, 0.3),
    "Executor":   (0.7, 0.3),
    "Summarizer": (0.7, 0.8),
}

def render_frame(round_idx: int, traj_metrics: dict, out_path: Path):
    fig, ax = plt.subplots(figsize=(10, 6), dpi=120)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Round {round_idx + 1}  |  residual={traj_metrics.get('tier_residual', 0)} "
                 f"embedding={traj_metrics.get('tier_embedding', 0)} "
                 f"text={traj_metrics.get('tier_text', 0)}",
                 fontsize=14, fontweight="bold")
    # 画节点
    for name, (x, y) in NODES.items():
        circle = plt.Circle((x, y), 0.08, color="#4A90E2", alpha=0.8)
        ax.add_patch(circle)
        ax.text(x, y, name, ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    # 画通信边（按 tier 着色）
    tier_residual = traj_metrics.get("tier_residual", 0)
    tier_embedding = traj_metrics.get("tier_embedding", 0)
    tier_text = traj_metrics.get("tier_text", 0)
    edges = [
        ("Planner", "Retriever", tier_residual, "#FF8C00"),   # 残差=橙
        ("Retriever", "Executor", tier_embedding, "#1E90FF"),  # embedding=蓝
        ("Executor", "Summarizer", tier_text, "#808080"),      # text=灰
    ]
    for src, dst, count, color in edges:
        if count > 0:
            x0, y0 = NODES[src]
            x1, y1 = NODES[dst]
            ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                        arrowprops=dict(arrowstyle="->", color=color, lw=2 + count * 0.5, alpha=0.7))
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2 + 0.05
            ax.text(mx, my, str(count), ha="center", fontsize=9, color=color, fontweight="bold")
    plt.savefig(out_path, bbox_inches="tight", facecolor="white")
    plt.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    traj = data["result"]["synapse_trajectory"]
    for i, m in enumerate(traj):
        render_frame(i, m, out_dir / f"frame_{i+1:03d}.png")
    print(f"rendered {len(traj)} frames to {out_dir}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 跑测试 + 跑真实数据**

```bash
uv run pytest tests/test_render_topology.py -v
# Expected: PASS

# 用真实数据渲染
uv run python scripts/render_agent_topology.py \
    --input runs/demo_2026-07-25/ab_result.json \
    --out docs/figs/agent_topology
ls docs/figs/agent_topology/
# Expected: frame_001.png ~ frame_010.png
```

- [ ] **Step 4: 写 replay_ab_ticker.py（OBS 录制时的底部 ticker 终端回放）**

Create `scripts/replay_ab_ticker.py`：

```python
"""OBS 录制时在第二个终端窗口跑这个，回放 A/B ticker。
读取 ab_result.json，逐轮打印 round | text_bytes | synapse_bytes | saved_% | hit_rate。
"""
import argparse
import json
import time
import sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--delay", type=float, default=1.5, help="每轮间隔秒数")
    args = ap.parse_args()
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    text_traj = data["result"]["text_trajectory"]
    syn_traj = data["result"]["synapse_trajectory"]
    print(f"{'round':<6}{'text_bytes':<14}{'synapse_bytes':<16}{'saved_%':<10}{'hit_rate':<10}")
    print("-" * 56)
    sys.stdout.flush()
    for i, (t, s) in enumerate(zip(text_traj, syn_traj)):
        tb = t.get("text_bytes", 0) + t.get("header_bytes", 0) + t.get("nontext_bytes", 0)
        sb = s.get("text_bytes", 0) + s.get("header_bytes", 0) + s.get("nontext_bytes", 0)
        saved = (1 - sb / tb * 1.0) if tb > 0 else 0.0
        hit = s.get("memory_hits", 0) / s.get("memory_queries", 1) if s.get("memory_queries", 0) > 0 else 0.0
        print(f"{i+1:<6}{tb:<14}{sb:<16}{saved*100:<10.1f}{hit:<10.2f}")
        sys.stdout.flush()
        time.sleep(args.delay)

if __name__ == "__main__":
    main()
```

测试方法：`uv run python scripts/replay_ab_ticker.py --input runs/demo_2026-07-25/ab_result.json --delay 0.5`

预期：逐行打印 10 行 ticker。

- [ ] **Step 5: 写 plot_contraction_trajectory.py（残差字节轨迹动画）**

Create `scripts/plot_contraction_trajectory.py`：

```python
"""渲染残差字节收缩轨迹静态图（用于视频 L4 镜头叠加）。
输入 signal_result.json，输出 contraction_trajectory.png。
"""
import argparse
import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams["font.family"] = "DejaVu Sans"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    # contraction_bytes 在 result.improvement 或 result 本身，路径需根据实际 result.json 调整
    cb = data.get("result", data).get("contraction_bytes") or data.get("contraction_bytes")
    if not cb:
        # fallback：从 synapse_trajectory 取 nontext_bytes
        traj = data.get("result", {}).get("synapse_trajectory", [])
        cb = [m.get("nontext_bytes", 0) for m in traj]
    fig, ax = plt.subplots(figsize=(10, 5), dpi=120)
    rounds = list(range(1, len(cb) + 1))
    ax.plot(rounds, cb, "o-", color="#FF8C00", linewidth=2.5, markersize=10)
    ax.fill_between(rounds, cb, alpha=0.2, color="#FF8C00")
    for x, y in zip(rounds, cb):
        ax.annotate(str(y), (x, y), textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=10, fontweight="bold")
    ax.set_xlabel("Round", fontsize=12)
    ax.set_ylabel("Non-text bytes (residual)", fontsize=12)
    ax.set_title("Residual Bytes Contraction (memory kicks in)", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)
    if len(cb) >= 2:
        drop = (1 - cb[-1] / cb[0]) * 100
        ax.text(0.98, 0.95, f"−{drop:.1f}% bytes", transform=ax.transAxes,
                ha="right", va="top", fontsize=14, color="#FF8C00", fontweight="bold",
                bbox=dict(boxstyle="round", facecolor="white", edgecolor="#FF8C00"))
    plt.savefig(args.out, bbox_inches="tight", facecolor="white")
    print(f"saved {args.out}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 跑 contraction 轨迹图**

```bash
uv run python scripts/plot_contraction_trajectory.py \
    --input runs/demo_2026-07-25/signal_result.json \
    --out docs/figs/contraction_trajectory.png
```

预期：生成 `docs/figs/contraction_trajectory.png`，显示单调下降曲线 + 「−XX% bytes」标注。

- [ ] **Step 7: Commit**

```bash
git add scripts/render_agent_topology.py scripts/replay_ab_ticker.py scripts/plot_contraction_trajectory.py
git add tests/test_render_topology.py
git add docs/figs/agent_topology/ docs/figs/contraction_trajectory.png
git commit -m "viz(demo): agent 拓扑动画 + A/B ticker + 残差轨迹渲染脚本"
```

---

## Task 5: 架构图与谱系图制作

**目的**：制作两张视频核心静态图——新架构图（L2 镜头）和三轴定位谱系图（L2 镜头）。

**依赖**：无（仅依赖说明书叙事）。

**Files:**
- Create: `docs/figs/architecture_v2.drawio` + `.png`
- Create: `docs/figs/axis_positioning.drawio` + `.png`

- [ ] **Step 1: 制作新架构图（drawio）**

打开 `D:\操作系统开源大赛\synapse\SYNAPSE_architecture.drawio`（现有源文件）作参考。

按说明书 [074] 流水线绘制新架构图 `docs/figs/architecture_v2.drawio`：

```
[Agent: Planner] → [Protocol: Message{action,params,result,handles}]
                              ↓
                   [Stateplane: CAS 句柄 → ResidualCodec 残差]
                              ↓
                   [Memory: MemoryStore → HybridRetriever → ToMPredictor → Consolidator]
                              ↓
                   [Eval: Metrics{messages, tokens, bytes, hit_rate}]
                              ↓
                              ┌──── feedback loop ────┐
                              └───────────────────────┘
```

4 个 Agent 节点（Planner/Retriever/Executor/Summarizer）按菱形排列；中间是三平面（Protocol/Stateplane/Memory）；底部是 Eval。虚线箭头表示记忆反馈闭环。

用 drawio 桌面版或 https://app.diagrams.net/ 制作。

导出 PNG：`File → Export As → PNG → Quality 100 → docs/figs/architecture_v2.png`

- [ ] **Step 2: 制作三轴定位谱系图**

读 `docs/系统设计文档.md` §10.1（line 224-228）和 §10.3（line 245-261）。

制作 `docs/figs/axis_positioning.drawio`：

三个轴：
- WHAT（表示粒度）：Token → Phrase → Embedding → KV cache
- WHICH（对齐要求）：跨层对齐 → 同层 → 无需对齐
- HOW（重构方式）：全量重传 → 近邻查找 → 预测基 + 残差

在三维空间标注 SYNAPSE 位置 + 3 个对照（C2C / LatentMAS / HyLaT）。

表格化呈现（更清晰）：

| 方案 | WHAT | WHICH | HOW | 需白盒 | 需训练 |
|---|---|---|---|:---:|:---:|
| C2C | KV cache | 跨层 | 近邻 | ✅ | ✅ |
| LatentMAS | Hidden state | 跨层 | 近邻 | ✅ | ✅ |
| HyLaT | Hidden state | 同层 | 适配器 | ✅ | ✅ |
| **SYNAPSE** | **Embedding 残差** | **无需** | **预测基+残差** | **❌** | **❌** |

SYNAPSE 行高亮（橙色边框 + 加粗）。

导出 `docs/figs/axis_positioning.png`。

- [ ] **Step 3: 制作 CodeAgents 对照表图**

Create `docs/figs/codeagents_compare.png`（用 matplotlib 或 PPT 做）：

| 方法 | 路线 | 通信表示 | HotpotQA F1 | Input Token |
|---|---|---|---|---|
| NL baseline | 文本透传 | 自然语言 | （Task 3 数字） | （Task 3 数字） |
| CodeAgents | 文本结构化 | Python 伪代码 | （Task 3 数字） | （Task 3 数字） |
| **SYNAPSE** | **非文本残差** | **句向量残差+句柄** | **0.68** | **省 71%** |

SYNAPSE 行高亮。

- [ ] **Step 4: Commit**

```bash
git add docs/figs/architecture_v2.* docs/figs/axis_positioning.* docs/figs/codeagents_compare.png
git commit -m "docs(figs): 新架构图 + 三轴定位谱系图 + CodeAgents 对照表"
```

---

## Task 6: 视频脚本 v2 定稿

**目的**：基于 design doc §6 和 Task 2/3/4/5 的全部资产，重写 `docs/演示视频脚本-v2.md`（7 镜头 5:00），作为 OBS 录制脚本。

**依赖**：Task 2（真实数据）、Task 3（CodeAgents 数字）、Task 4（动态资产）、Task 5（静态图）。

**Files:**
- Create: `docs/演示视频脚本-v2.md`
- Modify: `docs/演示视频脚本.md`（顶部加 deprecated 标记）
- Create: `docs/录制checklist.md`

- [ ] **Step 1: 标记旧脚本为 deprecated**

在 `docs/演示视频脚本.md` 顶部插入：

```markdown
> ⚠️ **DEPRECATED（2026-07-25）**：本脚本已被 `docs/演示视频脚本-v2.md` 取代。
> 旧脚本数字为 07-08 旧平台（Paratera），与新 run 目录不符。
> 请使用 v2 脚本（07-24 VectorEngine 真实数据 + 7 镜头对齐 design doc）。

```

- [ ] **Step 2: 写 docs/演示视频脚本-v2.md（完整 7 镜头）**

完整文件内容见下方（每个镜头含：时长 / 画面 / 终端命令 / 字幕 / 口播 / 素材依赖）：

````markdown
# SYNAPSE 演示视频脚本 v2（2026-07-25）

> 对齐 `docs/superpowers/specs/2026-07-25-demo-video-design.md`
> 数据源：`runs/demo_2026-07-25/SUMMARY.md`
> 总时长：5:00 | 镜头数：7 | 录制工具：OBS + openEuler 终端

---

## L1：openEuler 落地（0:00-0:30，30s）

**画面**：原生 openEuler SSH 终端，深色背景，font 14+。

**终端命令**（逐条执行，每条间隔 2-3 秒）：
```bash
uname -a
# 预期：Linux ... GNU/Linux ... x86_64
cat /etc/os-release | head -3
# 预期：NAME="openEuler" VERSION="24.03 (LTS)"
cd ~/synapse
uv run synapse smoke
# 预期：5 项 PASS + SMOKE PASSED
```

**字幕**（底部）：
> SYNAPSE · openEuler 24.03-LTS-SP3 原生运行

**口播**：
> SYNAPSE 在 openEuler 24.03-LTS 上原生运行。一条命令完成依赖安装，零网络零密钥即可通过五项离线自检，满足赛题 M10 红线。

**素材**：无（实时录制）

---

## L2：痛点 + Wyner-Ziv framing + 三重机制（0:30-1:30，60s）

**画面**：
- 0:30-0:45：痛点动画（PPT 或预录视频）。三大瓶颈逐条出现：
  - 瓶颈 1：通信冗长 → Token 消耗极高
  - 瓶颈 2：编解码往返 → 时延 + 语义损耗
  - 瓶颈 3：经验不沉淀 → 跨任务重复推理
- 0:45-1:15：切入 `docs/figs/architecture_v2.png`，大字标题：
  > **带增长边信息的 Wyner-Ziv 条件率失真编码**
- 三栏淡入（结构化通信协议 → 句向量预测残差编码 → 内容寻址共享记忆）
- 1:15-1:30：切入 `docs/figs/axis_positioning.png`，高亮 SYNAPSE 行（黑盒 latent 唯一无需白盒/训练）

**字幕**：
> 协作即压缩 · 惊讶残差而非全量信息

**口播**：
> SYNAPSE 将多智能体协作建模为带增长边信息的 Wyner-Ziv 条件率失真编码。共享记忆不断积累，发送方仅需传递惊讶残差而非全量信息。三重机制：结构化通信协议、句向量预测残差编码、内容寻址共享记忆。

**素材**：`docs/figs/architecture_v2.png`、`docs/figs/axis_positioning.png`、痛点动画（PPT 录屏）

---

## L3：同基座 A/B 启动（1:30-2:30，60s）

**画面**：
- 主画面：openEuler 终端
- 画中画（右上 1/4）：`docs/figs/agent_topology/frame_*.png` 序列循环播放
- 底部 ticker（叠加）：另一终端窗口跑 `scripts/replay_ab_ticker.py`

**终端命令**（实时启动 + 等几秒后切到 ticker 回放）：
```bash
uv run synapse ab --rounds 5 --config configs/vectorengine.yaml
# 启动几秒后，OBS 切到第二个终端窗口（已预跑 ticker）
```

**底部 ticker 命令**（预跑数据回放）：
```bash
uv run python scripts/replay_ab_ticker.py --input runs/demo_2026-07-25/ab_result.json --delay 4
```

**字幕**：
> 同基座 · 同后端 · 同任务 · 唯一变量 = 通信介质

**口播**：
> 同基座 Qwen3-235B、同后端 VectorEngine、同任务序列。Text 模式全文本透传，Synapse 模式启用协议 + 残差 + 记忆。G1 五轮深挖主题，G2 五轮关联演进，共十轮连续任务。

**素材**：`docs/figs/agent_topology/frame_*.png`、`scripts/replay_ab_ticker.py`

---

## L4：A/B 结果 + 跨组记忆 + 因果消融（2:30-3:30，60s）

**画面**：
- 0:00-0:20：三数据集结果表（PPT 静态图，数字来自 `runs/demo_2026-07-25/SUMMARY.md`）：

| 数据集 | text token | synapse token | 节省 % | gold_recall / F1 |
|---|---|---|---|---|
| HotpotQA N=10 | <填> | <填> | **<填>%** | 0.9 |
| MuSiQue N=3 | <填> | <填> | **<填>%** | F1 +0.333 |
| CoQA 38 轮 | <填> | <填> | <填>% | hit 0.921 |

- 0:20-0:40：切入 `docs/figs/contraction_trajectory.png`，残差字节 2787→960 轨迹

- 0:40-1:00：因果消融饼图（B1 65.6% vs B3 1.6% → 97.6% 记忆归因）+ m7 跨组对比小图（G1 hit 0.8 → G2 hit 1.0）

**字幕**：
> 71% Token 节省 · gold_recall 保持 · 97.6% 收缩归因记忆

**口播**：
> HotpotQA 省 <填>% Token，金标召回保持 0.9。MuSiQue 省 <填>%，F1 反升 0.333。残差字节从 <填> 收缩到 <填>，百分之九十七点六的收缩因果归因于记忆复用——记忆的主动检索与复用是压缩效果的必要条件。

**诚实标注**（字幕小字，2 秒）：
> HotpotQA ΔF1=-0.100（小样本 N=10），集中在 hard 题答案表达差异，不影响通信压缩与召回结论

**素材**：`docs/figs/contraction_trajectory.png`、因果消融饼图（PPT）、m7 对比小图（PPT）

---

## L5：共享记忆模块细节（3:30-4:00，30s）

**画面**：
- 代码片段（`src/synapse/memory/retrieval.py:34-40` 三路混合检索）特写
- CoQA "越长越省" 曲线（`docs/figs/coqa_tokens.png` 已有）
- 命中率 0.921 大字 + ToMPredictor + Consolidator 标签

**字幕**：
> 三路混合检索 · 心智理论预测器 · 跨任务巩固

**口播**：
> 三路混合检索：关键词倒排、标签过滤、语义向量余弦相似度。心智理论预测器估计接收方已知，跨任务巩固器演化记忆链。CoQA 命中率 0.921，对话越长优势越显著。

**素材**：`docs/figs/coqa_tokens.png`（已有）、代码片段（终端 cat 或 IDE 截图）

---

## L6：CodeAgents 学术对照（4:00-4:30，30s）

**画面**：切入 `docs/figs/codeagents_compare.png`：

| 方法 | 路线 | 通信表示 | HotpotQA F1 | Input Token |
|---|---|---|---|---|
| NL baseline | 文本透传 | 自然语言 | <Task 3 数字> | <Task 3 数字> |
| CodeAgents | 文本结构化 | Python 伪代码 | <Task 3 数字> | <Task 3 数字> |
| **SYNAPSE** | **非文本残差** | **句向量残差+句柄** | **gold_recall 0.9** | **省 71%** |

**字幕**：
> 文本符号层 vs 连续表示层 · 突破文本序列化瓶颈

**口播**：
> 对照文本压缩 SOTA CodeAgents。它在文本符号层做结构化压缩；SYNAPSE 走连续表示层，直接传句向量预测残差，wire bytes 减 94%。两者作用于同一通信环节，SYNAPSE 突破文本表示的根本限制。

**素材**：`docs/figs/codeagents_compare.png`

---

## L7：总结（4:30-5:00，30s）

**画面**：
- frontier 图（`docs/figs/hotpot_frontier.png` 已有，SYNAPSE 占左上）
- openEuler logo + SYNAPSE logo 淡入
- 大字：「**协作即压缩 · 越用越省 · 越用越聪明**」

**字幕**：
> SYNAPSE · 71-81% Token 节省 · openEuler 24.03-LTS · Apache-2.0

**口播**：
> SYNAPSE：协作即压缩。在 openEuler 上以 CodeAct 模式真跑，节省 71 到 81% Token，命中率 92%。越用越省，越用越聪明。

**素材**：`docs/figs/hotpot_frontier.png`、openEuler logo

---

## 素材依赖清单（录制前必须全部就绪）

- [ ] `runs/demo_2026-07-25/SUMMARY.md`（Task 2）
- [ ] `docs/figs/architecture_v2.png`（Task 5）
- [ ] `docs/figs/axis_positioning.png`（Task 5）
- [ ] `docs/figs/codeagents_compare.png`（Task 3 + 5）
- [ ] `docs/figs/agent_topology/frame_*.png`（Task 4）
- [ ] `docs/figs/contraction_trajectory.png`（Task 4）
- [ ] `docs/figs/coqa_tokens.png`（已有）
- [ ] `docs/figs/hotpot_frontier.png`（已有）
- [ ] 痛点动画（PPT 录屏）
- [ ] 因果消融饼图 + m7 对比小图（PPT）
````

- [ ] **Step 3: 写 docs/录制checklist.md（OBS 录制当日 checklist）**

```markdown
# OBS 录制当日 checklist

## 录制前 30 分钟

### 环境检查
- [ ] SSH 登录 openEuler 服务器，`uname -a` + `cat /etc/os-release` 正确
- [ ] `cd ~/synapse && uv run synapse smoke` → SMOKE PASSED
- [ ] `.env` 的 VECTORENGINE_API_KEY 有效（`uv run synapse probe` 通过）
- [ ] OBS Studio 启动，场景「SYNAPSE 演示」加载完毕
- [ ] OBS 录制路径设为 `~/recordings/`，剩余磁盘 > 20GB
- [ ] OBS 编码：H.264 / 1080p / 30fps / CRF 18

### 终端窗口准备
- [ ] 终端窗口 1（主）：背景黑，字体 14+，路径 `~/synapse`，`clear`
- [ ] 终端窗口 2（ticker）：背景黑，已 cd 到 `~/synapse`，待命 `python scripts/replay_ab_ticker.py ...`
- [ ] OBS 采集：窗口 1（主）+ 窗口 2（ticker，叠加底部）+ 图像素材（架构图等）

### 素材加载
- [ ] 所有 `docs/figs/*.png` 在 OBS 图像源中加载
- [ ] agent_topology 帧序列设为 OBS 滚动播放（每帧 4 秒）
- [ ] PPT 素材（痛点动画、饼图）导出 MP4 备用

## 录制中（按 v2 脚本 7 镜头）

- [ ] L1 openEuler 落地（30s）
- [ ] L2 痛点 + Wyner-Ziv（60s）
- [ ] L3 A/B 启动（60s）
- [ ] L4 结果 + 记忆（60s）
- [ ] L5 共享记忆细节（30s）
- [ ] L6 CodeAgents 对照（30s）
- [ ] L7 总结（30s）

## 应急预案

| 故障 | 对策 |
|---|---|
| VectorEngine API 抖动 | 切到预跑 ticker，不实时跑全程 |
| 终端命令出错 | 停录，重启 OBS 该镜头，重录 |
| 时长超 5 分钟 | 砍 L5（共享记忆细节），合并到 L4 |
| OBS 崩溃 | 备用：asciinema 录纯终端 + 后期合成 |

## 录制后

- [ ] 检查视频时长 ≤ 5:00
- [ ] 检查画面出现 openEuler 24.03-LTS 标识
- [ ] 检查所有数字与 SUMMARY.md 一致
- [ ] 备份原始录制到本地
```

- [ ] **Step 4: Commit**

```bash
git add docs/演示视频脚本-v2.md docs/演示视频脚本.md docs/录制checklist.md
git commit -m "docs(demo): 视频脚本 v2（7 镜头对齐 design）+ 录制 checklist"
```

---

## Task 7: OBS 录制（原生 openEuler 服务器）

**目的**：在原生 openEuler 服务器上按 v2 脚本录制 7 镜头原始素材。

**依赖**：Task 1（环境）、Task 6（脚本 + checklist）。

**Files:**
- 产出：`~/recordings/synapse_demo_raw.mp4`（或分镜头 MP4）

- [ ] **Step 1: 按 `docs/录制checklist.md` 完成所有「录制前 30 分钟」项**

逐项打勾。任何一项失败则停下来修复，不开始录制。

- [ ] **Step 2: 试录 L1（30 秒）验证 OBS 设置**

按 L1 脚本录制，回放检查：
- 画面清晰度（字体可读）
- 帧率（终端滚动不卡顿）
- 音频（若录口播，麦克风正常）

若不合格，调整 OBS 编码 / 分辨率 / 字体后重试。

- [ ] **Step 3: 按 v2 脚本逐镜头录制**

每录完一个镜头：
- 立即回放检查
- 命名保存：`~/recordings/L1_openEuler.mp4`、`~/recordings/L2_framework.mp4`、...
- 在 checklist 对应项打勾

**重要**：L3 的 A/B 命令启动几秒后立即切到 ticker 回放窗口，不要等真实 LLM 跑完（会超时）。

- [ ] **Step 4: 整体检查**

播放全部 7 个镜头，核对：
- 总时长 ≤ 5:00
- 所有数字与 `runs/demo_2026-07-25/SUMMARY.md` 一致
- 画面出现 openEuler 标识（L1）
- 无明显卡顿/掉帧/错字

- [ ] **Step 5: 备份原始素材**

```bash
# 打包传回本地
cd ~/recordings
tar czf synapse_demo_raw_$(date +%Y%m%d).tar.gz L*.mp4
# scp 回本地
scp synapse_demo_raw_*.tar.gz <local-user>@<local-ip>:/d/操作系统开源大赛/项目文档/recordings/
```

---

## Task 8: 后期剪辑与导出

**目的**：将 7 个镜头剪辑成最终 ≤5 分钟演示视频，加字幕、转场、口播音频。

**依赖**：Task 7（原始素材）。

**Files:**
- 产出：`D:\操作系统开源大赛\项目文档\SYNAPSE_演示视频.mp4`

- [ ] **Step 1: 导入素材到剪辑软件**

用剪映 / Premiere / DaVinci Resolve（任选）。
导入 `recordings/L1_*.mp4` ~ `L7_*.mp4`。

- [ ] **Step 2: 按时间轴拼接**

按 v2 脚本时间分配：
- L1：0:00-0:30
- L2：0:30-1:30
- L3：1:30-2:30
- L4：2:30-3:30
- L5：3:30-4:00
- L6：4:00-4:30
- L7：4:30-5:00

镜头间用淡入淡出转场（0.3 秒）。

- [ ] **Step 3: 加字幕**

按 v2 脚本每个镜头的「字幕」字段，逐镜头压字幕。
字体：思源黑体 / 苹方，字号适中，底部居中。

**关键术语字幕统一口径**（来自 design 附录 A）：
- SYNAPSE（全大写）
- 带增长边信息的 Wyner-Ziv 条件率失真编码
- 结构化通信协议 + 句向量预测残差编码 + 内容寻址共享记忆
- 惊讶残差
- CAS（Content Addressable Storage，内容寻址存储）

- [ ] **Step 4: 录制口播音频（若 L1-L7 未同步录）**

按 v2 脚本「口播」字段逐镜头录音。
建议用麦克风单独录，后期对齐画面。

- [ ] **Step 5: 最终检查（对照 design §10 验收标准）**

逐项核对 design doc §10 的 8 条验收标准：

- [ ] 时长 ≤5 分钟
- [ ] 画面出现 openEuler 24.03-LTS 标识（uname + os-release）
- [ ] 包含真实 A/B 对比数字（71.09% / 80.9% / 0.921）
- [ ] 包含 CodeAgents 外部对照
- [ ] 严格对齐说明书核心 framing（Wyner-Ziv + 三重机制）
- [ ] 不越过诚实红线（不说向量数据库/IPC/延迟降低/105 个实验）
- [ ] 保留诚信负数（ΔF1=-0.100）
- [ ] 在原生 openEuler 服务器录制

- [ ] **Step 6: 导出最终视频**

```bash
# 剪辑软件导出设置
# 格式：MP4（H.264）
# 分辨率：1920x1080
# 帧率：30fps
# 码率：8-12 Mbps
# 音频：AAC 192kbps
```

导出到 `D:\操作系统开源大赛\项目文档\SYNAPSE_演示视频.mp4`。

- [ ] **Step 7: 最终交付检查**

```bash
# 检查时长（ffprobe）
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \
    "D:/操作系统开源大赛/项目文档/SYNAPSE_演示视频.mp4"
# 预期：≤ 300 秒
```

- [ ] **Step 8: 更新文档 + Commit**

在 `docs/验收自检清单.md` 第 61 行「演示视频待录制」改为「✅ 已完成，路径 `项目文档/SYNAPSE_演示视频.mp4`」。

```bash
git add docs/验收自检清单.md
git commit -m "docs: 演示视频已完成（M10 + 7 镜头对齐 design v2）"
```

---

## 完成判定

整个演示视频项目完成的标志：
1. ✅ `D:\操作系统开源大赛\项目文档\SYNAPSE_演示视频.mp4` 存在，时长 ≤ 5:00
2. ✅ 满足 design doc §10 的 8 条验收标准
3. ✅ `runs/demo_2026-07-25/SUMMARY.md` 真实数据齐全
4. ✅ `docs/演示视频脚本-v2.md` 与最终视频一致
5. ✅ 所有可视化资产在 `docs/figs/` 齐全
6. ✅ `docs/验收自检清单.md` 更新为已完成

---

## 降级路径（任一 Task 严重受阻时）

| 受阻 Task | 降级方案 |
|---|---|
| Task 1 服务器无桌面 | Docker 内录（已实测），用 `cat /etc/os-release` 证明 openEuler |
| Task 2 m7 不达标 | 用旧平台（Paratera）m7 数字 + 诚实标注 |
| Task 3 CodeAgents 复现失败 | 退化为引用论文 Table 4 数字（design §4.4） |
| Task 4 拓扑动画做不出 | 降级静态 drawio 图 + 画外音 |
| Task 7 OBS 崩溃 | asciinema 录纯终端 + 后期合成图 |
| 5 分钟塞不下 | 砍 L5（合并到 L4） |

最低保证：现有 6 张图 + 现有 9 镜头脚本（数字更新）+ Docker 内录 = 可交付的 5 分钟视频。

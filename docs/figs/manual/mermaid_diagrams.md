# SYNAPSE 说明书 · Mermaid 流程图源码

> 用途：供项目说明书嵌入。GitHub / Typora / VSCode 预览可直接渲染；转 docx 需用 `mermaid-cli` 或 pandoc 的 mermaid 插件预先生成 PNG。
> 生成 PNG 命令（可选）：`mmdc -i 某图.mmd -o 某图.png -b transparent -w 1200`

---

## 图M1 · 核心正反馈闭环（Memory↗→Predict↑→Residual↓→Comm↓）

```mermaid
graph LR
    A([共享记忆积累<br/>M↗]) --> B[接收端状态预测<br/>Ŷ=f·M]
    B --> C[语义残差编码<br/>Z=Y−Ŷ]
    C --> D([通信开销降低<br/>Comm↓])
    D --> E[新经验沉淀<br/>写入记忆]
    E -.->|跨任务巩固| A
    style A fill:#2ECC71,stroke:#27AE60,color:#fff
    style B fill:#4A90E2,stroke:#2980B9,color:#fff
    style C fill:#FF8C00,stroke:#E67E22,color:#fff
    style D fill:#2ECC71,stroke:#27AE60,color:#fff
    style E fill:#9B59B6,stroke:#8E44AD,color:#fff
```

---

## 图M2 · 三档混合协议（发送方主动预判选档）

```mermaid
graph TD
    Start([发送方准备传递非文本状态]) --> Check{有预测基 B̂?}
    Check -->|无 / 首轮冷启动| R1[residual 档·零基<br/>编码大残差<br/>收缩序列正起点]
    Check -->|有| Sim{相似度 cos·Y,B̂}
    Sim -->|≥ 0.97 阈值| R2[residual 档<br/>仅传稀疏残差<br/>字节开销最小]
    Sim -->|< 阈值| EM[embedding 档<br/>退一档传量化向量+摘要<br/>仍结构化]
    R1 --> Send[发送句柄+残差]
    R2 --> Send
    EM --> Send
    Send --> Recv[接收方解码 + verify]
    Recv --> Verify{余弦相似度≥阈值?}
    Verify -->|是| OK([接受恢复结果])
    Verify -->|否·校验失败| Text[text 档回退<br/>传全量文本]
    Text --> OK
    style R1 fill:#FF8C00,stroke:#E67E22,color:#fff
    style R2 fill:#FF8C00,stroke:#E67E22,color:#fff
    style EM fill:#4A90E2,stroke:#2980B9,color:#fff
    style Text fill:#95A5A6,stroke:#7F8C8D,color:#fff
    style OK fill:#2ECC71,stroke:#27AE60,color:#fff
```

---

## 图M3 · Wyner-Ziv 编码示意（带增长边信息）

```mermaid
graph LR
    subgraph 发送端
        Y[目标状态 Y]
    end
    subgraph 共享记忆边信息
        M1[M₁] --> M2[M₂] --> M3[M₃...<br/>边信息持续增长]
    end
    subgraph 接收端
        Pred[预测器 ToM<br/>Ŷ=f·M]
        Recv[恢复状态]
    end
    Y -->|计算残差| Z[Z = Y −Ŷ<br/>惊讶残差]
    M3 --> Pred
    Pred -->|预测基 Ŷ| Z
    Z -->|仅传残差| Recv
    Pred -->|加残差恢复| Recv
    style Z fill:#FF8C00,stroke:#E67E22,color:#fff
    style M3 fill:#2ECC71,stroke:#27AE60,color:#fff
    style Pred fill:#4A90E2,stroke:#2980B9,color:#fff
```

> 可达速率下界：**R = H(Y | B̂ⱼ) = H(Y|Bⱼ) + Δ**，其中 Δ = I(Y;Bⱼ|B̂ⱼ) ≥ 0 为 ToM 失配惩罚；当预测准确（B̂ⱼ→Bⱼ）时 Δ→0，速率趋于 Wyner-Ziv 信息地板。

---

## 图M4 · 五模块系统架构（数据流 ↓ 记忆反哺 ↑）

```mermaid
graph TB
    subgraph RT[① 多Agent运行时 runtime/]
        P[Planner 规划]
        R[Retriever 检索]
        E[Executor CodeAct执行]
        S[Summarizer 总结]
    end
    subgraph PR[② 协议解析与调度 protocol/]
        MSG[Message Schema]
        CNR[CNR 能力协商]
        SCH[Scheduler 路由]
    end
    subgraph SP[③ 状态交换数据平面 stateplane/]
        CAS[CAS 内容寻址]
        RES[ResidualCodec 残差编解码]
        VLC[VLC 校验回退]
    end
    subgraph MM[④ 共享记忆与检索 memory/]
        RET[HybridRetriever 三路混合]
        TOM[ToMPredictor 心智预测]
        CON[Consolidator 巩固器]
    end
    subgraph EV[⑤ 评测与度量 eval/]
        AB[ABRunner A/B双模式]
        MET[Metrics 多维统计]
    end
    P --> R --> E --> S
    RT -.->|结构化消息| PR
    PR -.->|状态引用| SP
    SP -.->|预测基| MM
    MM -.->|边信息| SP
    EV -.->|统计| RT
    style RT fill:#4A90E2,stroke:#2980B9,color:#fff
    style PR fill:#9B59B6,stroke:#8E44AD,color:#fff
    style SP fill:#FF8C00,stroke:#E67E22,color:#fff
    style MM fill:#2ECC71,stroke:#27AE60,color:#fff
    style EV fill:#F39C12,stroke:#E67E22,color:#fff
```

---

## 图M5 · Verified Lossy Coordination 流程

```mermaid
graph LR
    A[发送方<br/>生成预测残差 Z] -->|压缩传输| B[接收方<br/>用共享记忆同一证据重嵌入得真值]
    B --> C{比对余弦相似度<br/>D·Y,Ŷ}
    C -->|误差 < 阈值| D([接受恢复结果])
    C -->|关键语义偏差| E[触发校验回退]
    E --> F1[请求更高精度残差]
    E --> F2[回退全量文本]
    E --> F3[更新共享记忆]
    F1 --> D
    F2 --> D
    style A fill:#FF8C00,stroke:#E67E22,color:#fff
    style D fill:#2ECC71,stroke:#27AE60,color:#fff
    style E fill:#E74C3C,stroke:#C0392B,color:#fff
```

> 静默损坏率：**0**（有校验）vs **16/16 全错**（无校验基线）。

---

## 使用说明

- 上述 mermaid 代码块可直接粘贴到支持 mermaid 的 md 编辑器（Typora/VSCode/Obsidian）渲染。
- 若需转 docx，推荐用 mermaid-cli 预渲染：
  ```bash
  npm install -g @mermaid-js/mermaid-cli
  mmdc -i mermaid_diagrams.md -o mermaid_render.html   # 或逐图导出 PNG
  ```
- 也可在 Word 中插入对象，或截图后作为图片粘贴。

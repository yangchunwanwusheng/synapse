# SYNAPSE 源码与复现入口

本目录包含 SYNAPSE 的可安装 Python 包、离线测试、公开数据样例和 openEuler 容器配置。项目总览、机制说明与实验结论见仓库根目录的 `README.md`。

## 环境要求

- Python 3.11 或更高版本
- `uv` 包管理器
- 仅真实 API 实验需要密钥；离线自检和单元测试不需要网络或密钥

## 快速验证

```bash
uv sync --locked --extra dev --no-editable
uv run --no-sync ruff check .
uv run --no-sync pytest -q
uv run --no-sync synapse smoke
```

Windows PowerShell 可执行：

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
uv sync --locked --extra dev --no-editable
uv run --no-sync ruff check .
uv run --no-sync pytest -q
uv run --no-sync synapse smoke
```

仓库父目录含中文时，Python 3.11 会按系统 locale 读取 editable-install 的 `.pth`，可能在启动阶段出现 GBK 解码错误。统一门禁使用 `--no-editable` 避开绝对路径 `.pth`；PowerShell 脚本同时设置进程级 UTF-8 输入输出环境，并在结束后恢复。

## AF_UNIX 控制面

控制面可选用 Linux/openEuler `AF_UNIX` 传输：4 字节长度前缀保证 framing，发送并发、
超时、重复关闭、对端死亡和截断帧均有显式语义。端到端复验见
[`scripts/probe_unix_transport.py`](scripts/probe_unix_transport.py)；边界与故障矩阵见
[`../docs/工程化基线.md`](../docs/工程化基线.md)。当前不承诺自动重连或背压策略。

## openEuler 容器验证

```bash
docker build -t synapse:local .
docker run --rm synapse:local
```

容器默认执行零密钥离线 smoke。真实 API 实验需先复制 `.env.example` 为 `.env`，填写密钥后通过 `--env-file .env` 注入；请勿把 `.env`、密钥或访问令牌提交到仓库。

## 目录说明

- `src/synapse/`：运行时、协议、状态平面、共享记忆与评测实现
- `tests/`：离线单元与集成测试
- `configs/`：离线和真实后端配置
- `data/`：可随仓复现的公开数据样例
- `scripts/`：数据获取与实验辅助脚本
- `Dockerfile`：openEuler 24.03-LTS-SP3 复现镜像

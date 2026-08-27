# SYNAPSE — openEuler 24.03-LTS-SP3 部署镜像（赛题 M10 指定版本）
# 基座 smolagents 为纯 Python 轻依赖（无 torch/transformers/langchain）→ openEuler 友好、镜像小。
# 默认入口 = 离线自检（零网络/零密钥，评审 `docker run` 即见 PASS）；真实实验经 .env 注入密钥。
FROM openeuler/openeuler:24.03-lts-sp3

# 系统层：Python 3.11（openEuler 24.03 自带）+ pip + shadow-utils（useradd，最小镜像默认无）
RUN dnf install -y python3 python3-pip shadow-utils && dnf clean all

# 统一用 uv 管理（项目约定）；强制系统 Python，构建期不下载托管解释器
RUN python3 -m pip install --no-cache-dir uv
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON=python3 \
    UV_NO_PROGRESS=1

WORKDIR /app

# 依赖清单先入层，利用构建缓存
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
# 核心(smolagents) + api(openai，真实 Paratera 路径)；不装 embed/vector(torch/faiss 重)，默认 hash 嵌入
RUN uv sync --frozen --no-dev --extra api --no-editable

COPY configs ./configs
COPY tests ./tests
COPY scripts ./scripts

# 非 root 运行（最小权限；root 仅用于上面的系统安装/依赖同步）
RUN useradd -r -u 1001 -m -d /home/synapse synapse && chown -R synapse:synapse /app
USER synapse

# 健康检查 = 离线 smoke（零依赖外部服务）
HEALTHCHECK --interval=1h --timeout=120s --retries=1 \
    CMD ["uv", "run", "--no-sync", "synapse", "smoke"]

# 入口=项目 CLI；默认离线自检。真实实验：
#   docker run --rm --env-file .env synapse signal --rounds 10
ENTRYPOINT ["uv", "run", "--no-sync", "synapse"]
CMD ["smoke"]

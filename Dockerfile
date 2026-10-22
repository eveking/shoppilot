# ---- 阶段 1：构建 React 聊天窗 ----
FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

# ---- 阶段 2：Python 运行时（uv 官方镜像）----
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 先装依赖，利用 Docker 层缓存
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY --from=web-build /web/dist ./web/dist
RUN uv sync --no-dev

EXPOSE 8000
CMD [".venv/bin/uvicorn", "shoppilot.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

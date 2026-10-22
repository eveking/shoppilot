"""ShopPilot 应用工厂：装配全部模块与接缝的内置实现。"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from shoppilot.adapters.mock_shop import MockShopAdapter
from shoppilot.api.routes import router
from shoppilot.contrib.aftersales import AftersalesToolSet
from shoppilot.contrib.orders import OrdersToolSet
from shoppilot.core.tools import ToolRegistry
from shoppilot.identity.provider import HmacIdentityProvider, MockIdentityProvider
from shoppilot.llm.client import LLMClient
from shoppilot.settings import Settings
from shoppilot.storage.database import make_engine_and_factory
from shoppilot.storage.migrations import run_migrations
from shoppilot.storage.repository import ChatRepository

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _mount_web_dist(app: FastAPI) -> None:
    """托管 React 聊天窗构建产物（示例集成，存在才挂载）。"""
    for base in (_REPO_ROOT, Path.cwd()):
        dist = base / "web" / "dist"
        if dist.is_dir():
            app.mount("/", StaticFiles(directory=dist, html=True), name="web")
            logger.info("已托管聊天窗静态资源: %s", dist)
            return
    logger.info("未找到 web/dist，聊天窗未托管（可只使用 HTTP/SSE API）")


def _auto_migrate(settings: Settings) -> None:
    for base in (Path.cwd(), _REPO_ROOT):
        if (base / "alembic.ini").is_file():
            run_migrations(settings.database_url, base)
            return
    logger.warning("未找到 alembic.ini，跳过自动迁移；请手动执行 alembic upgrade head")


def create_app(
    settings: Settings | None = None,
    llm_client: LLMClient | None = None,
    toolsets: list | None = None,
) -> FastAPI:
    """构建应用。

    llm_client 供测试注入替身（依赖接受而非创建）；
    toolsets 为领域插件列表，缺省注册内置示例（orders/aftersales + Mock 适配器）；
    接入自己的订单系统时传入用真实适配器构造的 ToolSet（见 README「接入你的订单系统」）。
    """
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.auto_migrate:
            _auto_migrate(settings)
        yield
        await app.state.engine.dispose()

    app = FastAPI(title="ShopPilot", version="0.1.0", lifespan=lifespan)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    engine, factory = make_engine_and_factory(settings.database_url)
    identity_provider = (
        MockIdentityProvider()
        if settings.demo_mode
        else HmacIdentityProvider(settings.identity_secret)
    )

    # 领域插件：缺省用内置示例集成（Mock 适配器同时满足两个领域协议）
    if toolsets is None:
        mock_shop = MockShopAdapter()
        toolsets = [OrdersToolSet(mock_shop), AftersalesToolSet(mock_shop)]
    registry = ToolRegistry()
    for toolset in toolsets:
        registry.register(toolset)

    app.state.settings = settings
    app.state.engine = engine
    app.state.repo = ChatRepository(factory)
    app.state.identity_provider = identity_provider
    app.state.registry = registry
    app.state.llm = llm_client or LLMClient(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
    )

    app.include_router(router)
    _mount_web_dist(app)
    return app

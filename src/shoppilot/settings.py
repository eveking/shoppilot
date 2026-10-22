"""ShopPilot 运行时配置。

所有配置项均带 SHOPILOT_ 前缀，支持 .env 文件与环境变量。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHOPILOT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- LLM（OpenAI 兼容协议，默认 DeepSeek，见 ADR-0005）----
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # ---- 身份（见 ADR-0004）----
    # HMAC 签名密钥，生产环境必须更换
    identity_secret: str = "change-me-to-a-long-random-secret"
    # demo 模式：true 时创建会话可直接传 user_id（MockIdentityProvider）
    demo_mode: bool = True

    # ---- 存储（见 ADR-0007）----
    database_url: str = "sqlite+aiosqlite:///./data/shoppilot.db"

    # ---- Agent 行为 ----
    agent_max_tool_rounds: int = 8
    context_max_messages: int = 20
    tool_result_max_chars: int = 6000

    # ---- 其他 ----
    auto_migrate: bool = True
    cors_origins: list[str] = ["*"]

    @property
    def is_default_secret(self) -> bool:
        return self.identity_secret.startswith("change-me")

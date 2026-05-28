"""从环境变量加载应用配置。

这里集中管理演示模式、数据库/向量库地址、模型名称、文本切片参数和
浏览器跨域白名单等运行时开关。
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """供 FastAPI 路由和服务层统一使用的强类型配置对象。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding='utf-8', extra='ignore')
    APP_NAME: str = 'CampusAgent Pro API'
    DEBUG: bool = True
    DEMO_MODE: bool = True
    DATABASE_URL: str
    QDRANT_URL: str = 'http://localhost:6333'
    QDRANT_COLLECTION: str = 'campus_knowledge'
    OPENAI_BASE_URL: str = ''
    OPENAI_API_KEY: str = ''
    LLM_MODEL: str = 'deepseek-chat'
    EMBEDDING_MODEL: str = 'text-embedding-3-small'
    MODEL_PROVIDER: str = 'custom'
    DEEPSEEK_BASE_URL: str = 'https://api.deepseek.com/v1'
    DEEPSEEK_API_KEY: str = ''
    DEEPSEEK_LLM_MODEL: str = 'deepseek-chat'
    DEEPSEEK_EMBEDDING_MODEL: str = ''
    QWEN_BASE_URL: str = 'http://127.0.0.1:8001/v1'
    QWEN_API_KEY: str = ''
    QWEN_LLM_MODEL: str = 'qwen2.5-7b-instruct'
    QWEN_EMBEDDING_MODEL: str = ''
    TOP_K: int = 5
    CHUNK_SIZE: int = 700
    CHUNK_OVERLAP: int = 120
    CORS_ORIGINS: str = 'http://localhost:5173'

    # 既保留 Pydantic 原本支持的标准布尔解析，又额外支持项目自己的环境名称写法。
    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """允许用 release/prod/production 这类词快速关闭调试模式。"""
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    @property
    def cors_origins_list(self) -> List[str]:
        """把逗号分隔的跨域来源转换成 FastAPI 需要的列表格式。"""
        return [x.strip() for x in self.CORS_ORIGINS.split(',') if x.strip()]


settings = Settings()
"""
Pydantic 就是 Python 项目里负责“检查数据格式、转换数据类型、定义数据结构”的工具。
在项目里，它主要服务于 FastAPI：请求体、响应体、配置文件，都会用到它。
"""

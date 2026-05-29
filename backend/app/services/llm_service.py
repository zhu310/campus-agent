"""大模型和向量模型调用封装，支持运行时切换 OpenAI-compatible provider。"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import List

from openai import OpenAI

from app.config import settings


@dataclass(frozen=True)
class ModelProviderConfig:
    provider: str
    display_name: str
    base_url: str
    api_key: str
    llm_model: str
    embedding_model: str


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    provider: str
    display_name: str
    base_url: str
    api_key: str
    embedding_model: str
    configured: bool
    reason: str = ""


PROVIDER_ALIASES = {
    "deepseek": "deepseek",
    "qwen": "qwen_local",
    "qwen_local": "qwen_local",
    "qwenLocal": "qwen_local",
    "custom": "custom",
    "openai": "custom",
}

_active_provider = PROVIDER_ALIASES.get(settings.MODEL_PROVIDER, settings.MODEL_PROVIDER)
_last_runtime_error = ""
_last_embedding_error = ""
logger = logging.getLogger(__name__)


def _provider_config(provider: str | None = None) -> ModelProviderConfig:
    selected = PROVIDER_ALIASES.get(provider or _active_provider, provider or _active_provider)
    if selected == "deepseek":
        return ModelProviderConfig(
            provider="deepseek",
            display_name="DeepSeek API",
            base_url=settings.DEEPSEEK_BASE_URL,
            api_key=settings.DEEPSEEK_API_KEY,
            llm_model=settings.DEEPSEEK_LLM_MODEL or settings.LLM_MODEL,
            embedding_model=settings.DEEPSEEK_EMBEDDING_MODEL,
        )
    if selected == "qwen_local":
        return ModelProviderConfig(
            provider="qwen_local",
            display_name="本地 Qwen",
            base_url=settings.QWEN_BASE_URL,
            api_key=settings.QWEN_API_KEY,
            llm_model=settings.QWEN_LLM_MODEL or settings.LLM_MODEL,
            embedding_model=settings.QWEN_EMBEDDING_MODEL,
        )
    return ModelProviderConfig(
        provider="custom",
        display_name="自定义 OpenAI-compatible",
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        llm_model=settings.LLM_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
    )


def _embedding_config() -> EmbeddingProviderConfig:
    """Resolve embeddings independently from the active chat model provider."""
    if settings.EMBEDDING_BASE_URL and settings.EMBEDDING_API_KEY and settings.EMBEDDING_MODEL:
        return EmbeddingProviderConfig(
            provider="embedding_custom",
            display_name="独立 Embedding 服务",
            base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY,
            embedding_model=settings.EMBEDDING_MODEL,
            configured=True,
        )

    if not settings.EMBEDDING_PROVIDER:
        if settings.OPENAI_BASE_URL and settings.OPENAI_API_KEY and settings.EMBEDDING_MODEL:
            selected = "custom"
        elif settings.QWEN_BASE_URL and settings.QWEN_API_KEY and settings.QWEN_EMBEDDING_MODEL:
            selected = "qwen_local"
        elif settings.DEEPSEEK_BASE_URL and settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_EMBEDDING_MODEL:
            selected = "deepseek"
        else:
            selected = PROVIDER_ALIASES.get(_active_provider, _active_provider)
    else:
        selected = PROVIDER_ALIASES.get(settings.EMBEDDING_PROVIDER, settings.EMBEDDING_PROVIDER)
    if selected == "deepseek":
        configured = bool(settings.DEEPSEEK_BASE_URL and settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_EMBEDDING_MODEL)
        return EmbeddingProviderConfig(
            provider="deepseek",
            display_name="DeepSeek Embedding",
            base_url=settings.DEEPSEEK_BASE_URL,
            api_key=settings.DEEPSEEK_API_KEY,
            embedding_model=settings.DEEPSEEK_EMBEDDING_MODEL,
            configured=configured,
            reason="" if configured else "DeepSeek 未配置可用的 embedding 模型；请配置 EMBEDDING_BASE_URL/EMBEDDING_API_KEY 或切换 EMBEDDING_PROVIDER。",
        )
    if selected == "qwen_local":
        configured = bool(settings.QWEN_BASE_URL and settings.QWEN_API_KEY and settings.QWEN_EMBEDDING_MODEL)
        return EmbeddingProviderConfig(
            provider="qwen_local",
            display_name="本地 Qwen Embedding",
            base_url=settings.QWEN_BASE_URL,
            api_key=settings.QWEN_API_KEY,
            embedding_model=settings.QWEN_EMBEDDING_MODEL,
            configured=configured,
            reason="" if configured else "本地 Qwen 未配置 QWEN_EMBEDDING_MODEL。",
        )
    configured = bool(settings.OPENAI_BASE_URL and settings.OPENAI_API_KEY and settings.EMBEDDING_MODEL)
    return EmbeddingProviderConfig(
        provider="custom",
        display_name="自定义 Embedding 服务",
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        embedding_model=settings.EMBEDDING_MODEL,
        configured=configured,
        reason="" if configured else "未配置可用的 OpenAI-compatible embedding 服务。",
    )


def _client_for(config: ModelProviderConfig) -> OpenAI | None:
    global _last_runtime_error
    if settings.DEMO_MODE or not config.base_url or not config.api_key:
        reason = "DEMO_MODE 已开启" if settings.DEMO_MODE else f"{config.display_name} 未配置 base_url 或 api_key"
        _last_runtime_error = reason
        return None
    _last_runtime_error = ""
    return OpenAI(base_url=config.base_url, api_key=config.api_key)


def _demo_embed(text: str, dim: int = 384) -> List[float]:
    data = hashlib.sha256(text.encode("utf-8")).digest()
    values = []
    for i in range(dim):
        values.append(((data[i % len(data)] / 255.0) * 2) - 1)
    return values


def set_active_provider(provider: str) -> dict:
    """Switch active provider for subsequent LLM calls without exposing secrets."""
    global _active_provider
    normalized = PROVIDER_ALIASES.get(provider)
    if not normalized:
        raise ValueError(f"Unsupported model provider: {provider}")
    config = _provider_config(normalized)
    if not config.base_url or not config.api_key:
        raise ValueError(f"{config.display_name} 未配置 base_url 或 api_key。")
    _active_provider = normalized
    return model_runtime_status()


def model_runtime_status() -> dict:
    current = _provider_config()
    embedding = _embedding_config()
    providers = []
    for key in ("deepseek", "qwen_local", "custom"):
        config = _provider_config(key)
        providers.append(
            {
                "provider": config.provider,
                "display_name": config.display_name,
                "base_url": config.base_url,
                "llm_model": config.llm_model,
                "embedding_model": config.embedding_model,
                "api_key_configured": bool(config.api_key),
                "active": config.provider == current.provider,
            }
        )
    return {
        "mode": "demo" if settings.DEMO_MODE else "real",
        "active_provider": current.provider,
        "display_name": current.display_name,
        "base_url": current.base_url,
        "llm_model": current.llm_model,
        "api_key_configured": bool(current.api_key),
        "embedding_provider": embedding.provider,
        "embedding_display_name": embedding.display_name,
        "embedding_base_url": embedding.base_url,
        "embedding_model": embedding.embedding_model,
        "embedding_configured": embedding.configured,
        "embedding_reason": embedding.reason,
        "providers": providers,
        "local_model_compatible": True,
        "degraded": bool(settings.DEMO_MODE or _last_runtime_error or not current.api_key or not embedding.configured or _last_embedding_error),
        "last_error": _last_runtime_error,
        "last_embedding_error": _last_embedding_error,
    }


def embed_texts(texts: list[str]) -> list[list[float]]:
    global _last_embedding_error
    config = _embedding_config()
    if settings.DEMO_MODE:
        _last_embedding_error = "DEMO_MODE 已开启，未调用真实 embedding 服务"
        return [_demo_embed(t) for t in texts]
    if not config.configured:
        _last_embedding_error = config.reason
        raise RuntimeError(config.reason)
    client = OpenAI(base_url=config.base_url, api_key=config.api_key)
    try:
        response = client.embeddings.create(model=config.embedding_model, input=texts)
        _last_embedding_error = ""
        return [item.embedding for item in response.data]
    except Exception as exc:
        _last_embedding_error = f"Embedding 调用失败：{exc}"
        logger.warning("Embedding provider failed.", exc_info=True)
        raise RuntimeError(_last_embedding_error) from exc


def chat_completion(system_prompt: str, user_prompt: str) -> str:
    global _last_runtime_error
    config = _provider_config()
    client = _client_for(config)
    if client is None:
        return ""
    try:
        response = client.chat.completions.create(
            model=config.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        _last_runtime_error = f"LLM 调用失败：{exc}"
        logger.warning("LLM provider failed; returning empty answer for transparent fallback.", exc_info=True)
        return ""

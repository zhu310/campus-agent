"""大模型和向量模型调用封装，支持运行时切换 OpenAI-compatible provider。"""

from __future__ import annotations

import hashlib
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


PROVIDER_ALIASES = {
    "deepseek": "deepseek",
    "qwen": "qwen_local",
    "qwen_local": "qwen_local",
    "qwenLocal": "qwen_local",
    "custom": "custom",
    "openai": "custom",
}

_active_provider = PROVIDER_ALIASES.get(settings.MODEL_PROVIDER, settings.MODEL_PROVIDER)


def _provider_config(provider: str | None = None) -> ModelProviderConfig:
    selected = PROVIDER_ALIASES.get(provider or _active_provider, provider or _active_provider)
    if selected == "deepseek":
        return ModelProviderConfig(
            provider="deepseek",
            display_name="DeepSeek API",
            base_url=settings.DEEPSEEK_BASE_URL,
            api_key=settings.DEEPSEEK_API_KEY,
            llm_model=settings.DEEPSEEK_LLM_MODEL or settings.LLM_MODEL,
            embedding_model=settings.DEEPSEEK_EMBEDDING_MODEL or settings.EMBEDDING_MODEL,
        )
    if selected == "qwen_local":
        return ModelProviderConfig(
            provider="qwen_local",
            display_name="本地 Qwen",
            base_url=settings.QWEN_BASE_URL,
            api_key=settings.QWEN_API_KEY,
            llm_model=settings.QWEN_LLM_MODEL or settings.LLM_MODEL,
            embedding_model=settings.QWEN_EMBEDDING_MODEL or settings.EMBEDDING_MODEL,
        )
    return ModelProviderConfig(
        provider="custom",
        display_name="自定义 OpenAI-compatible",
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        llm_model=settings.LLM_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
    )


def _client_for(config: ModelProviderConfig) -> OpenAI | None:
    if settings.DEMO_MODE or not config.base_url or not config.api_key:
        return None
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
        "embedding_model": current.embedding_model,
        "api_key_configured": bool(current.api_key),
        "providers": providers,
        "local_model_compatible": True,
    }


def embed_texts(texts: list[str]) -> list[list[float]]:
    config = _provider_config()
    client = _client_for(config)
    if client is None or not config.embedding_model:
        return [_demo_embed(t) for t in texts]
    try:
        response = client.embeddings.create(model=config.embedding_model, input=texts)
        return [item.embedding for item in response.data]
    except Exception:
        return [_demo_embed(t) for t in texts]


def chat_completion(system_prompt: str, user_prompt: str) -> str:
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
    except Exception:
        return ""

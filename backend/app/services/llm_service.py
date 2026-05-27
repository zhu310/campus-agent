"""大模型和向量模型调用封装。

在 DEMO_MODE 或 API 配置缺失时自动降级到确定性的本地伪向量/本地答案，保证
无网络环境也能展示主要流程。
"""

import hashlib
from typing import List
from openai import OpenAI
from app.config import settings


client = None
if not settings.DEMO_MODE and settings.OPENAI_API_KEY and settings.OPENAI_BASE_URL:
    client = OpenAI(base_url=settings.OPENAI_BASE_URL, api_key=settings.OPENAI_API_KEY)


def _demo_embed(text: str, dim: int = 384) -> List[float]:
    data = hashlib.sha256(text.encode('utf-8')).digest()
    values = []
    for i in range(dim):
        values.append(((data[i % len(data)] / 255.0) * 2) - 1)
    return values


def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.DEMO_MODE or client is None:
        return [_demo_embed(t) for t in texts]
    try:
        response = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=texts)
        return [item.embedding for item in response.data]
    except Exception:
        # 部分聊天模型供应商不提供 embedding 接口，这里回退到稳定伪向量，
        # 让知识库入库和检索演示不被外部模型能力卡住。
        return [_demo_embed(t) for t in texts]


def chat_completion(system_prompt: str, user_prompt: str) -> str:
    if settings.DEMO_MODE or client is None:
        return ''
    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ''
    except Exception:
        return ''

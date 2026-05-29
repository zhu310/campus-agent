"""Qdrant 向量库访问与本地重排服务。"""

from typing import Any, Dict, List
import re
import logging

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import settings


client = QdrantClient(url=settings.QDRANT_URL)
logger = logging.getLogger(__name__)
_last_error = ""
_last_collection = ""
_last_available = False


def _safe_collection_name(vector_size: int) -> str:
    base = re.sub(r"[^A-Za-z0-9_]", "_", settings.QDRANT_COLLECTION).strip("_") or "campus_knowledge"
    return f"{base}_{vector_size}d"


def ensure_collection(vector_size: int) -> str:
    global _last_collection, _last_available, _last_error
    collection_name = _safe_collection_name(vector_size)
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        _last_collection = collection_name
        _last_available = True
        _last_error = ""
        return collection_name

    info = client.get_collection(collection_name)
    current_size = info.config.params.vectors.size
    if current_size != vector_size:
        raise ValueError(f"向量库 {collection_name} 维度为 {current_size}，当前向量维度为 {vector_size}。请使用新的 collection 或重建索引。")
    _last_collection = collection_name
    _last_available = True
    _last_error = ""
    return collection_name


def _point_vector_size(point: models.PointStruct) -> int:
    vector = point.vector
    if isinstance(vector, list):
        return len(vector)
    if isinstance(vector, dict):
        first = next(iter(vector.values()), [])
        return len(first) if isinstance(first, list) else 0
    return 0


def vector_runtime_status() -> dict[str, Any]:
    return {
        "url": settings.QDRANT_URL,
        "base_collection": settings.QDRANT_COLLECTION,
        "active_collection": _last_collection,
        "available": _last_available,
        "last_error": _last_error,
    }


def upsert_chunks(points: list[models.PointStruct]) -> bool:
    global _last_available, _last_error
    if points:
        try:
            vector_size = _point_vector_size(points[0])
            collection_name = ensure_collection(vector_size)
            client.upsert(collection_name=collection_name, points=points)
            _last_available = True
            _last_error = ""
            return True
        except Exception as exc:
            _last_available = False
            _last_error = f"向量写入失败：{exc}"
            logger.warning("Qdrant upsert failed; SQL chunks remain available.", exc_info=True)
            # Qdrant is an acceleration layer here. SQL chunks remain the reliable fallback.
            return False
    return False


def search(query_vector: list[float], limit: int = 5, document_ids: list[int] | None = None):
    global _last_available, _last_error
    try:
        collection_name = ensure_collection(len(query_vector))
    except Exception as exc:
        _last_available = False
        _last_error = f"向量检索准备失败：{exc}"
        return []
    query_filter = None
    if document_ids:
        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=document_ids),
                )
            ]
        )
    try:
        return client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
            query_filter=query_filter,
        )
    except Exception as exc:
        _last_available = False
        _last_error = f"向量检索失败：{exc}"
        logger.warning("Qdrant search failed; caller should use lexical fallback.", exc_info=True)
        return []


def rerank_hits(question: str, hits: List[Any], top_k: int = 5) -> List[Dict[str, Any]]:
    keywords = {token for token in question.lower().replace("？", " ").replace("?", " ").split() if token}
    ranked: List[Dict[str, Any]] = []
    for item in hits:
        payload = item.payload or {}
        text = payload.get("text", "")
        lowered = text.lower()
        lexical_score = sum(1 for token in keywords if token in lowered)
        heuristic_score = lexical_score + float(item.score or 0)
        ranked.append(
            {
                "document_id": payload.get("document_id"),
                "filename": payload.get("filename") or payload.get("title"),
                "chunk_id": payload.get("chunk_id"),
                "text": text,
                "score": float(item.score or 0),
                "rerank_score": heuristic_score,
                "location": payload.get("location", "片段"),
                "retrieval_source": "vector",
            }
        )
    ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return ranked[:top_k]

"""Qdrant 向量库访问与本地重排服务。"""

from typing import Any, Dict, List

from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.config import settings


client = QdrantClient(url=settings.QDRANT_URL)


def ensure_collection(vector_size: int):
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )
        return

    info = client.get_collection(settings.QDRANT_COLLECTION)
    current_size = info.config.params.vectors.size
    if current_size != vector_size:
        client.recreate_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        )


def upsert_chunks(points: list[models.PointStruct]):
    if points:
        try:
            client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
        except Exception:
            # Qdrant is an acceleration layer here. SQL chunks remain the reliable fallback.
            return


def search(query_vector: list[float], limit: int = 5, document_ids: list[int] | None = None):
    try:
        ensure_collection(len(query_vector))
    except Exception:
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
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
            query_filter=query_filter,
        )
    except Exception:
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
            }
        )
    ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return ranked[:top_k]

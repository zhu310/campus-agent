"""RAG chat routes with resilient hybrid retrieval and session logging."""

import json
import re
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models import ChatLog, Document, DocumentChunk, ToolLog
from app.schemas import AskRequest, AskResponse, Citation, TraceStep
from app.services.chat_service import default_suggestions, generate_answer, plan_user_request
from app.services.llm_service import chat_completion, embed_texts
from app.services.session_service import add_session_event
from app.services.text_utils import chunk_text
from app.services.vector_service import rerank_hits, search

router = APIRouter(prefix="/chat", tags=["chat"])


def _query_terms(question: str) -> set[str]:
    terms = {item for item in re.split(r"[\s,，。；;？?、]+", question) if item}
    compact = re.sub(r"\s+", "", question)
    for size in (2, 3, 4):
        for index in range(0, max(0, len(compact) - size + 1)):
            terms.add(compact[index:index + size])
    return terms


def _decompose_question(question: str) -> list[str]:
    """Use the LLM to expand one user question into retrieval sub-questions."""
    fallback = [question]
    broad_terms = ["截止时间", "申请条件", "提交材料", "提交方式", "注意事项"]
    if len(question) <= 12:
        fallback.extend(f"{question} {term}" for term in broad_terms[:3])
    if settings.DEMO_MODE:
        return fallback[:5]

    prompt = (
        "请把用户问题拆成最多5个适合检索通知/制度原文的子问题。"
        "只返回JSON数组字符串，不要解释。用户问题："
        f"{question}"
    )
    raw = chat_completion("你是检索查询改写器。", prompt)
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if not isinstance(parsed, list):
        return fallback[:5]
    queries = [question]
    for item in parsed:
        if isinstance(item, str) and item.strip() and item.strip() not in queries:
            queries.append(item.strip())
    return queries[:5]


def _load_chunks(req: AskRequest, db: Session) -> tuple[dict[int, str], list[DocumentChunk]]:
    selected_docs = db.query(Document).filter(Document.id.in_(req.document_ids)).all()
    docs = {doc.id: doc.filename for doc in selected_docs}
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id.in_(req.document_ids)).all()
    if chunks:
        return docs, chunks

    runtime_chunks: list[DocumentChunk] = []
    for doc in selected_docs:
        for idx, text in enumerate(chunk_text(doc.content or "", settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)):
            runtime_chunks.append(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_id=f"{doc.id}_runtime_{idx}",
                    text=text,
                    scenario=doc.scenario,
                    source_type=doc.source_type,
                )
            )
    return docs, runtime_chunks


def _lexical_hits(query: str, docs: dict[int, str], chunks: list[DocumentChunk], limit: int) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    ranked: list[dict[str, Any]] = []
    for chunk in chunks:
        text = chunk.text or ""
        score = sum(1 for term in terms if term and term in text)
        if score <= 0:
            continue
        ranked.append(
            {
                "document_id": chunk.document_id,
                "filename": docs.get(chunk.document_id, "选中文件"),
                "chunk_id": chunk.chunk_id,
                "text": text,
                "score": 0.0,
                "rerank_score": float(score) + 10.0,
                "location": "SQL切片",
            }
        )
    ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return ranked[:limit]


def _vector_hits(query: str, document_ids: list[int], limit: int) -> list[dict[str, Any]]:
    try:
        query_vector = embed_texts([query])[0]
        hits = search(query_vector, limit, document_ids=document_ids)
        return rerank_hits(query, hits, top_k=limit)
    except Exception:
        return []


def _merge_hits(all_hits: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    best_by_chunk: dict[tuple[int, str], dict[str, Any]] = {}
    for item in all_hits:
        key = (int(item.get("document_id") or 0), str(item.get("chunk_id") or ""))
        previous = best_by_chunk.get(key)
        if previous is None or float(item.get("rerank_score") or 0) > float(previous.get("rerank_score") or 0):
            best_by_chunk[key] = item
    merged = list(best_by_chunk.values())
    merged.sort(key=lambda item: float(item.get("rerank_score") or 0), reverse=True)
    return merged[:top_k]


def _top_documents(hits: list[dict[str, Any]], top_n: int = 3) -> list[int]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    coverage: dict[int, set[int]] = defaultdict(set)
    for item in hits:
        doc_id = int(item.get("document_id") or 0)
        if not doc_id:
            continue
        groups[doc_id].append(item)
        if "query_index" in item:
            coverage[doc_id].add(int(item["query_index"]))

    scored: list[tuple[float, int]] = []
    for doc_id, items in groups.items():
        scores = [float(item.get("rerank_score") or 0) for item in items]
        count_score = min(len(items), 12)
        max_score = max(scores) if scores else 0
        avg_score = sum(scores) / len(scores) if scores else 0
        coverage_score = len(coverage[doc_id]) * 3
        scored.append((count_score + max_score * 1.5 + avg_score + coverage_score, doc_id))
    scored.sort(reverse=True)
    return [doc_id for _, doc_id in scored[:top_n]]


def _retrieve(req: AskRequest, db: Session) -> tuple[list[dict[str, Any]], list[str], list[int]]:
    docs, chunks = _load_chunks(req, db)
    queries = _decompose_question(req.question)
    all_hits: list[dict[str, Any]] = []
    for index, query in enumerate(queries):
        per_query = _vector_hits(query, req.document_ids, 10) + _lexical_hits(query, docs, chunks, 10)
        for item in per_query:
            item["query_index"] = index
        all_hits.extend(per_query)

    if not all_hits:
        all_hits = _lexical_hits(req.question, docs, chunks, settings.TOP_K)

    top_doc_ids = _top_documents(all_hits, top_n=3)
    focused_hits = [item for item in all_hits if int(item.get("document_id") or 0) in top_doc_ids]
    return _merge_hits(focused_hits or all_hits, settings.TOP_K), queries, top_doc_ids


def _run_chat(req: AskRequest, db: Session) -> AskResponse:
    if not req.document_ids:
        raise HTTPException(status_code=400, detail="请先选择至少一份制度/通知文件，再发送问题。")

    plan = plan_user_request(req.question)
    intent = plan["intent"]
    reranked, search_queries, top_doc_ids = _retrieve(req, db)

    citations = [
        Citation(
            document_id=item["document_id"],
            filename=item["filename"],
            chunk_id=item["chunk_id"],
            text=item["text"],
            score=item.get("score"),
            rerank_score=item.get("rerank_score"),
            location=item.get("location"),
            highlight=(item.get("text") or "")[:160],
        )
        for item in reranked
    ]
    answer, fallback_used = generate_answer(req.question, reranked)
    suggestions = default_suggestions(req.question)
    trace = [
        TraceStep(
            title="意图识别",
            status="completed",
            detail=f"识别为 {intent}，计划工具：{', '.join(item['name'] for item in plan['tools'])}",
        ),
        TraceStep(
            title="多问题混合检索",
            status="completed",
            detail=f"拆分 {len(search_queries)} 个检索问题，重点分析文件ID：{top_doc_ids or '未命中'}",
        ),
        TraceStep(
            title="答案生成",
            status="completed",
            detail="已使用模型基于证据回答" if not fallback_used else "模型不可用，已使用本地证据兜底回答",
        ),
    ]

    chat_log = ChatLog(
        question=req.question,
        answer=answer,
        citations=[item.model_dump() for item in citations],
        scenario=req.scenario,
        status="fallback" if fallback_used else "completed",
    )
    db.add(chat_log)
    db.add(
        ToolLog(
            task_name="RAG问答",
            tool_name="search_knowledge",
            status="fallback" if fallback_used else "completed",
            input_payload={
                "question": req.question,
                "intent": intent,
                "document_ids": req.document_ids,
                "session_id": req.session_id,
            },
            output_payload={"citations": len(citations), "top_document_ids": top_doc_ids},
        )
    )
    if req.session_id:
        add_session_event(
            db,
            req.session_id,
            req.scenario,
            "answer",
            req.question,
            {
                "question": req.question,
                "answer": answer,
                "citations": [item.model_dump() for item in citations],
                "document_ids": req.document_ids,
                "trace": [item.model_dump() for item in trace],
            },
        )
    db.commit()

    return AskResponse(
        intent=intent,
        answer=answer,
        citations=citations,
        suggestions=suggestions,
        trace=trace,
        fallback_used=fallback_used,
    )


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, db: Session = Depends(get_db)):
    return _run_chat(req, db)


@router.post("/query", response_model=AskResponse)
def query(req: AskRequest, db: Session = Depends(get_db)):
    return _run_chat(req, db)


@router.post("/query-stream")
def query_stream(req: AskRequest, db: Session = Depends(get_db)):
    response = _run_chat(req, db)

    def event_stream():
        yield f"data: {json.dumps({'type': 'meta', 'intent': response.intent, 'fallback_used': response.fallback_used}, ensure_ascii=False)}\n\n"
        for index in range(0, len(response.answer), 18):
            yield f"data: {json.dumps({'type': 'delta', 'content': response.answer[index:index + 18]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'citations', 'citations': [item.model_dump() for item in response.citations]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': response.suggestions}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

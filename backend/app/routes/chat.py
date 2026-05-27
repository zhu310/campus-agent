"""RAG 问答接口。

先基于用户选中的制度/通知文档做向量召回，再叠加本地关键词召回作为兜底，
最后生成带引用依据的答案。
"""

import json
import re
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models import ChatLog, Document, DocumentChunk, ToolLog
from app.schemas import AskRequest, AskResponse, Citation, TraceStep
from app.services.chat_service import default_suggestions, detect_intent, generate_answer
from app.services.llm_service import embed_texts
from app.services.text_utils import chunk_text
from app.services.vector_service import rerank_hits, search

router = APIRouter(prefix="/chat", tags=["chat"])


SYNONYMS = {
    "参赛人员": ["参赛对象", "参赛范围", "报名对象", "人员", "学院", "院系"],
    "参赛对象": ["参赛人员", "参赛范围", "报名对象", "人员", "学院", "院系"],
    "限制": ["范围", "对象", "要求", "条件"],
    "学院": ["院系", "专业", "方向"],
}

SECTION_TERMS = {
    "参赛": ["参赛对象", "参赛人员", "参赛范围", "报名对象"],
    "对象": ["参赛对象", "报名对象", "适用对象"],
    "学院": ["参赛对象", "报名对象", "适用对象", "院系", "专业"],
}


def _query_terms(question: str) -> set[str]:
    """扩展用户问题中的检索词，提升中文短问句的本地召回效果。"""
    terms = {item for item in re.split(r"[\s,，。？?、]+", question) if item}
    for key, values in SYNONYMS.items():
        if key in question:
            terms.update(values)
    for key, values in SECTION_TERMS.items():
        if key in question:
            terms.update(values)
    for size in (2, 3, 4):
        for index in range(0, max(0, len(question) - size + 1)):
            terms.add(question[index:index + size])
    return terms


def _db_lexical_hits(req: AskRequest, db: Session, top_k: int) -> List[Dict[str, Any]]:
    """在数据库文本片段中做关键词召回，补足向量召回可能漏掉的明确字段。"""
    if not req.document_ids:
        return []
    selected_docs = db.query(Document).filter(Document.id.in_(req.document_ids)).all()
    docs = {doc.id: doc.filename for doc in selected_docs}
    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id.in_(req.document_ids))
        .all()
    )
    if not chunks:
        for doc in selected_docs:
            for idx, text in enumerate(chunk_text(doc.content or "", settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)):
                chunks.append(
                    DocumentChunk(
                        document_id=doc.id,
                        chunk_id=f"{doc.id}_runtime_{idx}",
                        text=text,
                        scenario=doc.scenario,
                        source_type=doc.source_type,
                    )
                )
    terms = _query_terms(req.question)
    ranked: List[Dict[str, Any]] = []
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
                "location": "文件分块",
            }
        )
    ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return ranked[:top_k]


def _merge_hits(primary: List[Dict[str, Any]], fallback: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """合并两路召回结果，并按重排分数去重后截断。"""
    merged: List[Dict[str, Any]] = []
    seen = set()
    for item in fallback + primary:
        key = (item.get("document_id"), item.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    merged.sort(key=lambda item: item["rerank_score"], reverse=True)
    return merged[:top_k]


def _run_chat(req: AskRequest, db: Session) -> AskResponse:
    """执行一次完整 RAG 问答，并把答案、引用和工具日志写入数据库。"""
    if not req.document_ids:
        raise HTTPException(status_code=400, detail="请先选择至少一份制度/通知文件，再发起问答。")
    intent = detect_intent(req.question)
    trace = [
        TraceStep(title="意图识别", status="completed", detail=f"识别为 {intent}"),
        TraceStep(title="混合检索", status="completed", detail="已结合 Qdrant 向量召回与选中文件关键词召回"),
    ]

    # 向量召回负责语义相似，关键词召回负责命中明确字段/章节名，两者互补。
    query_vector = embed_texts([req.question])[0]
    vector_hits = search(query_vector, settings.TOP_K, document_ids=req.document_ids)
    vector_ranked = rerank_hits(req.question, vector_hits, top_k=settings.TOP_K)
    lexical_ranked = _db_lexical_hits(req, db, top_k=settings.TOP_K)
    reranked = _merge_hits(vector_ranked, lexical_ranked, top_k=settings.TOP_K)

    citations = [
        Citation(
            document_id=item["document_id"],
            filename=item["filename"],
            chunk_id=item["chunk_id"],
            text=item["text"],
            score=item["score"],
            rerank_score=item["rerank_score"],
            location=item["location"],
            highlight=item["text"][:160],
        )
        for item in reranked
    ]

    answer, fallback_used = generate_answer(req.question, reranked)
    trace.append(
        TraceStep(
            title="答案生成",
            status="completed",
            detail="已完成基于证据的回答生成" if not fallback_used else "模型不可用，已使用本地证据规则回答",
        )
    )
    suggestions = default_suggestions(req.question)

    db.add(
        ChatLog(
            question=req.question,
            answer=answer,
            citations=[item.model_dump() for item in citations],
            scenario=req.scenario,
            status="fallback" if fallback_used else "completed",
        )
    )
    db.add(
        ToolLog(
            task_name="RAG问答",
            tool_name="search_knowledge",
            status="fallback" if fallback_used else "completed",
            input_payload={"question": req.question, "intent": intent, "document_ids": req.document_ids},
            output_payload={"citations": len(citations)},
        )
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
    """用 SSE 分段返回答案，兼容前端的流式展示体验。"""
    response = _run_chat(req, db)

    def event_stream():
        yield f"data: {json.dumps({'type': 'meta', 'intent': response.intent, 'fallback_used': response.fallback_used}, ensure_ascii=False)}\n\n"
        text = response.answer
        step = 18
        for index in range(0, len(text), step):
            yield f"data: {json.dumps({'type': 'delta', 'content': text[index:index + step]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'citations', 'citations': [item.model_dump() for item in response.citations]}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'suggestions', 'suggestions': response.suggestions}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

"""文档、任务、规则和操作日志相关的 SQLAlchemy ORM 模型。

这些表对应产品主流程：上传制度/材料文档、切分为可检索片段、执行问答/审核/
表单/流程规划，并把工具调用结果沉淀到看板和历史记录中。
"""

"""
models.py 一般定义的是数据库模型，也就是数据最终怎么存。
它关心表名、字段类型、索引、外键、默认值、数据库约束、关系映射等。
比如 SQLAlchemy model 里的字段会对应数据库表结构。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# 这里定义所有核心数据表：文档、切片、聊天记录、审核任务、表单填充、流程记录、规则、工具日志。

class SessionRecord(Base):
    """会话分组记录，为后续多会话工作流预留。"""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="比赛报名办理会话")
    scenario: Mapped[str] = mapped_column(String(100), default="competition_registration")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Document(Base):
    """上传或内置导入的源文件，保存解析后的完整文本。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="upload")
    source_type: Mapped[str] = mapped_column(String(50), default="knowledge_base")
    scenario: Mapped[str] = mapped_column(String(100), default="competition_registration")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document")


class DocumentChunk(Base):
    """可检索的文本片段，同时关联 SQL 记录和 Qdrant 向量点。"""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(String(100), default="competition_registration")
    source_type: Mapped[str] = mapped_column(String(50), default="knowledge_base")
    qdrant_point_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    document: Mapped[Document] = relationship(back_populates="chunks")


class ChatLog(Base):
    """保存 RAG 问答、答案和引用依据，供历史记录页面展示。"""

    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON)
    scenario: Mapped[str] = mapped_column(String(100), default="competition_registration")
    status: Mapped[str] = mapped_column(String(50), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditTask(Base):
    """用户发起的一次材料审核任务。"""

    __tablename__ = "audit_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    material_name: Mapped[str] = mapped_column(String(255))
    scenario: Mapped[str] = mapped_column(String(100), default="competition_registration")
    source_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    results: Mapped[list["AuditResult"]] = relationship(back_populates="task")


class AuditResult(Base):
    """审核任务对应的结构化审核结果。"""

    __tablename__ = "audit_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("audit_tasks.id"))
    level: Mapped[str] = mapped_column(String(50), default="pending")
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    task: Mapped[AuditTask] = relationship(back_populates="results")


class FormTemplate(Base):
    """表单预填服务使用的可复用表单结构。"""

    __tablename__ = "form_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    scenario: Mapped[str] = mapped_column(String(100), default="competition_registration")
    schema: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FormFillResult(Base):
    """根据材料文本生成的表单字段预填结果。"""

    __tablename__ = "form_fill_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_name: Mapped[str] = mapped_column(String(255), default="比赛报名表")
    source_text: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowRun(Base):
    """围绕校园办事场景生成的下一步办理计划。"""

    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    intent: Mapped[str] = mapped_column(String(100))
    request_text: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RulePolicy(Base):
    """材料审核时执行的可配置校验规则。"""

    __tablename__ = "rule_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(255))
    scenario: Mapped[str] = mapped_column(String(100), default="competition_registration")
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator: Mapped[str] = mapped_column(String(50))
    expected_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    severity: Mapped[str] = mapped_column(String(50), default="medium")
    suggestion: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ToolLog(Base):
    """通用工具调用日志，用于最近任务和数据看板统计。"""

    __tablename__ = "tool_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_name: Mapped[str] = mapped_column(String(255))
    tool_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="completed")
    input_payload: Mapped[dict] = mapped_column(JSON)
    output_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class HumanReviewRecord(Base):
    """人工复核记录，保存机器抽取结果、人工修正字段和复核状态。"""

    __tablename__ = "human_review_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    material_name: Mapped[str] = mapped_column(String(255))
    scenario: Mapped[str] = mapped_column(String(100), default="other")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    original_payload: Mapped[dict] = mapped_column(JSON)
    corrected_fields: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Backward-compatible alias for older imports in the project.
WorkflowLog = WorkflowRun

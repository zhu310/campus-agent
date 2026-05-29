"""Privacy helpers for logs and review payloads."""

from __future__ import annotations

import re
from typing import Any
"""
文件的内容都要按照逻辑上传数据库和向量库呀，不然怎么调用后续工具函数等逻辑呢，那这个智能体的效果就很差了呀
"""

PHONE_RE = re.compile(r"1[3-9]\d{9}")
EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
STUDENT_ID_RE = re.compile(r"\b([A-Za-z]?\d{4})\d{3,16}\b")


def mask_text(value: str) -> str:
    value = PHONE_RE.sub(lambda m: m.group(0)[:3] + "****" + m.group(0)[-4:], value)
    value = EMAIL_RE.sub(lambda m: m.group(1) + "***" + m.group(2), value)
    value = STUDENT_ID_RE.sub(lambda m: m.group(1) + "****", value)
    return value


def redact_payload(payload: Any) -> Any:
    """Recursively mask common personal identifiers before writing logs."""
    if isinstance(payload, str):
        return mask_text(payload)
    if isinstance(payload, list):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, dict):
        return {key: redact_payload(value) for key, value in payload.items()}
    return payload

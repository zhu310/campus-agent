"""Spreadsheet analysis helpers inspired by the standalone data-analysis agent."""

from __future__ import annotations

import json
from collections import deque
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from app.services.llm_service import chat_completion


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _clean_empty(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace(r"^\s*$", np.nan, regex=True)
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
    df = df.reset_index(drop=True)
    df.columns = range(df.shape[1])
    return df


def _find_blocks(df: pd.DataFrame, min_rows: int = 2, min_cols: int = 2) -> list[pd.DataFrame]:
    df = df.map(lambda value: value if pd.notnull(value) and str(value).strip() else np.nan)
    mask = df.notnull().values
    visited = np.zeros_like(mask, dtype=bool)
    rows, cols = df.shape
    blocks: list[pd.DataFrame] = []

    def bfs(start_row: int, start_col: int) -> list[tuple[int, int]]:
        queue: deque[tuple[int, int]] = deque([(start_row, start_col)])
        visited[start_row, start_col] = True
        coords: list[tuple[int, int]] = []
        while queue:
            row, col = queue.popleft()
            coords.append((row, col))
            for d_row in (-1, 0, 1):
                for d_col in (-1, 0, 1):
                    if d_row == 0 and d_col == 0:
                        continue
                    next_row, next_col = row + d_row, col + d_col
                    if 0 <= next_row < rows and 0 <= next_col < cols and mask[next_row, next_col] and not visited[next_row, next_col]:
                        visited[next_row, next_col] = True
                        queue.append((next_row, next_col))
        return coords

    for row in range(rows):
        for col in range(cols):
            if mask[row, col] and not visited[row, col]:
                coords = bfs(row, col)
                row_start = min(item[0] for item in coords)
                row_end = max(item[0] for item in coords)
                col_start = min(item[1] for item in coords)
                col_end = max(item[1] for item in coords)
                block = _clean_empty(df.iloc[row_start : row_end + 1, col_start : col_end + 1])
                if block.shape[0] >= min_rows and block.shape[1] >= min_cols:
                    blocks.append(block)
    return blocks


def _load_memory_file(file_name: str, content: bytes) -> list[tuple[str, pd.DataFrame]]:
    ext = Path(file_name).suffix.lower()
    if ext == ".csv":
        return [("sheet0", pd.read_csv(BytesIO(content), header=None))]
    if ext in {".xlsx", ".xls"}:
        excel = pd.ExcelFile(BytesIO(content))
        return [(sheet, excel.parse(sheet_name=sheet, header=None)) for sheet in excel.sheet_names]
    raise ValueError(f"不支持的文件类型：{file_name}")


def _normalize_block(block: pd.DataFrame) -> pd.DataFrame:
    if block.empty:
        return block
    header = [str(value).strip() if pd.notnull(value) and str(value).strip() else f"列{idx + 1}" for idx, value in enumerate(block.iloc[0].tolist())]
    deduped: list[str] = []
    seen: dict[str, int] = {}
    for idx, name in enumerate(header):
        base = name or f"列{idx + 1}"
        seen[base] = seen.get(base, 0) + 1
        deduped.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    normalized = block.iloc[1:].copy().reset_index(drop=True)
    normalized.columns = deduped
    if normalized.empty:
        normalized = block.copy()
        normalized.columns = [f"列{idx + 1}" for idx in range(block.shape[1])]
    return normalized


def _summarize_table(df: pd.DataFrame) -> dict[str, Any]:
    total_cells = int(df.shape[0] * df.shape[1])
    missing_cells = int(df.isna().sum().sum())
    columns: list[dict[str, Any]] = []
    numeric_summary: list[dict[str, Any]] = []

    for col in df.columns:
        series = df[col]
        numeric = pd.to_numeric(series, errors="coerce")
        non_null = int(series.notna().sum())
        missing = int(series.isna().sum())
        unique = int(series.dropna().nunique())
        column_type = "数值" if numeric.notna().sum() >= max(2, non_null * 0.6) else "文本"
        columns.append(
            {
                "name": str(col),
                "type": column_type,
                "non_null": non_null,
                "missing": missing,
                "unique": unique,
            }
        )
        if column_type == "数值":
            clean = numeric.dropna()
            if not clean.empty:
                numeric_summary.append(
                    {
                        "column": str(col),
                        "min": _jsonable(clean.min()),
                        "max": _jsonable(clean.max()),
                        "mean": _jsonable(clean.mean()),
                        "sum": _jsonable(clean.sum()),
                    }
                )

    preview = df.head(8).replace({np.nan: None}).map(_jsonable).to_dict(orient="records")
    return {
        "row_count": int(df.shape[0]),
        "column_count": int(df.shape[1]),
        "missing_cells": missing_cells,
        "missing_rate": round(missing_cells / total_cells, 4) if total_cells else 0,
        "columns": columns,
        "numeric_summary": numeric_summary,
        "preview": preview,
    }


def _build_fallback_insights(blocks: list[dict[str, Any]], task: str) -> str:
    if not blocks:
        return "未检测到可分析的数据块。"
    total_rows = sum(block["row_count"] for block in blocks)
    total_cols = sum(block["column_count"] for block in blocks)
    highest_missing = max(blocks, key=lambda item: item["missing_rate"])
    numeric_columns = [item for block in blocks for item in block["numeric_summary"]]
    lines = [
        f"已围绕“{task}”完成基础数据体检：共识别 {len(blocks)} 个数据块，合计 {total_rows} 行、{total_cols} 列。",
        f"缺失率最高的数据块是 {highest_missing['key']}，缺失率约 {highest_missing['missing_rate']:.1%}。",
    ]
    if numeric_columns:
        top = max(numeric_columns, key=lambda item: abs(float(item.get("sum") or 0)))
        lines.append(f"数值字段中，{top['column']} 的汇总值最突出，合计约 {top['sum']}，平均值约 {round(float(top['mean']), 2)}。")
    lines.append("建议优先核对高缺失字段、统一表头命名，再按业务维度做分组对比。")
    return "\n".join(lines)


def _build_llm_insights(blocks: list[dict[str, Any]], task: str) -> tuple[str, bool]:
    compact_blocks = [
        {
            "key": block["key"],
            "rows": block["row_count"],
            "columns": block["column_count"],
            "missing_rate": block["missing_rate"],
            "columns_detail": block["columns"],
            "numeric_summary": block["numeric_summary"],
            "preview": block["preview"][:3],
        }
        for block in blocks
    ]
    system_prompt = "你是校园业务数据分析智能体。请基于结构化表格摘要给出可靠、克制、可执行的中文分析，不编造未出现的数据。"
    user_prompt = (
        f"分析任务：{task}\n\n"
        "表格数据摘要如下，请输出：1. 数据概览；2. 关键发现；3. 风险/缺失；4. 后续建议。\n"
        f"{json.dumps(compact_blocks, ensure_ascii=False, indent=2)}"
    )
    answer = chat_completion(system_prompt, user_prompt).strip()
    if answer:
        return answer, False
    return _build_fallback_insights(blocks, task), True


async def analyze_files(files: Iterable[Any], task: str) -> dict[str, Any]:
    memory_files: list[tuple[str, bytes]] = []
    for idx, file in enumerate(files):
        content = await file.read()
        if content:
            memory_files.append((file.filename or f"upload_{idx}.xlsx", content))
    if not memory_files:
        raise ValueError("未获取到文件内容")

    blocks: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    for file_name, content in memory_files:
        loaded = _load_memory_file(file_name, content)
        file_block_count = 0
        for sheet, raw_df in loaded:
            for block_idx, raw_block in enumerate(_find_blocks(raw_df), 1):
                table = _normalize_block(raw_block)
                table_summary = _summarize_table(table)
                key = f"{file_name}|{sheet}|block{block_idx}"
                blocks.append({"key": key, "file_name": file_name, "sheet": sheet, **table_summary})
                file_block_count += 1
        file_summaries.append({"file_name": file_name, "blocks": file_block_count})

    if not blocks:
        raise ValueError("未检测到可用数据块")

    insights, fallback_used = _build_llm_insights(blocks, task)
    return {
        "task": task,
        "files": file_summaries,
        "block_count": len(blocks),
        "blocks": blocks,
        "insights": insights,
        "fallback_used": fallback_used,
    }

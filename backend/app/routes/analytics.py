"""Data-analysis agent endpoints."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.data_analysis_service import analyze_files

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/analyze")
async def analyze_spreadsheets(
    files: List[UploadFile] = File(..., description="上传一个或多个 Excel/CSV 文件"),
    task: str = Form("请分析这批校园业务数据的整体情况、异常和后续建议"),
):
    if not files:
        raise HTTPException(status_code=400, detail="至少需要上传一个文件")
    try:
        return await analyze_files(files, task=task.strip() or "请分析这批校园业务数据")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据分析失败：{exc}") from exc

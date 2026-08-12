"""Narratives router — Gemini-based text extraction, validation, registration, and safety check."""

import asyncio
import json
import logging
import os
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.agents.gemini_agent import extract_from_text, check_safety_compliance
from app.agents.validator import validate_schema
from app.lib.db_operations import register_to_database
from app.lib.file_readers import read_file
from app.schemas.narrative import (
    ExtractionRequest,
    ExtractedGraph,
    RegistrationResult,
    SafetyCheckResult,
    ValidationResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/narratives", tags=["narratives"])

# サポートするファイル拡張子
_SUPPORTED_EXTENSIONS = {".docx", ".xlsx", ".pdf", ".txt", ".csv"}


@router.post("/extract")
async def extract(request: ExtractionRequest):
    """ナラティブテキストから構造化データを抽出する。"""
    try:
        result = await extract_from_text(request.text, request.client_name)
        if result is None:
            raise HTTPException(
                status_code=422,
                detail="テキストからのデータ抽出に失敗しました。入力内容を確認してください。",
            )
        return ExtractedGraph(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("extract failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/extract-stream")
async def extract_stream(request: ExtractionRequest):
    """ナラティブテキストの抽出進捗を SSE でストリーミングする。

    イベントは {stage, progress, message, data?} の JSON オブジェクト。
    """

    async def event_generator():
        def sse(event: dict) -> str:
            return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        try:
            yield sse({"stage": "started", "progress": 0, "message": "処理を開始しました"})
            await asyncio.sleep(0.01)

            # Stage 1: chunking
            yield sse({"stage": "chunking", "progress": 15, "message": "テキストを解析しています"})
            await asyncio.sleep(0.01)

            # Stage 2: extraction (Gemini call)
            yield sse({"stage": "extracting", "progress": 30, "message": "Gemini でエンティティを抽出中..."})
            try:
                result = await extract_from_text(request.text, request.client_name)
            except Exception as exc:
                yield sse({"stage": "error", "progress": 0, "message": f"抽出失敗: {exc}"})
                return
            if result is None:
                yield sse({"stage": "error", "progress": 0, "message": "抽出結果が空でした"})
                return
            yield sse({
                "stage": "extracting",
                "progress": 60,
                "message": f"抽出完了: {len(result.get('nodes', []))} ノード",
            })
            await asyncio.sleep(0.01)

            # Stage 3: validation
            yield sse({"stage": "validating", "progress": 70, "message": "構造を検証中..."})
            try:
                validation = validate_schema(result)
                if not validation.get("is_valid", True):
                    yield sse({
                        "stage": "validating",
                        "progress": 70,
                        "message": f"警告: {len(validation.get('warnings', []))}件",
                    })
            except Exception as exc:
                logger.warning("validation failed: %s", exc)
            await asyncio.sleep(0.01)

            # Stage 4: complete
            yield sse({
                "stage": "complete",
                "progress": 100,
                "message": (
                    f"完了: {len(result.get('nodes', []))}ノード, "
                    f"{len(result.get('relationships', []))}リレーション"
                ),
                "data": {
                    "graph": result,
                    "semanticWarnings": [],
                },
            })

        except Exception as exc:
            logger.error("SSE stream failed: %s", exc, exc_info=True)
            yield sse({"stage": "error", "progress": 0, "message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/validate", response_model=ValidationResult)
async def validate(graph: ExtractedGraph):
    """抽出済みグラフデータのスキーマバリデーションを行う。"""
    try:
        return validate_schema(graph.model_dump())
    except Exception as exc:
        logger.error("validate failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/register", response_model=RegistrationResult)
async def register(graph: ExtractedGraph):
    """抽出済みグラフデータを Neo4j に登録する。"""
    try:
        result = register_to_database(graph.model_dump(exclude={"confirmDuplicates"}))
        if result.get("status") == "error":
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "データベース登録に失敗しました。"),
            )

        return RegistrationResult(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("register failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """ファイルをアップロードしてテキストを抽出する。"""
    try:
        # ファイル拡張子チェック
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"未対応のファイル形式です: {ext}（対応: {', '.join(sorted(_SUPPORTED_EXTENSIONS))}）",
            )

        content = await file.read()
        text = read_file(BytesIO(content), file.filename)
        if not text or not text.strip():
            raise HTTPException(
                status_code=422,
                detail="ファイルからテキストを抽出できませんでした。",
            )
        return {"filename": file.filename, "text": text}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("upload_file failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/safety-check", response_model=SafetyCheckResult)
async def safety_check(request: ExtractionRequest):
    """テキスト内容の安全性チェック（NgAction との照合）を行う。"""
    try:
        ng_actions = []
        if request.client_name:
            from app.lib.db_operations import run_query
            records = run_query(
                "MATCH (c:Client {name: $name})-[:MUST_AVOID]->(ng:NgAction) RETURN ng",
                {"name": request.client_name},
            )
            ng_actions = [dict(r["ng"]) for r in records]
        result = await check_safety_compliance(request.text, ng_actions)
        if result is None:
            raise HTTPException(
                status_code=422,
                detail="安全性チェックに失敗しました。",
            )
        return SafetyCheckResult(**result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("safety_check failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

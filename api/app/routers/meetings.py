"""Meetings router — text/document meeting records and retrieval."""
import io
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.lib.db_operations import register_to_database, run_query
from app.lib.embedding import embed_text
from app.lib.file_readers import read_file
from app.schemas.meeting import MeetingRecord, MeetingUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meetings", tags=["meetings"])
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "meetings"

SUPPORTED_DOCUMENT_EXTENSIONS = {".docx", ".xlsx", ".pdf", ".txt"}

# 2026-08-12: 音声の文字起こしは廃止。AI を Claude 一本にまとめる方針に対し、
# Claude は音声を扱えないため（→ docs/manuals/COMPLETE_MANUAL.md 2-3）。面談記録は
# 文字入力または文書ファイルで受ける。


@router.post("/upload", response_model=MeetingUploadResponse)
async def upload_meeting(
    file: UploadFile | None = File(None),
    client_name: str = Form(...),
    title: str = Form(""),
    note: str = Form(""),
    text: str = Form(""),
):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:8]
    today = datetime.now().strftime("%Y-%m-%d")

    if text.strip():
        # その場で文字入力: 本文をテキストファイルとして保存（filePath が embedding 付与のキーになる）
        file_path = UPLOAD_DIR / f"{file_id}_memo.txt"
        file_path.write_text(text, encoding="utf-8")
        transcript = text
        default_title = f"面談メモ {today}"
    elif file is not None and file.filename:
        suffix = Path(file.filename or "").suffix.lower()
        content_type = file.content_type or ""
        is_document = suffix in SUPPORTED_DOCUMENT_EXTENSIONS
        if not is_document:
            return MeetingUploadResponse(
                status="error",
                message=(
                    f"対応していないファイル形式です: {suffix or content_type}。"
                    "文書（Word・Excel・PDF・テキスト）を選んでください。"
                    "音声の文字起こしは廃止しました。"
                ),
            )

        safe_filename = Path(file.filename).name.replace("..", "").replace("/", "").replace("\\", "")
        file_path = UPLOAD_DIR / f"{file_id}_{safe_filename}"
        content = await file.read()
        file_path.write_bytes(content)

        try:
            transcript = read_file(io.BytesIO(content), file.filename)
        except (ValueError, ImportError) as e:
            file_path.unlink(missing_ok=True)
            logger.error(f"Document text extraction failed: {e}")
            return MeetingUploadResponse(
                status="error",
                message="文書ファイルからテキストを読み取れませんでした。ファイルを開けるか確認してください。",
            )
        default_title = file.filename
    else:
        return MeetingUploadResponse(
            status="error",
            message="記録の内容がありません。文章を入力するか、ファイルを選んでください。",
        )

    graph = {
        "nodes": [
            {"temp_id": "c1", "label": "Client", "properties": {"name": client_name}},
            {"temp_id": "mr1", "label": "MeetingRecord", "properties": {
                "date": today,
                "title": title or default_title,
                "filePath": str(file_path),
                "transcript": transcript or "",
                "note": note,
            }},
        ],
        "relationships": [
            {"source_temp_id": "mr1", "target_temp_id": "c1", "type": "ABOUT", "properties": {}},
        ],
    }
    register_to_database(graph)

    if transcript:
        embedding = await embed_text(transcript)
        if embedding:
            run_query(
                "MATCH (mr:MeetingRecord {filePath: $path}) SET mr.textEmbedding = $embedding",
                {"path": str(file_path), "embedding": embedding},
            )

    return MeetingUploadResponse(status="success", transcript=transcript, meeting_id=file_id)


@router.get("/{client_name}", response_model=list[MeetingRecord])
async def list_meetings(client_name: str):
    records = run_query(
        """
        MATCH (mr:MeetingRecord)-[:ABOUT]->(c:Client {name: $name})
        RETURN mr.date AS date, mr.title AS title, mr.duration AS duration,
               mr.transcript AS transcript, mr.note AS note,
               mr.filePath AS file_path, c.name AS client_name
        ORDER BY mr.date DESC
        """,
        {"name": client_name},
    )
    return [MeetingRecord(**r) for r in records]

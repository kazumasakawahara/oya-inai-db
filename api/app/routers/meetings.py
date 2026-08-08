"""Meetings router — audio upload, Gemini transcription, and meeting record retrieval."""
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from app.lib.db_operations import register_to_database, run_query
from app.lib.embedding import embed_text
from app.schemas.meeting import MeetingRecord, MeetingUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/meetings", tags=["meetings"])
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads" / "meetings"

SUPPORTED_AUDIO_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/wav", "audio/ogg",
    "audio/webm", "audio/flac", "audio/aac", "audio/x-m4a",
}
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".wav", ".ogg", ".webm", ".flac", ".aac", ".m4a"}


async def _transcribe_with_gemini(file_path: str) -> str | None:
    try:
        import google.generativeai as genai
        from app.config import settings
        genai.configure(api_key=settings.gemini_api_key or settings.google_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        audio_file = genai.upload_file(file_path)
        response = model.generate_content(
            ["この音声を正確に日本語で文字起こししてください。", audio_file],
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini transcription failed: {e}")
        return None


@router.post("/upload", response_model=MeetingUploadResponse)
async def upload_meeting(
    file: UploadFile = File(...),
    client_name: str = Form(...),
    title: str = Form(""),
    note: str = Form(""),
):
    # Validate file type
    suffix = Path(file.filename or "").suffix.lower()
    content_type = file.content_type or ""
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS and content_type not in SUPPORTED_AUDIO_TYPES:
        return MeetingUploadResponse(
            status="error",
            message=f"Unsupported file format: {suffix or content_type}. Please upload an audio file.",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex[:8]
    safe_filename = Path(file.filename).name.replace("..", "").replace("/", "").replace("\\", "")
    file_path = UPLOAD_DIR / f"{file_id}_{safe_filename}"
    content = await file.read()
    file_path.write_bytes(content)

    transcript = await _transcribe_with_gemini(str(file_path))

    graph = {
        "nodes": [
            {"temp_id": "c1", "label": "Client", "properties": {"name": client_name}},
            {"temp_id": "mr1", "label": "MeetingRecord", "properties": {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "title": title or file.filename,
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

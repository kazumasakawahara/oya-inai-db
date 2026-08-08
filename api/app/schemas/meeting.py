from pydantic import BaseModel


class MeetingRecord(BaseModel):
    date: str | None = None
    title: str | None = None
    duration: str | None = None
    transcript: str | None = None
    note: str | None = None
    client_name: str | None = None
    file_path: str | None = None


class MeetingUploadResponse(BaseModel):
    status: str
    transcript: str | None = None
    meeting_id: str | None = None
    message: str | None = None

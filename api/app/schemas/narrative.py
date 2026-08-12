from typing import Literal

from pydantic import BaseModel


class RegistrationResult(BaseModel):
    status: str
    client_name: str | None = None
    registered_count: int = 0
    registered_types: list[str] = []
    message: str | None = None


class QuickLogRequest(BaseModel):
    client_name: str
    note: str
    situation: str | None = None
    # 語彙は SCHEMA_CONVENTION §7.4 の10値（UI にはうち6値のみ表示）
    emotion: (
        Literal[
            "Joy", "Anger", "Sadness", "Fear", "Surprise",
            "Disgust", "Calm", "Anxiety", "Confusion", "Neutral",
        ]
        | None
    ) = None
    trigger_tag: str | None = None
    context: str | None = None
    action: str | None = None
    effectiveness: Literal["Effective", "Neutral", "Ineffective"] | None = None
    supporter_name: str = "system"

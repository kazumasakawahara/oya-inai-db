from datetime import datetime

from fastapi import APIRouter

from app.lib.db_operations import register_to_database
from app.schemas.narrative import QuickLogRequest, RegistrationResult

router = APIRouter(prefix="/api/quicklog", tags=["quicklog"])


@router.post("", response_model=RegistrationResult)
async def create_quicklog(request: QuickLogRequest):
    graph = {
        "nodes": [
            {"temp_id": "c1", "label": "Client", "properties": {"name": request.client_name}},
            {"temp_id": "s1", "label": "Supporter", "properties": {"name": request.supporter_name}},
            {
                "temp_id": "log1",
                "label": "SupportLog",
                "properties": {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "note": request.note,
                    "situation": request.situation or "日常記録",
                },
            },
        ],
        "relationships": [
            {"source_temp_id": "s1", "target_temp_id": "log1", "type": "LOGGED", "properties": {}},
            {"source_temp_id": "log1", "target_temp_id": "c1", "type": "ABOUT", "properties": {}},
        ],
    }
    result = register_to_database(graph, user_name=request.supporter_name)
    return RegistrationResult(**result)

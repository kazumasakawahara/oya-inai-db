from fastapi import APIRouter, Query
from app.lib.ecomap import fetch_ecomap_data, TEMPLATES, CATEGORY_COLORS
from app.schemas.ecomap import EcomapData, EcomapTemplate

router = APIRouter(prefix="/api/ecomap", tags=["ecomap"])


@router.get("/templates", response_model=list[EcomapTemplate])
async def list_templates():
    return [EcomapTemplate(id=k, name=v["name"], description=v["description"]) for k, v in TEMPLATES.items()]


@router.get("/colors")
async def get_category_colors():
    return CATEGORY_COLORS


@router.get("/{client_name}", response_model=EcomapData)
async def get_ecomap(client_name: str, template: str = Query("full_view")):
    return fetch_ecomap_data(client_name, template)

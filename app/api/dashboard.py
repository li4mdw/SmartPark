from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(tags=["dashboard"])
_DASHBOARD_FILE = Path(__file__).resolve().parents[1] / "templates" / "dashboard.html"


@router.get(
    "/dashboard",
    response_class=FileResponse,
    include_in_schema=False,
)
async def dashboard() -> FileResponse:
    return FileResponse(_DASHBOARD_FILE, media_type="text/html")

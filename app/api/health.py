from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.schemas.health import HealthResponse


router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Report whether the web process is running."""
    return HealthResponse(status="alive", service="smartpark-api")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readiness(request: Request) -> HealthResponse | JSONResponse:
    """Report whether application startup has completed."""
    if not getattr(request.app.state, "ready", False):
        payload = HealthResponse(status="not_ready", service="smartpark-api")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )

    return HealthResponse(status="ready", service="smartpark-api")

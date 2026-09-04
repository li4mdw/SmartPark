from fastapi import APIRouter, Depends, Request

from app.schemas.operator import (
    ActiveUsersResponse,
    OperatorCarparksResponse,
    OperatorCarparkStatus,
)
from app.services.operator import OperatorService


router = APIRouter(prefix="/api/operator", tags=["operator"])


def get_operator_service(request: Request) -> OperatorService:
    return request.app.state.operator_service


@router.get("/carparks", response_model=OperatorCarparksResponse)
async def list_carparks(
    service: OperatorService = Depends(get_operator_service),
) -> OperatorCarparksResponse:
    carparks = await service.list_carparks()
    return OperatorCarparksResponse(
        carparks=[
            OperatorCarparkStatus(
                carpark_id=item.carpark_id,
                status="known" if item.stored_status is not None else "unknown",
                available_spaces=(
                    item.stored_status.available_spaces if item.stored_status else None
                ),
                confidence_score=(
                    item.stored_status.confidence_score if item.stored_status else None
                ),
                inference_ms=(
                    item.stored_status.inference_ms if item.stored_status else None
                ),
                model_version=(
                    item.stored_status.model_version if item.stored_status else None
                ),
                updated_at=(
                    item.stored_status.updated_at if item.stored_status else None
                ),
            )
            for item in carparks
        ]
    )


@router.get("/active-users", response_model=ActiveUsersResponse)
async def active_users(
    service: OperatorService = Depends(get_operator_service),
) -> ActiveUsersResponse:
    return ActiveUsersResponse(
        window_seconds=service.recent_user_window_seconds,
        active_users=await service.count_active_users(),
    )

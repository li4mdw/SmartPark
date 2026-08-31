import base64

from fastapi import APIRouter, Depends, Request

from app.schemas.carpark import AnnotateCarparkQuery, AnnotateCarparkResponse
from app.services.annotation import AnnotationService


router = APIRouter(prefix="/api", tags=["core"])


def get_annotation_service(request: Request) -> AnnotationService:
    return request.app.state.annotation_service


@router.get("/annotate-carpark", response_model=AnnotateCarparkResponse)
async def annotate_carpark(
    query: AnnotateCarparkQuery = Depends(),
    service: AnnotationService = Depends(get_annotation_service),
) -> AnnotateCarparkResponse:
    result = await service.annotate(query.carpark_id)
    return AnnotateCarparkResponse(
        carpark_id=result.carpark_id,
        image_base64=base64.b64encode(result.image).decode("ascii"),
    )

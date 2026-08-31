import base64

from fastapi import APIRouter, Depends, Request

from app.schemas.carpark import (
    AnnotateCarparkQuery,
    AnnotateCarparkResponse,
    CarparkSearchItem,
    FindCarparksQuery,
    FindCarparksResponse,
)
from app.services.annotation import AnnotationService
from app.services.carpark_search import CarparkSearchService


router = APIRouter(prefix="/api", tags=["core"])


def get_annotation_service(request: Request) -> AnnotationService:
    return request.app.state.annotation_service


def get_carpark_search_service(request: Request) -> CarparkSearchService:
    return request.app.state.carpark_search_service


@router.get("/find-carparks", response_model=FindCarparksResponse)
async def find_carparks(
    query: FindCarparksQuery = Depends(),
    service: CarparkSearchService = Depends(get_carpark_search_service),
) -> FindCarparksResponse:
    result = await service.find(query.uuid, query.n)
    return FindCarparksResponse(
        uuid=result.uuid,
        speed_inference=f"{result.total_inference_ms:.2f} ms",
        requested_n=result.requested_n,
        results=[
            CarparkSearchItem(
                carpark_id=item.carpark_id,
                available_spaces=item.available_spaces,
                confidence_score=item.confidence_score,
            )
            for item in result.results
        ],
    )


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

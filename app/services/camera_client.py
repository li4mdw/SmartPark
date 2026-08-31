import base64
import binascii
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from app.schemas.camera import CameraPhotoPayload


class CameraClientError(RuntimeError):
    """Base error for camera communication failures."""


class CameraTimeoutError(CameraClientError):
    """Raised when a camera does not respond within the configured timeout."""


class CameraUnavailableError(CameraClientError):
    """Raised when the camera service cannot be reached or rejects a request."""


class InvalidCameraResponseError(CameraClientError):
    """Raised when a camera response cannot be safely used."""


@dataclass(frozen=True, slots=True)
class CameraPhoto:
    carpark_id: str
    content: bytes
    media_type: str


class CameraClient:
    def __init__(self, http_client: httpx.AsyncClient, max_image_bytes: int) -> None:
        self._http_client = http_client
        self._max_image_bytes = max_image_bytes

    async def take_photo(self, carpark_id: str) -> CameraPhoto:
        try:
            response = await self._http_client.get(
                "/api/takephoto",
                params={"carpark_id": carpark_id},
            )
        except httpx.TimeoutException as exc:
            raise CameraTimeoutError(f"Camera timed out for {carpark_id}") from exc
        except httpx.RequestError as exc:
            raise CameraUnavailableError(
                f"Camera service is unavailable for {carpark_id}"
            ) from exc

        if response.status_code != 200:
            raise CameraUnavailableError(
                f"Camera returned HTTP {response.status_code} for {carpark_id}"
            )

        self._reject_oversized_response(response)
        try:
            payload = CameraPhotoPayload.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise InvalidCameraResponseError("Camera returned invalid JSON") from exc

        if payload.carpark_id != carpark_id:
            raise InvalidCameraResponseError("Camera returned a mismatched carpark_id")

        try:
            image_content = base64.b64decode(payload.image_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise InvalidCameraResponseError("Camera returned invalid base64 data") from exc

        if not image_content:
            raise InvalidCameraResponseError("Camera returned an empty image")
        if len(image_content) > self._max_image_bytes:
            raise InvalidCameraResponseError("Camera image exceeds the configured size limit")

        return CameraPhoto(
            carpark_id=payload.carpark_id,
            content=image_content,
            media_type=payload.media_type,
        )

    def _reject_oversized_response(self, response: httpx.Response) -> None:
        # Base64 expands data by roughly one third; allow modest JSON overhead.
        maximum_response_bytes = (self._max_image_bytes * 4 // 3) + 4096
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > maximum_response_bytes:
                    raise InvalidCameraResponseError(
                        "Camera response exceeds the configured size limit"
                    )
            except ValueError as exc:
                raise InvalidCameraResponseError(
                    "Camera returned an invalid Content-Length header"
                ) from exc

        if len(response.content) > maximum_response_bytes:
            raise InvalidCameraResponseError(
                "Camera response exceeds the configured size limit"
            )

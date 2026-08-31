from typing import Literal

from pydantic import BaseModel, ConfigDict


class CameraPhotoPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carpark_id: str
    status: Literal["success"]
    msg: str
    media_type: Literal["image/jpeg", "image/png"]
    image_base64: str

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TakePhotoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carpark_id: str
    status: Literal["success"] = "success"
    msg: str = "success"
    media_type: Literal["image/jpeg", "image/png"]
    image_base64: str


class CameraErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class CameraErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["error"] = "error"
    msg: str
    error: CameraErrorDetail


class TakePhotoQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carpark_id: str = Field(pattern=r"^CBD_[0-9]{3}$")

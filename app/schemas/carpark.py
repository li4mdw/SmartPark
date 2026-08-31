from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnnotateCarparkQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carpark_id: str = Field(pattern=r"^CBD_[0-9]{3}$")


class AnnotateCarparkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carpark_id: str
    status: Literal["success"] = "success"
    msg: str = "success"
    image_base64: str


class FindCarparksQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uuid: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )
    n: int = Field(ge=1)


class CarparkSearchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carpark_id: str
    available_spaces: int = Field(ge=0)
    confidence_score: float = Field(ge=0.0, le=1.0)


class FindCarparksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uuid: str
    status: Literal["success"] = "success"
    msg: str = "success"
    speed_inference: str
    requested_n: int
    results: list[CarparkSearchItem]

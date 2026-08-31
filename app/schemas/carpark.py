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

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OperatorCarparkStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carpark_id: str
    status: Literal["known", "unknown"]
    available_spaces: int | None = Field(default=None, ge=0)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    inference_ms: float | None = Field(default=None, ge=0.0)
    model_version: str | None = None
    updated_at: float | None = None


class OperatorCarparksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    msg: str = "success"
    carparks: list[OperatorCarparkStatus]


class ActiveUsersResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    msg: str = "success"
    window_seconds: int = Field(ge=1)
    active_users: int = Field(ge=0)

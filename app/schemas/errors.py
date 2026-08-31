from typing import Literal

from pydantic import BaseModel, ConfigDict


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["error"]
    msg: str
    error: ErrorDetail

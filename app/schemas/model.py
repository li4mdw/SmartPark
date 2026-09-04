from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    msg: str = "success"
    model_version: str = Field(min_length=1)
    model_format: Literal["pt", "onnx"]
    model_path: str = Field(min_length=1)
    loaded: bool

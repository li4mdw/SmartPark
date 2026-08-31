from dataclasses import dataclass
import os
from pathlib import Path


_DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "images"


@dataclass(frozen=True, slots=True)
class CameraSettings:
    dataset_path: Path
    log_level: str

    @classmethod
    def from_environment(cls) -> "CameraSettings":
        return cls(
            dataset_path=Path(
                os.getenv("CAMERA_DATASET_PATH", str(_DEFAULT_DATASET_PATH))
            ),
            log_level=os.getenv("CAMERA_LOG_LEVEL", "INFO").upper(),
        )

from dataclasses import dataclass
from pathlib import Path
import secrets


SUPPORTED_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


class ImageRepositoryError(RuntimeError):
    """Raised when the simulator cannot provide a source image."""


@dataclass(frozen=True, slots=True)
class CameraImage:
    content: bytes
    media_type: str


class ImageRepository:
    def __init__(self, dataset_path: Path) -> None:
        self._dataset_path = dataset_path

    def take_random(self) -> CameraImage:
        image_paths = self._find_images()
        if not image_paths:
            raise ImageRepositoryError("No supported images are available")

        image_path = secrets.choice(image_paths)
        try:
            content = image_path.read_bytes()
        except OSError as exc:
            raise ImageRepositoryError("The selected image could not be read") from exc

        if not content:
            raise ImageRepositoryError("The selected image is empty")

        return CameraImage(
            content=content,
            media_type=SUPPORTED_IMAGE_TYPES[image_path.suffix.lower()],
        )

    def _find_images(self) -> tuple[Path, ...]:
        if not self._dataset_path.is_dir():
            return ()

        return tuple(
            path
            for path in self._dataset_path.iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_TYPES
        )

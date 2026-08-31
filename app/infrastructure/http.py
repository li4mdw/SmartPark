import httpx

from app.infrastructure.settings import Settings


def create_http_client(settings: Settings) -> httpx.AsyncClient:
    """Create the shared asynchronous client used for camera requests."""
    timeout = httpx.Timeout(
        connect=settings.camera_connect_timeout_seconds,
        read=settings.camera_read_timeout_seconds,
        write=settings.camera_read_timeout_seconds,
        pool=settings.camera_connect_timeout_seconds,
    )
    return httpx.AsyncClient(
        base_url=settings.camera_base_url.rstrip("/"),
        timeout=timeout,
        follow_redirects=False,
    )

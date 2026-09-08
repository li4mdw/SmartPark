# The camera simulator only serves image files; it does not perform ML inference.

# A small standard Python image is therefore enough and keeps this service separate.
FROM python:3.12-slim-bookworm

# Write logs immediately and avoid creating Python cache files in the container.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/camera \
    CAMERA_DATASET_PATH=/app/images

WORKDIR /app

# Install only the camera simulator's small set of runtime dependencies.
COPY requirements-camera.txt ./requirements-camera.txt
RUN python -m pip install --no-cache-dir -r requirements-camera.txt \
    && groupadd --gid 10002 camera \
    && useradd --uid 10002 --gid camera --create-home --shell /usr/sbin/nologin camera

# Copy only what this service needs: its code, shared logging helper, and test dataset.
# The dataset is intentionally included because the simulator cannot operate without it.
COPY --chown=camera:camera camera_simulator ./camera_simulator
COPY --chown=camera:camera app/__init__.py ./app/__init__.py
COPY --chown=camera:camera app/infrastructure/__init__.py app/infrastructure/logging.py ./app/infrastructure/
COPY --chown=camera:camera images ./images

# The service does not need administrator privileges at runtime.
USER camera
EXPOSE 8001

# OpenAPI is available only after FastAPI has started accepting requests.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/openapi.json', timeout=3)"]

CMD ["python", "-m", "uvicorn", "camera_simulator.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--no-access-log"]

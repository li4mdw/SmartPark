# SmartPark runs YOLO inference on CPUs, so use Ultralytics' lightweight CPU image.
# It already supplies compatible Ultralytics, PyTorch and OpenCV packages. Pinning
# the version makes builds repeatable and avoids downloading the large ML stack again.
FROM ultralytics/ultralytics:8.4.135-python

# Keep Python logs immediate and stop tools writing configuration into the app folder.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/smartpark \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib \
    MODEL_PATH=/models/model.pt

WORKDIR /app

# Install only SmartPark's direct runtime dependencies. ML dependencies come from
# the version-pinned base image; development and test tools stay outside this image.
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 smartpark \
    && useradd --uid 10001 --gid smartpark --create-home --shell /usr/sbin/nologin smartpark \
    && mkdir -p /models /tmp/ultralytics /tmp/matplotlib \
    && chown -R smartpark:smartpark /app /models /tmp/ultralytics /tmp/matplotlib

# Copy only the API package. The model is deliberately excluded and must be mounted
# at /models (or MODEL_PATH can point to another mounted model file).
COPY --chown=smartpark:smartpark app ./app

# Running as a non-root user limits damage if the application is compromised.
USER smartpark
EXPOSE 8000

# Readiness checks confirm the API and mounted model are usable before traffic arrives.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3)"]

# One worker avoids loading a separate model copy per process. Scale with containers.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]

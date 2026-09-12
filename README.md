# SmartPark

SmartPark is a containerised parking-availability platform built with FastAPI, YOLO, Redis and Kubernetes. It processes images from a simulated camera service, estimates available parking spaces and exposes operational monitoring endpoints.

The project demonstrates service separation, shared caching, external model storage, horizontal scaling, health checks and load testing.

## Architecture

```text
Client / Locust
       |
       v
SmartPark API (FastAPI + YOLO)
       |                     |
       v                     v
Camera Simulator           Redis
(image delivery)           (cache and shared state)
```

- **SmartPark API** handles routing, orchestration and YOLO inference. Each replica loads its own model and inference worker.
- **Camera Simulator** represents multiple logical car parks and returns an image for a valid carpark ID.
- **Redis** provides shared caching, request activity and carpark status across API replicas.

Separating these services allows the API to scale independently while keeping camera delivery and shared state outside the inference container.

## Features

- Parking-space detection using Ultralytics-compatible `.pt` or `.onnx` models
- Ranked carpark search
- Annotated images returned as Base64
- Redis-backed caching and operational state
- Active-user and model-status monitoring
- Structured request logging
- Docker Compose development environment
- Kubernetes deployments, health probes, persistent storage and autoscaling
- Locust load-testing scenarios

## Repository layout

```text
app/                    SmartPark API and application layers
camera_simulator/       Separate FastAPI camera service
images/                 Camera simulator dataset
kubernetes/             Kubernetes deployments and services
locust/locustfile.py     Load-testing scenarios
model/README.md          External model setup
tests/                   Automated API and service tests
Dockerfile              SmartPark production image
camera.Dockerfile       Camera simulator image
compose.yaml             Local multi-container environment
requirements*.txt       Runtime and development dependencies
```

## API overview

| Route | Purpose |
| --- | --- |
| `GET /api/find-carparks?uuid=user-001&n=2` | Samples carparks and returns those with the most available spaces. |
| `GET /api/annotate-carpark?uuid=user-001&carpark_id=CBD_001` | Returns a newly captured and annotated image as Base64. |
| `GET /api/operator/carparks` | Returns the latest known status of each carpark. |
| `GET /api/operator/active-users` | Reports recently active user identifiers. |
| `GET /api/operator/model` | Reports the loaded model’s format, version and status. |
| `GET /health/live` | Confirms that the API process is running. |
| `GET /health/ready` | Confirms that required dependencies are ready. |
| `GET /dashboard` | Opens the lightweight operator dashboard. |

The default logical ID range is `CBD_001` to `CBD_010`. It can be adjusted using `CARPARK_COUNT`.

## Prerequisites

- Python 3.12
- Docker Desktop and Docker Compose
- A compatible YOLO `.pt` or `.onnx` model
- For Kubernetes: `gcloud`, `kubectl`, a GKE cluster and a Cloud Storage bucket

Model weights are deliberately excluded from the repository and Docker images. See [model/README.md](model/README.md) for setup instructions.

## Run locally with Python

Create a virtual environment and install development dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Place a compatible model at:

```text
model/model.pt
```

Start Redis:

```powershell
docker run --detach `
  --name smartpark-redis `
  --publish 6379:6379 `
  redis:7-alpine redis-server --appendonly yes
```

Start the camera simulator:

```powershell
python -m uvicorn camera_simulator.main:app --port 8001 --reload
```

Start SmartPark in another terminal:

```powershell
python -m uvicorn app.main:app --port 8000 --reload
```

Verify the application:

```powershell
Invoke-RestMethod "http://localhost:8000/health/ready"
Invoke-RestMethod "http://localhost:8000/api/find-carparks?uuid=manual-001&n=2"
Invoke-RestMethod "http://localhost:8000/api/operator/model"
```

Open the API documentation at `http://localhost:8000/docs`.

## Run with Docker Compose

Docker Compose builds both application images, starts Redis and mounts the local model directory read-only:

```powershell
docker compose up --build
```

Available interfaces:

- API documentation: `http://localhost:8000/docs`
- Operator dashboard: `http://localhost:8000/dashboard`
- Camera API: `http://localhost:8001/docs`

Stop the environment:

```powershell
docker compose down
```

Redis data remains in its named volume. Remove it only when the stored data is no longer needed:

```powershell
docker compose down --volumes
```

## Build the images

```powershell
docker build -t smartpark-api:latest .
docker build -f camera.Dockerfile -t smartpark-camera:latest .
```

The SmartPark image contains only the API and runtime dependencies. The model remains external and must be mounted when the container starts.

Redis uses the official `redis:7-alpine` image and does not require a custom Dockerfile.

## Deploy to Kubernetes

Before deployment:

1. Push both application images to a container registry.
2. Update the image references in the Kubernetes manifests.
3. Configure the external model bucket using [model/README.md](model/README.md).
4. Update the bucket name and model path in `kubernetes/smartpark-deployment.yaml`.

Deploy the base environment:

```powershell
kubectl apply -k kubernetes

kubectl rollout status deployment/redis --timeout=180s
kubectl rollout status deployment/camera-simulator --timeout=180s
kubectl rollout status deployment/smartpark-api --timeout=300s

kubectl get deployments,pods,services,pvc
```

Expose SmartPark publicly when required:

```powershell
kubectl apply -f kubernetes/smartpark-loadbalancer.yaml
kubectl get service smartpark-public --watch
```

Enable automatic API scaling:

```powershell
kubectl apply -f kubernetes/smartpark-hpa.yaml
kubectl get hpa smartpark-api --watch
```

Disable autoscaling and return to one replica:

```powershell
kubectl delete hpa smartpark-api --ignore-not-found
kubectl scale deployment/smartpark-api --replicas=1
```

## Load testing

The Locust script supports:

- `find` — tests `/find-carparks`
- `annotate` — tests `/annotate-carpark`
- `mixed` — sends approximately 80% search and 20% annotation traffic

```powershell
$env:SMARTPARK_SCENARIO = "mixed"

python -m locust `
  -f locust/locustfile.py `
  --host http://SMARTPARK_HOST
```

Open `http://localhost:8089` to configure and run the test.

New UUIDs are generated during testing so cached responses do not hide inference cost.

## Tests

The automated tests use fake camera, Redis and inference components where appropriate, keeping tests repeatable and independent of the deployed infrastructure:

```powershell
python -m pytest
```

The suite covers API validation, service workflows, caching, concurrency, model management, health checks and error handling.

## Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `MODEL_PATH` | `model/model.pt` | Local or mounted `.pt`/`.onnx` model. |
| `MODEL_VERSION` | `model-v1` | Model identifier used in metadata and cache keys. |
| `CAMERA_BASE_URL` | `http://127.0.0.1:8001` | Camera Simulator address. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Shared Redis connection. |
| `CARPARK_COUNT` | `10` | Number of logical carparks. |
| `INFERENCE_CONCURRENCY` | `1` | Predictions allowed concurrently per API process. |
| `SEARCH_CACHE_TTL_SECONDS` | `30` | Search-result cache lifetime. |
| `RECENT_USER_WINDOW_SECONDS` | `30` | Active-user reporting window. |

## Design notes

- The API is horizontally scalable because operational state is stored in Redis.
- Each API replica loads one model and provides an independent inference worker.
- Camera requests are asynchronous, while CPU-intensive inference is bounded to prevent uncontrolled contention.
- Redis is kept separate so every API replica sees consistent cached and operational data.
- Models are externally mounted, allowing model versions to change without rebuilding the application image.
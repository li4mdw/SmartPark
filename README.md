# SmartPark

SmartPark is a FastAPI application that uses a YOLO model to estimate parking
availability from simulated camera images. The repository contains the API,
camera simulator, Redis integration, Docker builds, Kubernetes manifests and a
Locust benchmark script. Model weights are supplied separately.

## Architecture

```text
Client / Locust
      |
      v
SmartPark API (FastAPI + YOLO)
      |                    |
      v                    v
Camera simulator         Redis
(random dataset image)   (cache, status and request activity)
```

- **SmartPark API** exposes the core, operator, health and dashboard routes. Each
  replica loads one model and limits inference concurrency within that process.
- **Camera simulator** represents all logical car parks and returns a random
  dataset image for a valid car-park ID.
- **Redis** is shared by every API replica. It stores cached searches, recent
  users, request events and the latest inferred status for each car park.

## Repository layout

```text
app/                    SmartPark API, services, repositories and dashboard
camera_simulator/       Separate FastAPI camera service
images/                 Camera simulator dataset
kubernetes/             GKE deployments, services, storage and HPA
locust/locustfile.py     Core-API load test
model/README.md          External model setup (weights are not submitted)
Dockerfile              SmartPark production image
camera.Dockerfile       Camera simulator image
compose.yaml             Local three-container environment
requirements*.txt       Production, camera and development dependencies
```

## API overview

| Route | Purpose |
| --- | --- |
| `GET /api/find-carparks?uuid=user-001&n=2` | Samples `2n` logical car parks and returns the best `n` results. |
| `GET /api/annotate-carpark?uuid=user-001&carpark_id=CBD_001` | Returns a newly captured and annotated image as base64. |
| `GET /api/operator/carparks` | Returns the latest Redis-backed status for every logical car park. |
| `GET /api/operator/active-users` | Counts UUIDs active in the configured recent-user window. |
| `GET /api/operator/model` | Reports the model path, format, version and loaded state. |
| `GET /health/live` | Confirms that the API process is running. |
| `GET /health/ready` | Confirms that Redis and the model are ready. |
| `GET /dashboard` | Opens the operator dashboard. |

Logical IDs range from `CBD_001` to `CBD_010` by default. `CARPARK_COUNT` may
change the upper bound from 10 to 99. Invalid IDs and UUIDs are rejected.

## Prerequisites

- Python 3.12 for local development
- Docker Desktop and Docker Compose
- For GKE: `gcloud`, `kubectl`, a Standard GKE cluster and a Cloud Storage bucket
- A compatible `.pt` or `.onnx` model supplied outside this artefact

See [model/README.md](model/README.md) before starting the API.

## Run locally with Python

From the repository root, create a virtual environment and install dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Place `model.pt` in `model/`, then start Redis:

```powershell
docker run --detach --name smartpark-redis --publish 6379:6379 redis:7-alpine redis-server --appendonly yes
```

Start the camera simulator and SmartPark API in separate terminals:

```powershell
python -m uvicorn camera_simulator.main:app --port 8001 --reload
```

```powershell
python -m uvicorn app.main:app --port 8000 --reload
```

Verify the application:

```powershell
Invoke-RestMethod "http://localhost:8000/health/ready"
Invoke-RestMethod "http://localhost:8000/api/find-carparks?uuid=manual-001&n=2"
Invoke-RestMethod "http://localhost:8000/api/operator/model"
```

## Run with Docker Compose

Compose builds the two application images, starts the official Redis image and
mounts `./model` read-only. It does not copy the model into an image.

```powershell
docker compose up --build
```

Open `http://localhost:8000/docs` or `http://localhost:8000/dashboard`. Stop the
services with `docker compose down`. Redis data remains in the named volume; use
`docker compose down --volumes` only when that data should also be removed.

## Build the images

Run from the repository root:

```powershell
docker build -t smartpark-api:v1 .
docker build -f camera.Dockerfile -t smartpark-camera:v1 .
```

`Dockerfile` contains only `app/` and SmartPark runtime dependencies.
`camera.Dockerfile` contains the camera service and dataset. Redis uses
`redis:7-alpine` directly and needs no custom Dockerfile.

## Deploy to GKE

The checked-in manifests use these values from the original deployment:

- Project: `causal-space-503901-p7`
- Cluster: `fit3184-cluster`
- Zone: `australia-southeast2-a`
- Model bucket: `causal-space-503901-p7-smartpark-models`
- Model object: `model-v1/model.pt`

For another project, update the image names and `bucketName` in
`kubernetes/smartpark-deployment.yaml`. The cluster must have Workload Identity
Federation and the Cloud Storage FUSE CSI driver enabled. Complete the bucket
and permission steps in [model/README.md](model/README.md), then deploy:

```powershell
gcloud container clusters get-credentials fit3184-cluster `
  --zone australia-southeast2-a `
  --project causal-space-503901-p7

kubectl apply -k kubernetes
kubectl rollout status deployment/redis --timeout=180s
kubectl rollout status deployment/camera-simulator --timeout=180s
kubectl rollout status deployment/smartpark-api --timeout=300s
kubectl get deployments,pods,services,pvc
```

The base kustomization deploys one SmartPark replica and private internal
Services. Create the public endpoint separately:

```powershell
kubectl apply -f kubernetes/smartpark-loadbalancer.yaml
kubectl get service smartpark-public --watch
```

Apply the HPA only when automatic scaling is required:

```powershell
kubectl apply -f kubernetes/smartpark-hpa.yaml
kubectl get hpa smartpark-api --watch
```

Disable it and return to one replica with:

```powershell
kubectl delete hpa smartpark-api --ignore-not-found
kubectl scale deployment/smartpark-api --replicas=1
```

## Locust benchmark

The Locust script supports `find`, `annotate` and `mixed` scenarios. Mixed mode
sends approximately 80% `/find-carparks` and 20% `/annotate-carpark` traffic.
Every request uses a new UUID so cache hits do not hide inference cost.

```powershell
$env:SMARTPARK_SCENARIO="mixed"
python -m locust -f locust/locustfile.py --host http://SMARTPARK_EXTERNAL_IP
```

Open `http://localhost:8089`. For comparable scaling tests, remove the HPA,
manually set 1, 2, 4 and 8 replicas, and use the same users, ramp-up rate and
steady-state duration for every run.

## Important environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `MODEL_PATH` | `model/model.pt` | Local or mounted `.pt`/`.onnx` model path. |
| `MODEL_VERSION` | `model-v1` | Included in model metadata and cache keys. |
| `CAMERA_BASE_URL` | `http://127.0.0.1:8001` | Camera service URL. |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Shared Redis connection. |
| `CARPARK_COUNT` | `10` | Number of logical car parks (10-99). |
| `INFERENCE_CONCURRENCY` | `1` | Concurrent predictions per API process. |
| `SEARCH_CACHE_TTL_SECONDS` | `30` | Search-result cache lifetime. |
| `RECENT_USER_WINDOW_SECONDS` | `30` | Active-user reporting window. |

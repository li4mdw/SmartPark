# SmartPark

The project currently includes the modular SmartPark API skeleton and a separate
camera simulator that returns random images from the supplied dataset.

## Run locally

Create and activate a virtual environment, install the development dependencies,
then run:

```text
python -m pip install -r requirements-test.txt
python -m uvicorn app.main:app --reload
```

The commands must be run from the `release` directory.

Health endpoints:

- `GET /health/live` confirms that the web process is running.
- `GET /health/ready` confirms that application startup has completed.

Core endpoint:

- `GET /api/find-carparks?uuid=unique-user-id-12345&n=3` scans exactly `2n`
  unique logical car parks sequentially and returns the top `n` by available
  spaces.
- `GET /api/annotate-carpark?carpark_id=CBD_001` retrieves a fresh simulated
  camera image, runs YOLO inference, and returns a base64-encoded annotated JPEG.

Run the camera simulator in another terminal:

```text
python -m uvicorn camera_simulator.main:app --port 8001 --reload
```

Request a simulated camera image:

```text
GET http://localhost:8001/api/takephoto?carpark_id=CBD_001
```

The simulator accepts logical IDs in the form `CBD_001` and echoes the ID with
a randomly selected base64-encoded JPEG or PNG image.

Run the tests with:

```text
python -m pytest
```

## Environment settings

| Variable | Default |
| --- | --- |
| `APP_NAME` | `SmartPark API` |
| `APP_VERSION` | `0.1.0` |
| `APP_ENV` | `development` |
| `LOG_LEVEL` | `INFO` |
| `MODEL_PATH` | `<release>/model/model.pt` |
| `MODEL_VERSION` | `model-v1` |
| `AVAILABLE_CLASS_ID` | `0` |
| `MAX_IMAGE_BYTES` | `10485760` |
| `CAMERA_BASE_URL` | `http://127.0.0.1:8001` |
| `CAMERA_CONNECT_TIMEOUT_SECONDS` | `2.0` |
| `CAMERA_READ_TIMEOUT_SECONDS` | `10.0` |
| `CARPARK_COUNT` | `10` |
| `CAMERA_CONCURRENCY` | `10` |
| `INFERENCE_CONCURRENCY` | `1` |
| `SEARCH_TIMEOUT_SECONDS` | `60.0` |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` |
| `RECENT_USER_WINDOW_SECONDS` | `30` |
| `SEARCH_CACHE_TTL_SECONDS` | `30` |
| `CAMERA_DATASET_PATH` | `<release>/images` |
| `CAMERA_LOG_LEVEL` | `INFO` |

`MODEL_PATH` may reference either the supplied `.pt` model or the supplied
`.onnx` export. The `.pt` model is the default. Only one model is loaded per
SmartPark process.

### Updating the model without rebuilding SmartPark

Keep model weights outside the application image and mount them into the
container at runtime. Configure each deployment using `MODEL_PATH` and give
every model release a distinct `MODEL_VERSION`:

```text
MODEL_PATH=/models/model.pt
MODEL_VERSION=parking-yolo-2026-09
```

To release a replacement model, place the new `.pt` or `.onnx` file in the
mounted model location, update `MODEL_PATH` and `MODEL_VERSION` if required,
then perform a rolling restart of the SmartPark pods. Each replacement pod
loads and validates the model before becoming ready. The container image does
not need to be rebuilt.

Use `GET /api/operator/model` to confirm the version, format, configured path,
and loaded state for the responding pod. Search-cache keys include the model
version, so results produced by an old model are not served after an update.

`CARPARK_COUNT` must be between 10 and 99. SmartPark generates logical IDs from
`CBD_001` through `CBD_N` and rejects IDs outside the active range.

Camera images for a search are fetched concurrently. Blocking model predictions
run in worker threads behind one shared per-process semaphore. Keep
`INFERENCE_CONCURRENCY=1` unless benchmarks show that the selected model backend
is safe and faster with a higher value.

SmartPark requires a reachable Redis server during startup. Redis stores recent
user activity, request events, latest car-park inference status, and short-lived
search cache entries. All SmartPark replicas must use the same `REDIS_URL`.

## Logging and request tracing

SmartPark and the camera simulator emit one-line JSON application logs. Every
HTTP request receives an `x-request-id`; a valid caller-provided value is
preserved, otherwise the service generates one. SmartPark returns this ID to the
client and forwards it, together with the user UUID when available, to the
camera simulator.

Completed-request logs include the HTTP method, path, response status, duration,
client address, request ID, and user UUID when available. Service logs emitted
during that request inherit the same correlation fields. Image bytes and base64
response bodies are never written to logs.

Uvicorn's default access log may be disabled to avoid a second, non-JSON access
line because the application already records structured access events:

```text
python -m uvicorn app.main:app --port 8000 --no-access-log
```

## Production SmartPark image

The production Docker build uses an allow-listed build context. Only the
`app/` package and pinned production requirements are sent into the build. The
model, image dataset, tests, virtual environment, notebooks, Git metadata, local
outputs, and environment files are excluded.

SmartPark uses the version-pinned `ultralytics/ultralytics:8.4.135-python`
CPU image. SmartPark performs CPU inference, and this base already provides a
compatible Ultralytics, PyTorch, and OpenCV stack. This keeps the Dockerfile
shorter and avoids rebuilding the largest dependencies. A versioned tag is used
instead of `latest` so that the same source produces a predictable environment.

Build from this `release` directory:

```text
docker build --tag smartpark-api:1.0.0 .
```

The container runs as the non-root user `smartpark` (UID 10001), starts one
Uvicorn worker, and exposes port 8000. Use one process per container and scale
with Kubernetes replicas; extra Uvicorn workers would load another copy of the
model into the same container.

The image intentionally contains no model. Mount one read-only at `/models` and
set its version. For local Docker testing while Redis and the camera simulator
are exposed on the host:

```powershell
$modelDirectory = (Resolve-Path .\model).Path

docker run --rm --name smartpark-api `
  --publish 8000:8000 `
  --mount "type=bind,source=$modelDirectory,target=/models,readonly" `
  --env MODEL_PATH=/models/model.pt `
  --env MODEL_VERSION=model-v1 `
  --env REDIS_URL=redis://host.docker.internal:6379/0 `
  --env CAMERA_BASE_URL=http://host.docker.internal:8001 `
  smartpark-api:1.0.0
```

In Docker Compose or Kubernetes, replace `host.docker.internal` with the
internal Service names, such as `redis` and `camera-simulator`. Do not expose
Redis publicly.

Verify the running container:

```text
curl http://localhost:8000/health/ready
curl http://localhost:8000/api/operator/model
```

Inspect the image configuration and contents:

```text
docker image inspect smartpark-api:1.0.0
docker run --rm --entrypoint sh smartpark-api:1.0.0 -c "find /app -maxdepth 3 -type f | sort"
```

### Camera and Redis containers

SmartPark and the camera simulator have separate Dockerfiles because they have
different source, dependencies, ports, and scaling behaviour. Redis uses the
official `redis:7-alpine` image and does not need a custom Dockerfile.

Build the camera simulator with its Dockerfile-specific allow-list:

```text
docker build --file camera.Dockerfile --tag smartpark-camera:1.0.0 .
```

The camera image contains `camera_simulator/`, its small shared logging module,
and the required image dataset. It does not contain SmartPark's APIs, Redis
client, tests, models, notebook, local environment, or result files.

Create a private network and persistent Redis volume:

```text
docker network create smartpark-network
docker volume create smartpark-redis-data
```

Start Redis and the camera simulator:

```text
docker run --detach --name smartpark-redis --network smartpark-network --volume smartpark-redis-data:/data redis:7-alpine redis-server --appendonly yes
docker run --detach --name camera-simulator --network smartpark-network --publish 8001:8001 smartpark-camera:1.0.0
```

Start SmartPark on the same network with an externally mounted model:

```powershell
$modelDirectory = (Resolve-Path .\model).Path

docker run --detach --name smartpark-api `
  --network smartpark-network `
  --publish 8000:8000 `
  --mount "type=bind,source=$modelDirectory,target=/models,readonly" `
  --env MODEL_PATH=/models/model.pt `
  --env MODEL_VERSION=model-v1 `
  --env REDIS_URL=redis://smartpark-redis:6379/0 `
  --env CAMERA_BASE_URL=http://camera-simulator:8001 `
  smartpark-api:1.0.0
```

The three-container request path is:

```text
Client -> SmartPark container -> Camera container
                         \-----> Redis container -> persistent volume
```

## Run the complete application with Docker Compose

Docker Compose is the simplest local workflow. It builds the two custom images,
starts the official Redis image, creates the internal network, and mounts the
model without copying it into the SmartPark image.

Place the externally supplied model at `model/model.pt`, then run from the
project root:

```text
docker compose up --build
```

Open `http://localhost:8000/docs`, `http://localhost:8000/dashboard`, or
`http://localhost:8000/health/ready`. Stop the environment with:

```text
docker compose down
```

Redis data is retained in the `smartpark_redis-data` named volume. To remove
that local data as well, use `docker compose down --volumes`.

## Deploy to GKE

The `kubernetes/` directory contains the camera, Redis, persistent storage,
SmartPark, health probes, internal Services, public LoadBalancer, and HPA
manifests. SmartPark uses these published images:

```text
australia-southeast2-docker.pkg.dev/causal-space-503901-p7/fit3184-a1/smartpark-api:v1
australia-southeast2-docker.pkg.dev/causal-space-503901-p7/fit3184-a1/smartpark-camera:v1
```

Before applying the manifests:

1. Enable Workload Identity Federation and the Cloud Storage FUSE CSI driver
   on the Standard GKE cluster.
2. Create the regional bucket `causal-space-503901-p7-smartpark-models`.
3. Upload the model as `model-v1/model.pt`.
4. Grant the `default/smartpark-model-reader` Kubernetes ServiceAccount the
   `roles/storage.objectViewer` role on that bucket.

The following commands perform that setup after the Standard cluster has been
created. Run them from the machine where `gcloud` and `kubectl` are configured:

```bash
gcloud config set project causal-space-503901-p7

gcloud storage buckets create \
  gs://causal-space-503901-p7-smartpark-models \
  --location=australia-southeast2 \
  --uniform-bucket-level-access

gcloud storage cp ./model/model.pt \
  gs://causal-space-503901-p7-smartpark-models/model-v1/model.pt

gcloud container clusters update fit3184-cluster \
  --zone=australia-southeast2-a \
  --workload-pool=causal-space-503901-p7.svc.id.goog

gcloud container node-pools update default-pool \
  --cluster=fit3184-cluster \
  --zone=australia-southeast2-a \
  --workload-metadata=GKE_METADATA

gcloud container clusters update fit3184-cluster \
  --zone=australia-southeast2-a \
  --update-addons=GcsFuseCsiDriver=ENABLED

gcloud container clusters get-credentials fit3184-cluster \
  --zone=australia-southeast2-a

PROJECT_NUMBER="$(gcloud projects describe causal-space-503901-p7 \
  --format='value(projectNumber)')"

gcloud storage buckets add-iam-policy-binding \
  gs://causal-space-503901-p7-smartpark-models \
  --member="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/causal-space-503901-p7.svc.id.goog/subject/ns/default/sa/smartpark-model-reader" \
  --role=roles/storage.objectViewer
```

Cloud Storage bucket names are globally unique. If a different bucket name is
required, update `bucketName` in `kubernetes/smartpark-deployment.yaml` as well.

Deploy the one-replica baseline environment:

```text
kubectl apply -k kubernetes
kubectl rollout status deployment/redis
kubectl rollout status deployment/camera-simulator
kubectl rollout status deployment/smartpark-api
kubectl port-forward deployment/smartpark-api 8000:8000
```

Run Locust against `http://localhost:8000` for the baseline. After collecting
the one-replica measurements, test three manually selected replicas:

```text
kubectl scale deployment/smartpark-api --replicas=3
kubectl rollout status deployment/smartpark-api
```

After recording the three-replica results, return to one replica, expose
SmartPark, and enable autoscaling:

```text
kubectl scale deployment/smartpark-api --replicas=1
kubectl apply -f kubernetes/smartpark-loadbalancer.yaml
kubectl apply -f kubernetes/smartpark-hpa.yaml
kubectl get service smartpark-public
kubectl get hpa smartpark-api
```

The LoadBalancer's external IP can take several minutes to appear. The camera
and Redis Services remain private inside the cluster.

### Locust

Install the test dependencies and start the Locust UI:

```text
python -m pip install -r requirements-test.txt
python -m locust -f locust/locustfile.py --host http://localhost:8000
```

Set `SMARTPARK_SCENARIO` to `find`, `annotate`, or `mixed` before starting
Locust. The benchmark script uses a fresh UUID for every request so Redis cache
hits do not hide YOLO inference cost. Use the same user levels, ramp-up rate,
and run duration for the 1, 2, 4, and 8 replica measurements.

### Submission packaging

The pretrained `.pt` and `.onnx` files must not be included in the submitted
ZIP. Keep `model/README.md` so the assessor knows where to place or upload the
external model. The model patterns in `.gitignore` prevent new model weights
from being added, but any weights already tracked by Git must be removed from
the ZIP or Git index separately.

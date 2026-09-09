# External model setup

Pretrained weights are intentionally excluded from the submitted project and
Docker images. SmartPark accepts Ultralytics-compatible `.pt` and `.onnx`
models. Each API process loads one model.

## Local Python or Docker Compose

Place the supplied model at:

```text
model/model.pt
```

The default local configuration and `compose.yaml` use this name. To use ONNX,
place it at `model/model.onnx` and change `MODEL_PATH` to that file. Also use a
distinct `MODEL_VERSION`, such as `model-v1-onnx`.

## Upload the model to Cloud Storage

The Kubernetes deployment mounts a regional Cloud Storage bucket with the GKE
Cloud Storage FUSE CSI driver. The bucket and cluster should use the same region.
The checked-in manifest expects:

```text
gs://causal-space-503901-p7-smartpark-models/model-v1/model.pt
```

From the repository root:

```powershell
$PROJECT_ID = "causal-space-503901-p7"
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$BUCKET = "$PROJECT_ID-smartpark-models"
gcloud config set project $PROJECT_ID

# Run only when the bucket does not already exist.
gcloud storage buckets create "gs://$BUCKET" `
  --location=australia-southeast2 `
  --uniform-bucket-level-access

gcloud storage cp .\model\model.pt "gs://$BUCKET/model-v1/model.pt"
gcloud storage ls -l "gs://$BUCKET/model-v1/"
```

Bucket names are globally unique. If the name changes, update `bucketName` in
`kubernetes/smartpark-deployment.yaml`.

## Enable the GKE mount

Enable Workload Identity Federation, node workload metadata and GCS FUSE on the
existing Standard cluster:

```powershell
gcloud container clusters update fit3184-cluster `
  --zone=australia-southeast2-a `
  --workload-pool=causal-space-503901-p7.svc.id.goog

gcloud container node-pools update default-pool `
  --cluster=fit3184-cluster `
  --zone=australia-southeast2-a `
  --workload-metadata=GKE_METADATA

gcloud container clusters update fit3184-cluster `
  --zone=australia-southeast2-a `
  --update-addons=GcsFuseCsiDriver=ENABLED
```

Create the Kubernetes ServiceAccount and grant it read-only bucket access:

```powershell
kubectl apply -f kubernetes/service-account.yaml

$PROJECT_ID = "causal-space-503901-p7"
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$BUCKET = "$PROJECT_ID-smartpark-models"

gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" `
  --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/default/sa/smartpark-model-reader" `
  --role="roles/storage.objectViewer"
```

`kubernetes/smartpark-deployment.yaml` mounts the bucket read-only at `/models`
and sets `MODEL_PATH=/models/model-v1/model.pt`. A replacement pod must load and
validate the model before becoming ready.

Verify the deployed model:

```powershell
kubectl rollout status deployment/smartpark-api --timeout=300s
kubectl port-forward service/smartpark-api 8000:80
Invoke-RestMethod "http://localhost:8000/api/operator/model"
```

The response should report `loaded: true`, `model_format: pt` and
`model_version: model-v1`.

## Update the deployed model

Upload a replacement under a new versioned path, then update `MODEL_PATH` and
`MODEL_VERSION` in `kubernetes/smartpark-deployment.yaml`:

```powershell
gcloud storage cp .\model\replacement.pt "gs://$BUCKET/model-v2/model.pt"
kubectl apply -f kubernetes/smartpark-deployment.yaml
kubectl rollout status deployment/smartpark-api --timeout=300s
```

Versioned paths simplify rollback and prevent old cached searches being reused.

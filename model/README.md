# External model setup

SmartPark accepts Ultralytics-compatible `.pt` and `.onnx` models. Model weights are excluded from Git and Docker images so models can be updated independently of the application.

Each SmartPark API process loads one configured model.

## Local development and Docker Compose

Place a compatible PyTorch model at:

```text
model/model.pt
```

This is the default used by the local configuration and `compose.yaml`.

To use ONNX instead:

1. Place the model at `model/model.onnx`.
2. Set `MODEL_PATH` to the ONNX file.
3. use a distinct `MODEL_VERSION`, such as `model-v1-onnx`.

Example:

```powershell
$env:MODEL_PATH = "model/model.onnx"
$env:MODEL_VERSION = "model-v1-onnx"
```

## Store the model in Cloud Storage

The Kubernetes deployment can mount a private Cloud Storage bucket using the GKE Cloud Storage FUSE CSI driver.

Choose your own values:

```powershell
$PROJECT_ID = "your-project-id"
$REGION = "your-gcp-region"
$BUCKET = "$PROJECT_ID-smartpark-models"

gcloud config set project $PROJECT_ID
```

Bucket names must be globally unique. Create a regional bucket:

```powershell
gcloud storage buckets create "gs://$BUCKET" `
  --location=$REGION `
  --uniform-bucket-level-access
```

Upload the model under a versioned path:

```powershell
gcloud storage cp `
  ".\model\model.pt" `
  "gs://$BUCKET/model-v1/model.pt"
```

Verify the object:

```powershell
gcloud storage ls -l "gs://$BUCKET/model-v1/"
```

Update `bucketName` in `kubernetes/smartpark-deployment.yaml` to match the selected bucket.

## Enable the GKE mount

Set the cluster details:

```powershell
$CLUSTER_NAME = "your-cluster-name"
$NODE_POOL = "default-pool"
$ZONE = "your-cluster-zone"
```

Enable Workload Identity Federation:

```powershell
gcloud container clusters update $CLUSTER_NAME `
  --zone=$ZONE `
  --workload-pool="$PROJECT_ID.svc.id.goog"
```

Enable workload metadata on the node pool:

```powershell
gcloud container node-pools update $NODE_POOL `
  --cluster=$CLUSTER_NAME `
  --zone=$ZONE `
  --workload-metadata=GKE_METADATA
```

Enable the Cloud Storage FUSE CSI driver:

```powershell
gcloud container clusters update $CLUSTER_NAME `
  --zone=$ZONE `
  --update-addons=GcsFuseCsiDriver=ENABLED
```

## Grant read-only model access

Create the Kubernetes ServiceAccount:

```powershell
kubectl apply -f kubernetes/service-account.yaml
```

Retrieve the project number:

```powershell
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID `
  --format="value(projectNumber)"
```

Grant the ServiceAccount read-only access to the model bucket:

```powershell
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" `
  --member="principal://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/$PROJECT_ID.svc.id.goog/subject/ns/default/sa/smartpark-model-reader" `
  --role="roles/storage.objectViewer"
```

The deployment mounts the bucket read-only at `/models`. Configure:

```yaml
- name: MODEL_PATH
  value: /models/model-v1/model.pt
- name: MODEL_VERSION
  value: model-v1
```

A SmartPark pod must successfully load the model before its readiness check passes.

## Verify the deployed model

Wait for the deployment:

```powershell
kubectl rollout status deployment/smartpark-api --timeout=300s
```

Forward the service locally:

```powershell
kubectl port-forward service/smartpark-api 8000:80
```

In another terminal:

```powershell
Invoke-RestMethod "http://localhost:8000/api/operator/model"
```

The response should report that the model is loaded and show its configured format and version.

## Update the model

Upload replacements under new versioned paths instead of overwriting the existing model:

```powershell
gcloud storage cp `
  ".\model\replacement.pt" `
  "gs://$BUCKET/model-v2/model.pt"
```

Update the deployment:

```yaml
- name: MODEL_PATH
  value: /models/model-v2/model.pt
- name: MODEL_VERSION
  value: model-v2
```

Apply the change:

```powershell
kubectl apply -f kubernetes/smartpark-deployment.yaml
kubectl rollout status deployment/smartpark-api --timeout=300s
```

Versioned paths make rollback straightforward and prevent cached results from one model version being reused by another.
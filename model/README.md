# External model location

The pretrained model is intentionally excluded from the submitted project artefact
and from the SmartPark container image.

For local Docker Compose use, place the selected model here as:

```text
model/model.pt
```

For GKE, upload it to:

```text
gs://causal-space-503901-p7-smartpark-models/model-v1/model.pt
```

The Kubernetes Deployment mounts that bucket at `/models` and configures
`MODEL_PATH=/models/model-v1/model.pt`. A `.onnx` file can be used instead by
changing `MODEL_PATH` and `MODEL_VERSION` in the deployment manifest.

# SmartPark

The project currently includes the modular SmartPark API skeleton and a separate
camera simulator that returns random images from the supplied dataset.

## Run locally

Create and activate a virtual environment, install the dependencies, then run:

```text
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The commands must be run from the `release` directory.

Health endpoints:

- `GET /health/live` confirms that the web process is running.
- `GET /health/ready` confirms that application startup has completed.

Core endpoint:

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
| `CAMERA_DATASET_PATH` | `<release>/images` |
| `CAMERA_LOG_LEVEL` | `INFO` |

`MODEL_PATH` may reference either the supplied `.pt` model or the supplied
`.onnx` export. The `.pt` model is the default. Only one model is loaded per
SmartPark process.

`CARPARK_COUNT` must be between 10 and 99. SmartPark generates logical IDs from
`CBD_001` through `CBD_N` and rejects IDs outside the active range.

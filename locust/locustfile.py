import os
from uuid import uuid4

from locust import HttpUser, between, task


SCENARIO = os.getenv("SMARTPARK_SCENARIO", "find").lower()
if SCENARIO not in {"find", "annotate", "mixed"}:
    raise ValueError("SMARTPARK_SCENARIO must be find, annotate, or mixed")


class SmartParkUser(HttpUser):
    """Generate uncached core-API traffic for repeatable scaling benchmarks."""

    wait_time = between(1, 3)

    @task
    def run_selected_scenario(self) -> None:
        if SCENARIO == "find":
            self.find_carparks()
        elif SCENARIO == "annotate":
            self.annotate_carpark()
        elif int(uuid4()) % 5:
            self.find_carparks()
        else:
            self.annotate_carpark()

    def find_carparks(self) -> None:
        # A new UUID prevents Redis from turning an inference benchmark into a
        # cache benchmark after each simulated user's first request.
        self.client.get(
            "/api/find-carparks",
            params={"uuid": f"locust-{uuid4()}", "n": 2},
            name="GET /api/find-carparks",
        )

    def annotate_carpark(self) -> None:
        self.client.get(
            "/api/annotate-carpark",
            params={"uuid": f"locust-{uuid4()}", "carpark_id": "CBD_001"},
            name="GET /api/annotate-carpark",
        )

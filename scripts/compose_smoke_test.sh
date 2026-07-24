#!/bin/sh
set -eu

python3 - <<'PY'
import json
import time
from urllib.request import Request, urlopen

base_url = "http://localhost:8000"


def wait_for_success(path: str, timeout_seconds: int = 45) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base_url}{path}", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError as error:
            last_error = error
        time.sleep(1)
    raise RuntimeError(f"{path} did not become ready within {timeout_seconds}s") from last_error


for path in ("/health", "/ready"):
    wait_for_success(path)

payload = {
    "customer_name": "Smoke Test",
    "customer_email": "smoke@example.com",
    "subject": "Compose smoke ticket",
    "description": "This ticket verifies the Docker Compose runtime path.",
    "category": "TECHNICAL",
}
request = Request(
    f"{base_url}/v1/tickets",
    data=json.dumps(payload).encode(),
    headers={"content-type": "application/json"},
    method="POST",
)
with urlopen(request, timeout=10) as response:
    assert response.status == 201
PY

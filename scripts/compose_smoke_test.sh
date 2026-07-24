#!/bin/sh
set -eu

python3 - <<'PY'
import json
from urllib.request import Request, urlopen

base_url = "http://localhost:8000"
for path in ("/health", "/ready"):
    with urlopen(f"{base_url}{path}", timeout=10) as response:
        assert response.status == 200

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

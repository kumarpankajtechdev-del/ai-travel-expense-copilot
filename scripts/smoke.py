"""Check an installed copy through real local HTTP, using disposable fictional data."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def main():
    with tempfile.TemporaryDirectory(prefix="tripledger-check-") as directory:
        env = dict(
            os.environ, TRIPLEDGER_PROVIDER="demo", TRIPLEDGER_DATA_DIR=directory, PYTHONNOUSERSITE="1"
        )
        env.pop("PYTHONPATH", None)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"

        def request(path, body=None):
            req = Request(
                base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=10) as response:
                raw = response.read()
                return (
                    json.loads(raw) if "application/json" in response.headers.get("Content-Type", "") else raw
                )

        def start(log):
            process = subprocess.Popen(
                [sys.executable, "-m", "expense_ai_copilot", "--port", str(port)],
                cwd=directory,
                env=env,
                stdout=log,
                stderr=log,
            )
            for _ in range(100):
                try:
                    assert request("/health")["mode"] == "demo"
                    return process
                except URLError:
                    if process.poll() is not None:
                        break
                    time.sleep(0.1)
            process.terminate()
            process.wait(timeout=10)
            raise RuntimeError(
                "Installed app did not start. Check the installation before running this script."
            )

        with (Path(directory) / "server.log").open("w") as log:
            process = start(log)
            try:
                assert b"TripLedger" in request("/")
                assert b"review-form" in request("/assets/app.js")
                assert b"--ink" in request("/assets/style.css")
                trip = request("/api/trips/london-weekend")
                assert trip["trip"]["spent_cents"] == 45420
                draft = request(
                    "/api/reviews",
                    {
                        "trip_id": "london-weekend",
                        "receipt_text": "Harbour Café\n2026-08-16\nDinner\nReference: 99999999\nTotal: GBP 32.50",
                    },
                )
                assert draft["status"] == "pending"
                fields = dict(draft["receipt"], acknowledge_warnings=False)
                saved = request("/api/reviews/" + draft["id"] + "/confirm", fields)
                assert request("/api/reviews/" + draft["id"] + "/confirm", fields)["id"] == saved["id"]
                result = request(
                    "/api/analytics", {"trip_id": "london-weekend", "question": "How much have I spent?"}
                )
                assert result["rows"][0]["value"] == 486.70
                answer = request(
                    "/api/rules/ask",
                    {"trip_id": "london-weekend", "question": "What is my daily meal budget?"},
                )
                assert any(source["id"] == "meal-limit" for source in answer["sources"])
                assert b"32.50" in request("/api/trips/london-weekend/export")
            finally:
                process.terminate()
                process.wait(timeout=10)
            process = start(log)
            try:
                assert request("/api/trips/london-weekend")["trip"]["spent_cents"] == 48670
            finally:
                process.terminate()
                process.wait(timeout=10)
    print(
        "PASS: installed assets, receipt review, confirmation, analytics, citations, CSV and restart persistence."
    )


if __name__ == "__main__":
    main()

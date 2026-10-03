import asyncio
import datetime
import json
import os
import random
import urllib.request
from urllib.parse import urlsplit

API = os.getenv("GRIDFORGE_TELEMETRY_URL", "http://127.0.0.1:8000/api/v1/telemetry")
if urlsplit(API).scheme != "http" or urlsplit(API).hostname not in {
    "localhost",
    "127.0.0.1",
    "::1",
}:
    raise ValueError("Prototype simulator target must be loopback HTTP")
ASSETS = {"CH-01": 920, "CP-02": 710, "EX-04": 1180, "CR-01": 1350, "PM-03": 390}


def send(payload: dict[str, str | float]) -> bytes:
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=2) as r:
        return bytes(r.read())


async def main() -> None:
    print("GridForge synthetic factory streaming at 1 Hz. Ctrl+C to stop.")
    while True:
        for asset, base in ASSETS.items():
            power = max(0, random.gauss(base, base * 0.035))
            if random.random() < 0.01:
                power *= random.uniform(1.15, 1.35)
            payload: dict[str, str | float] = {
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                "asset_id": asset,
                "voltage": random.gauss(415, 2),
                "current": power * 1000 / (1.732 * 415 * 0.92),
                "active_power_kw": power,
                "vibration": abs(random.gauss(2.4, 0.35)),
            }
            try:
                await asyncio.to_thread(send, payload)
            except Exception as e:
                print("API unavailable:", e)
                break
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())

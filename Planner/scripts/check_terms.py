import base64
import os
from pathlib import Path

import requests


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CLIENT_ID = os.environ.get("UMICH_SOC_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("UMICH_SOC_CLIENT_SECRET", "").strip()
if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit(
        "Missing UMICH_SOC_CLIENT_ID / UMICH_SOC_CLIENT_SECRET. "
        "Copy Planner/.env.example to Planner/.env and fill in your SOC API credentials."
    )

credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
resp = requests.post(
    "https://gw.api.it.umich.edu/um/oauth2/token",
    headers={"Authorization": f"Basic {credentials}"},
    data={"grant_type": "client_credentials", "scope": "umscheduleofclasses"},
)
token = resp.json()["access_token"]

terms = requests.get(
    "https://gw.api.it.umich.edu/um/Curriculum/SOC/Terms",
    headers={"Authorization": f"Bearer {token}"},
)
import pprint

pprint.pprint(terms.json())

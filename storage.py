import json
import re
from datetime import datetime
from pathlib import Path

RUNS_DIR = Path(__file__).parent / "runs"


def _slug(name):
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_") or "contract"


def save_run(contract_name, result, model):
    RUNS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{_slug(contract_name)}.json"
    path = RUNS_DIR / filename
    payload = {
        "contract_name": contract_name,
        "saved_at": timestamp,
        "model": model,
        "result": result,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_all_runs():
    RUNS_DIR.mkdir(exist_ok=True)
    runs = []
    for path in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            runs.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return runs

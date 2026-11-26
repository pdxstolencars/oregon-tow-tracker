"""Small JSON-based prototype archive; serializable and easy to inspect in GitHub."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archive" / "records.json"
STATE = ROOT / "archive" / "state.json"
REVIEW = ROOT / "archive" / "review.json"
SITE_DATA = ROOT / "site" / "data" / "records.json"

def read_json(path: Path, fallback):
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)

def save_record(record: dict):
    all_records = read_json(ARCHIVE, {})
    key = str(record["id"])
    now = datetime.now(timezone.utc).isoformat()
    old = all_records.get(key)
    data = {**record, "first_seen_at": old.get("first_seen_at", now) if old else now, "last_seen_at": now}
    # Don't erase manually verified map coordinates on subsequent source refreshes.
    if old and (data.get("lat") is None or data.get("lng") is None):
        if old.get("lat") is not None and old.get("lng") is not None:
            data["lat"], data["lng"] = old["lat"], old["lng"]
    if old:
        old_history = old.get("status_history", [])
        changed = old.get("status") != data.get("status")
        data["status_history"] = old_history + ([{"status": data.get("status", ""), "observed_at": now}] if changed else [])
    else:
        data["status_history"] = [{"status": data.get("status", ""), "observed_at": now}]
    all_records[key] = data
    write_json(ARCHIVE, all_records)
    return "updated" if old else "new"

def export_site():
    records = list(read_json(ARCHIVE, {}).values())
    records = [r for r in records if r.get("geo_scope") == "include"]
    records.sort(key=lambda r: (r.get("towed_at") or "", r.get("id") or ""), reverse=True)
    write_json(SITE_DATA, {"generated_at": datetime.now(timezone.utc).isoformat(), "records": records})
    return len(records)

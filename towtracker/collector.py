"""Conservative sequential AutoReturn collector. Never tries to bypass denied access.

Collection is OFF by default. A user must explicitly confirm they have permission
for automated retrieval; robots.txt is checked independently, and HTTP 403/429
stop the run. No cookies, proxies, browser spoofing, or challenge bypass.
"""
from __future__ import annotations
import argparse
import sys
import time
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser
import requests
from .archive import STATE, REVIEW, read_json, write_json, save_record, export_site
from .parser import parse_vehicle_html, ParseError

BASE = "https://search.autoreturn.com"
PATH = "/find-vehicle/details?vehicle={}"
AGENT = "OregonTowRecoveryTracker/0.1 (public-records research; contact: project owner)"

class CollectionBlocked(RuntimeError):
    pass

def check_robots(session: requests.Session):
    url = BASE + "/robots.txt"
    try:
        response = session.get(url, timeout=20)
    except requests.RequestException as exc:
        raise CollectionBlocked(f"Cannot verify robots.txt: {exc}") from exc
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise CollectionBlocked(f"Cannot verify robots.txt (HTTP {response.status_code}); stop")
    rules = RobotFileParser()
    rules.parse(response.text.splitlines())
    if not rules.can_fetch(AGENT, BASE + PATH.format(9994704)):
        raise CollectionBlocked("robots.txt does not allow these vehicle detail URLs")
    return rules

def fetch_one(session: requests.Session, vehicle_id: int, rules: RobotFileParser | None):
    url = BASE + PATH.format(vehicle_id)
    if rules and not rules.can_fetch(AGENT, url):
        raise CollectionBlocked(f"robots.txt disallows {url}")
    try:
        r = session.get(url, timeout=25)
    except requests.RequestException as exc:
        raise CollectionBlocked(f"Network failure at ID {vehicle_id}: {exc}") from exc
    if r.status_code in (401, 403, 429):
        raise CollectionBlocked(f"HTTP {r.status_code} at vehicle ID {vehicle_id}; stopping without attempting bypass")
    if r.status_code in (404, 410):
        return None
    if r.status_code != 200:
        raise CollectionBlocked(f"Unexpected HTTP {r.status_code} at ID {vehicle_id}; stopping")
    try:
        return parse_vehicle_html(r.text, vehicle_id)
    except ParseError as exc:
        raise CollectionBlocked(f"Cannot safely parse ID {vehicle_id}: {exc}") from exc

def run(start: int, end: int, delay: float, permission_confirmed: bool):
    if not permission_confirmed:
        raise CollectionBlocked("Automated collection is disabled until the project owner verifies permission (--authorized)")
    if end < start or start < 1 or end - start + 1 > 100:
        raise ValueError("Supply an ascending range of 1–100 IDs per manual test")
    if delay < 3:
        raise ValueError("Delay must be at least 3 seconds between requests")
    session = requests.Session()
    session.headers["User-Agent"] = AGENT
    rules = check_robots(session)
    state = read_json(STATE, {"last_processed_id": None, "runs": []})
    review = read_json(REVIEW, {})
    stats = {"new": 0, "updated": 0, "excluded": 0, "unconfirmed": 0, "missing": 0}
    error = None
    try:
        for vehicle_id in range(start, end + 1):
            record = fetch_one(session, vehicle_id, rules)
            if record is None:
                stats["missing"] += 1
            elif record["geo_scope"] == "include":
                stats[save_record(record)] += 1
            else:
                stats[record["geo_scope"]] += 1
                if record["geo_scope"] == "unconfirmed":
                    review[str(vehicle_id)] = {"id": str(vehicle_id), "evidence": record["geo_evidence"], "source_url": record["source_url"]}
                    write_json(REVIEW, review)
            state["last_processed_id"] = vehicle_id
            write_json(STATE, state)
            if vehicle_id < end:
                time.sleep(delay)
    except CollectionBlocked as exc:
        error = str(exc)
        raise
    finally:
        state["runs"].append({
            "start": start, "end": end,
            "last_processed_id": state.get("last_processed_id"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
            "status": "stopped" if error else "completed",
            "error": error,
        })
        state["runs"] = state["runs"][-100:]
        write_json(STATE, state)
        site_count = export_site()
        print(f"Processed IDs {start}–{end}: {stats}. Exported {site_count} Oregon records.")

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", type=int, default=9994605)
    ap.add_argument("--end", type=int, default=9994704)
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--authorized", action="store_true", help="Affirm automated access permission has been verified")
    args = ap.parse_args()
    try:
        run(args.start, args.end, args.delay, args.authorized)
    except (CollectionBlocked, ValueError) as exc:
        print("STOPPED:", exc, file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()

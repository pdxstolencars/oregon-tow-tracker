"""Import authorized, locally supplied record JSON (no website requests).

Accepted input: a JSON list of AutoReturn-like normalized dictionaries. Entries
are parsed and filtered in the same way as collector output.
"""
import argparse
from pathlib import Path
from .archive import save_record, export_site
from .normalize import oregon_scope, normalize_agency, classify_reason, parse_tow_datetime, vin_info, split_plate


def import_json(path):
    import json
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("records", [])
    imported = 0
    for row in rows:
        if not isinstance(row, dict) or not str(row.get("id", "")).isdigit():
            raise ValueError("Every row must have a numeric id")
        record = dict(row)
        record["id"] = str(row["id"])
        record["source_url"] = "https://search.autoreturn.com/find-vehicle/details?vehicle=" + record["id"]
        if "license" in record and not record.get("license_plate"):
            record["license_plate"], record["license_state"] = split_plate(record["license"])
        if "vin_masked" in record and not record.get("vin_last4"):
            record["vin"], record["vin_last4"] = vin_info(record["vin_masked"])
        if not record.get("towed_at"):
            record["towed_at"] = parse_tow_datetime(record.get("towed_at_raw", ""))
        record["agency"] = normalize_agency(record.get("towed_by", ""))
        record["reason_category"] = classify_reason(record.get("reason_raw", ""))
        record["geo_scope"], record["geo_evidence"] = oregon_scope(record.get("towed_from", ""), record.get("tow_company_address", ""), record.get("towed_by", ""))
        if record["geo_scope"] != "include":
            continue
        save_record(record)
        imported += 1
    count = export_site()
    print(f"Imported {imported} Oregon records; site now contains {count} records.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("json_path")
    args = ap.parse_args()
    import_json(args.json_path)

"""Normalization of AutoReturn data; never infer a confirmed theft from a generic tow."""
from __future__ import annotations
import re
from datetime import datetime
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")
# Recognize all US states; otherwise an out-of-state pickup in e.g. Texas
# could be falsely admitted merely because its tow yard is in Oregon.
STATES = dict(item.split(":", 1) for item in (
    "Alabama:AL", "Alaska:AK", "Arizona:AZ", "Arkansas:AR", "California:CA",
    "Colorado:CO", "Connecticut:CT", "Delaware:DE", "District of Columbia:DC",
    "Florida:FL", "Georgia:GA", "Hawaii:HI", "Idaho:ID", "Illinois:IL",
    "Indiana:IN", "Iowa:IA", "Kansas:KS", "Kentucky:KY", "Louisiana:LA",
    "Maine:ME", "Maryland:MD", "Massachusetts:MA", "Michigan:MI", "Minnesota:MN",
    "Mississippi:MS", "Missouri:MO", "Montana:MT", "Nebraska:NE", "Nevada:NV",
    "New Hampshire:NH", "New Jersey:NJ", "New Mexico:NM", "New York:NY",
    "North Carolina:NC", "North Dakota:ND", "Ohio:OH", "Oklahoma:OK",
    "Oregon:OR", "Pennsylvania:PA", "Rhode Island:RI", "South Carolina:SC",
    "South Dakota:SD", "Tennessee:TN", "Texas:TX", "Utah:UT", "Vermont:VT",
    "Virginia:VA", "Washington:WA", "West Virginia:WV", "Wisconsin:WI", "Wyoming:WY"
))
STATE_CODES_PATTERN = "(?:" + "|".join(sorted(set(STATES.values()))) + ")"
STATE_NAMES_PATTERN = "(?:" + "|".join(sorted(map(re.escape, STATES), key=len, reverse=True)) + ")"
PLATE_RE = re.compile(r"^(.+?)\s*[-–]\s*([A-Z]{2})$", re.I)
VIN_MASK_RE = re.compile(r"\*+\s*([A-Z0-9]{4})\s*$", re.I)

def compact(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

def split_plate(value: str) -> tuple[str, str]:
    text = (value or "").strip()
    match = PLATE_RE.match(text)
    if match:
        return match.group(1).strip().upper(), match.group(2).upper()
    return text.upper(), ""

def get_state(address: str) -> str:
    """Match state in a street/city address, not a license plate or tow agency."""
    text = (address or "").strip()
    patterns = [
        rf",\s*({STATE_CODES_PATTERN})\b",
        rf"\b({STATE_CODES_PATTERN})\s+\d{{5}}(?:-\d{{4}})?\b",
        rf",\s*({STATE_NAMES_PATTERN})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = match.group(1).upper()
            return STATES.get(value.title(), value)
    return ""

def normalize_agency(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "")).strip().upper()
    if re.search(r"\b(?:PORT OF PORTLAND|PORT POLICE|POPD)\b", text):
        return "PORT_POLICE"
    if re.search(r"\b(?:PPB|PORTLAND POLICE(?: BUREAU)?)\b", text):
        return "PPB"
    if re.search(r"\b(?:MCSO|MULTNOMAH COUNTY SHERIFF(?:'S)?(?: OFFICE)?)\b", text):
        return "MCSO"
    if re.search(r"\b(?:TRIMET|TRANSIT POLICE)\b", text):
        return "TRIMET"
    if re.search(r"\b(?:PBOT|PORTLAND BUREAU OF TRANSPORTATION)\b", text):
        return "PBOT"
    return "OTHER"

def classify_reason(reason: str) -> str:
    text = (reason or "").lower()
    if re.search(r"\b(?:not stolen|not reported stolen|possible stolen|suspected stolen)\b", text):
        return "needs_review"
    if re.search(r"\bstolen\b|\btheft\s+(?:recovery|recover(?:ed|y))\b|\brecovered\s+(?:stolen|theft)\b", text):
        return "stolen_recovery"
    if re.search(r"\b(?:ppi|prvt\s*prop|private\s*property)\b", text):
        return "private_property"
    if re.search(r"\babandon(?:ed|ment)?\b", text):
        return "abandoned"
    if re.search(r"\b(?:accident|collision|crash)\b", text):
        return "collision"
    if re.search(r"\b(?:parking|parked|construction zone|no[- ]parking|expired meter)\b", text):
        return "parking"
    if re.search(r"\b(?:impound|seized|evidence hold|investigation)\b", text):
        return "impound"
    if re.search(r"\b(?:traffic|hazard|disabled|blocking)\b", text):
        return "traffic"
    return "other"

def oregon_scope(towed_from: str, yard_address: str, towed_by: str = "") -> tuple[str, str]:
    """Return (include/exclude/unconfirmed, evidence).

    Explicit pickup state wins. An Oregon agency may establish geographic
    scope when the pickup lacks a state. A license plate's state is NOT proof
    of the tow location.
    """
    pickup_state = get_state(towed_from)
    yard_state = get_state(yard_address)
    if pickup_state:
        return ("include", "pickup_address_or") if pickup_state == "OR" else ("exclude", "pickup_out_of_state")
    if yard_state == "OR":
        return "include", "oregon_yard_only"
    if normalize_agency(towed_by) != "OTHER":
        return "include", "oregon_agency_only" if not yard_state else "oregon_agency_outside_yard"
    if yard_state:
        return "exclude", "yard_out_of_state"
    return "unconfirmed", "missing_geographic_evidence"

def parse_tow_datetime(value: str) -> str:
    value = re.sub(r"\s+", " ", (value or "").strip())
    for fmt in ("%m/%d/%y, %I:%M %p", "%m/%d/%Y, %I:%M %p", "%m/%d/%y %I:%M %p", "%m/%d/%Y %I:%M %p"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=PACIFIC).isoformat()
        except ValueError:
            continue
    return ""  # keep original text separately if a future format appears

def vin_info(text: str) -> tuple[str, str]:
    raw = (text or "").strip().upper()
    masked = VIN_MASK_RE.search(raw)
    if masked:
        return "", masked.group(1)
    token = compact(raw)
    if len(token) == 17 and not any(x in token for x in "IOQ"):
        return token, token[-4:]
    return "", ""

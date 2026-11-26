"""Best-effort parser for the AutoReturn Vehicle Details public page.

CAUTION: The site's HTML markup has NOT been retrieved in this environment (HTTP 403).
This parser is tested with representative fixtures, not confirmed live markup.
Fail closed on unexpected HTML so a redesign cannot silently create bad data.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from .normalize import split_plate, vin_info, parse_tow_datetime, normalize_agency, classify_reason, oregon_scope

LABELS = {
    "tr number": "tr_number", "license": "license", "vin": "vin",
    "vehicle": "vehicle", "towed date and time": "towed_date_time",
    "towed by": "towed_by", "towed from": "towed_from",
    "reason": "reason", "status": "status", "tow company": "tow_company",
}
SECTION_HEADINGS = {"tow details", "fee details", "vehicle details", "google maps"}
class ParseError(Exception):
    pass

def _clean(v: str) -> str:
    return re.sub(r"\s+", " ", (v or "")).strip()

def _key(v: str) -> str:
    return _clean(v).rstrip(":").casefold()

def _from_tabular(soup: BeautifulSoup) -> dict:
    result = {}
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) >= 2:
            label = _key(cells[0].get_text(" ", strip=True))
            if label in LABELS:
                result[LABELS[label]] = cells[1].get_text(" | ", strip=True)
    for dt in soup.find_all("dt"):
        label = _key(dt.get_text(" ", strip=True))
        dd = dt.find_next_sibling("dd")
        if label in LABELS and dd:
            result[LABELS[label]] = dd.get_text(" | ", strip=True)
    return result

def _from_strings(soup: BeautifulSoup) -> dict:
    tokens = [_clean(str(s)) for s in soup.stripped_strings]
    tokens = [t for t in tokens if t]
    result = {}
    for idx, token in enumerate(tokens):
        label = _key(token)
        if label not in LABELS:
            continue
        key = LABELS[label]
        following = []
        for candidate in tokens[idx + 1:]:
            if _key(candidate) in LABELS or _key(candidate) in SECTION_HEADINGS:
                break
            following.append(candidate)
        if following:
            result[key] = " | ".join(following[:8]) if key == "tow_company" else following[0]
    return result

def _fee_details(soup: BeautifulSoup) -> list[dict]:
    """Extract optional fee label/amount pairs without making them required.

    AutoReturn may present fee rows as a table or plain text. Capture any
    clearly labeled monetary amount following the Fee Details heading.
    This is deliberately conservative rather than guessing missing fees.
    """
    tokens = [_clean(str(x)) for x in soup.stripped_strings]
    start = next((i + 1 for i, text in enumerate(tokens) if _key(text) == "fee details"), None)
    if start is None:
        return []
    currency = re.compile(r"\$\s*\d[\d,]*(?:\.\d{2})?")
    collected = []
    pending = []
    for token in tokens[start:start + 80]:
        if _key(token) in SECTION_HEADINGS and _key(token) != "fee details":
            break
        if currency.search(token):
            # Can be "Impound Fee Standard $120.00" or separate tokens.
            match = currency.search(token)
            label_prefix = _clean(token[:match.start()]).rstrip(":")
            label = label_prefix or _clean(" ".join(pending))
            if label and len(label) < 150:
                item = {"label": label, "amount": match.group(0).replace(" ", "")}
                if item not in collected:
                    collected.append(item)
            pending = []
        else:
            if len(pending) < 4:
                pending.append(token)
    return collected


def _tow_company_phone(parts: list[str]) -> str:
    for part in parts[1:]:
        text = part.strip()
        if re.fullmatch(r"\+?1?[\s.()-]*\d{3}[\s.()-]*\d{3}[\s.-]*\d{4}", text):
            return text
    return ""


def parse_vehicle_html(html: str, vehicle_id: int) -> dict | None:
    if not html or len(html.strip()) < 60:
        raise ParseError("Blank or unusually short response")
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = _clean(soup.get_text(" ", strip=True)).lower()
    if "captcha" in title or "verify you are human" in title or "access denied" in title:
        raise ParseError("Access challenge; do not attempt to bypass")
    if any(s in title for s in ("no vehicle found", "vehicle not found", "no results found")):
        return None
    data = _from_strings(soup)
    data.update(_from_tabular(soup))
    required = ("vehicle", "towed_date_time", "reason", "tow_company")
    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ParseError(f"Vehicle details missing required fields: {', '.join(missing)}")
    company_parts = [p.strip() for p in data["tow_company"].split("|") if p.strip()]
    company_parts = [p for p in company_parts if _key(p) != "google maps"]
    company_name = company_parts[0] if company_parts else ""
    yard_address = next((p for p in company_parts[1:] if re.search(r",\s*[A-Z]{2}\b", p, re.I)), "")
    if not yard_address:
        yard_address = next((p for p in company_parts[1:] if re.search(r"\b(?:OR|WA|CA|CO|ID|NV)\s+\d{5}\b", p, re.I)), "")
    plate, plate_state = split_plate(data.get("license", ""))
    vin, vin_last4 = vin_info(data.get("vin", ""))
    scope, geographic_evidence = oregon_scope(data.get("towed_from", ""), yard_address, data.get("towed_by", ""))
    if not parse_tow_datetime(data["towed_date_time"]):
        raise ParseError("Tow date/time format is not recognized; inspect HTML before archiving")
    reason = data["reason"]
    return {
        "id": str(vehicle_id),
        "source_url": f"https://search.autoreturn.com/find-vehicle/details?vehicle={vehicle_id}",
        "tr_number": data.get("tr_number", ""),
        "license_plate": plate, "license_state": plate_state,
        "vin": vin, "vin_masked": data.get("vin", ""), "vin_last4": vin_last4,
        "vehicle": data["vehicle"],
        "towed_at_raw": data["towed_date_time"],
        "towed_at": parse_tow_datetime(data["towed_date_time"]),
        "towed_by": data.get("towed_by", ""),
        "agency": normalize_agency(data.get("towed_by", "")),
        "towed_from": data.get("towed_from", ""),
        "reason_raw": reason,
        "reason_category": classify_reason(reason),
        "status": data.get("status", ""),
        "tow_company": company_name,
        "tow_company_address": yard_address,
        "tow_company_phone": _tow_company_phone(company_parts),
        "fee_details": _fee_details(soup),
        "geo_scope": scope,
        "geo_evidence": geographic_evidence,
        "lat": None, "lng": None,
    }

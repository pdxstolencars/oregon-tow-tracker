# Oregon Tow & Recovery Tracker — PDX Stolen Cars

**Independent, separate project.** The Multnomah County jail-booking scraper is not used or modified.

A static GitHub Pages website plus a conservative Python sequential-ID AutoReturn collector. It is designed to archive **Oregon tow events** and make them searchable by license plate, available VIN digits, vehicle description, agency, tow date, and reason. A history timeline and Google Maps pickup-location view are included.

> **Status:** Starter code with offline-tested parsing. **Live AutoReturn HTML has not been verified** from this environment (web access attempts returned HTTP 403). The first collector run must be supervised. The website uses prominently marked **fictional demo records** whenever no real records have been archived.

## What's included

- `towtracker/collector.py`: checks ascending numeric `vehicle=` IDs, one at a time, conservatively (3-second minimum delay), within a manually chosen 1–100 ID range.
- `towtracker/parser.py`: extracts visible record fields and optional fee details.
- `towtracker/normalize.py`: identifies Oregon by the **tow pickup address if it includes a state**, otherwise the storage yard's state or Oregon-specific towing agency; normalizes agencies (`PPB`, `MCSO`, `TRIMET`, `PORT_POLICE`, `PBOT`) and tow reasons.
- `archive/`: immutable-in-ID records and observed status changes, plus a checkpoint and an inconclusive-location review queue.
- `site/`: search, date/agency/reason filters (including private-property impounds), newest-first sorting, stolen recoveries, possible vehicle history matches, and Google Maps.
- `.github/workflows/`: offline tests, a **manual-only** collector, and optional GitHub Pages publishing.

## Record fields

`id`, `source_url`, `tr_number`, `license_plate`, `license_state`, `vin` (only if really visible), `vin_masked` (original masked value), `vin_last4`, `vehicle`, `towed_at_raw`, `towed_at`, `towed_by`, `agency`, `towed_from`, `reason_raw`, `reason_category`, `status`, `tow_company`, `tow_company_address`, `tow_company_phone`, optional `fee_details` (`label`, `amount`), `geo_scope`, `geo_evidence`, `lat`, `lng`, `first_seen_at`, `last_seen_at`, and `status_history`.

**Never label an unspecified impound as stolen.** `stolen_recovery` means the public source explicitly contains theft/stolen recovery wording; it is not independent theft verification. The source masks VINs; suffix-only matches are *not* complete VIN confirmations.

## Get it on GitHub

1. Create a **new** public repository, e.g. `oregon-tow-tracker`. Do not reuse the jail scraper repository.
2. Upload all project files from this folder to the new repository **including `.github/workflows`**. Commit to the `main` branch.
3. In **Actions**, run **Test Oregon Tow Tracker**. The offline tests should pass without network access.
4. Open **Actions → Collect Oregon Tow IDs (manual) → Run workflow**. The initial test range is `9994605` through `9994704` (100 potential IDs). Leave `confirm_authorized` unchecked unless the owner has established permission. **The job will stop** if AutoReturn or robots.txt disallows automated access, the site challenges access, or expected HTML fields are missing. We don't attempt to evade restrictions.
5. Examine the Actions logs, `archive/records.json`, `archive/review.json`, and `site/data/records.json`. Only confirmed Oregon records are published. A row with an Oregon lot but incomplete pickup address is admitted with `geo_evidence=oregon_yard_only`; check before concluding it's a Portland tow.
6. To publish, open **Settings → Pages → Build and deployment → Source: GitHub Actions**. Run the **Publish Oregon Tow Tracker (GitHub Pages)** action or push to `main`.
7. The web interface can also be tested locally: `python -m http.server 8000 --directory site`, then open `http://localhost:8000`.

## Google Maps

By default the map tab offers **working links to Google Maps**, with no API key. To enable an **interactive embedded map**, put a Google Maps **JavaScript API** browser key in `site/config.js`. Restrict the key by HTTP referrer to your specific GitHub Pages domain and by API to Maps JavaScript API; enable billing if required. The demo geocodes at most 25 text addresses per view, and map pins should be pre-geocoded for larger datasets.

Map markers mean **reported tow pickup locations**, *not* proven original theft locations. The tow-company yard address is used for filtering, not for the pickup-location markers.

## Collector behavior and limits

- Website access ≠ automated HTTP access. In earlier tests the website returned `HTTP 403`; if GitHub encounters the same response it stops. Confirm access with the provider rather than changing identity, proxies, or bypassing challenges.
- Only ranges of 1–100 IDs are allowed, at least 3 seconds apart; start with a very small batch when verifying the parser, e.g. `9994704`–`9994704`.
- No schedule is enabled until a supervised successful run confirms stable behavior.
- If an error occurs midway through the manual run, the workflow commits records and a checkpoint from completed IDs, then marks the run as failed. Repeat from the first unprocessed ID when access is restored.
- Historic tow status is a snapshot of what the source shows when checked; rechecking known records is needed to observe later releases. This starter **does not yet recheck old records automatically**.
- No real tow data is included in this ZIP. Example records in `site/data/demo.json` are deliberately fictional.
- Potential matches across tow events based on plate/state/model are labeled **possible** because license plates can be reused and VINs are masked.
- Before publicly displaying plate/location details, confirm the precise scope of your data-use permission and applicable privacy requirements.

## Local setup

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
# after confirming authorized collection:
python -m towtracker.collector --start 9994704 --end 9994704 --authorized
# or import normalized test data:
python -m towtracker.import_records your-oregon-records.json
python -m http.server 8000 --directory site
```

### Future work

Once AutoReturn's live HTML and fetch behavior are verified: tune parser against saved authorized HTML; add steady incremental collection and periodic status rechecks; create a geocoding cache; add Portland-versus-rest-of-Oregon area switches; record precise agency codes and reason variants seen in the wild; and introduce privacy review/suppression controls.

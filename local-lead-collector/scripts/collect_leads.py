#!/usr/bin/env python3
"""Collect B2B leads for one place and one business category from OpenStreetMap.

Examples:
  python3 collect_leads.py --place "Al Barsha, Dubai" --category dentist --out leads.csv
  python3 collect_leads.py --place "Kallio, Helsinki" --category cafe --emails --max-sites 20
  python3 collect_leads.py --bbox 25.10,55.18,25.13,55.21 --tag office=it --out it.csv

Prints a compact JSON summary (and the first rows) to stdout, so Claude reads a
few hundred tokens instead of whole web pages. The full table goes to the CSV.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from categories import parse_tag, resolve
from dedupe import dedupe
from email_lookup import EmailFinder, LookupStats, is_role_address
from overpass import SearchArea, element_to_row, geocode, search
from polite_http import FetchError, PoliteClient

COLUMNS = [
    "name", "category", "website", "phone", "email", "email_source", "address",
    "opening_hours", "lat", "lon", "osm_url", "source", "collected_at",
]
SOURCE_NOTE = "OpenStreetMap contributors (ODbL)"


PHONE_RE = re.compile(r"\+?[0-9][0-9 ()./-]*")


def safe_cell(value: str) -> str:
    """Stop text from a map or web page running as a spreadsheet formula.

    A plain phone number like +971 4 000 0000 is left alone: it cannot run as a formula.
    """
    if value and value[0] in ("+", "-") and PHONE_RE.fullmatch(value[1:] if value[0] == "-" else value):
        return value
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def write_csv(rows: List[Dict[str, str]], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: safe_cell(str(row.get(k, ""))) for k in COLUMNS})


def parse_bbox(text: str):
    parts = [float(p) for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError("--bbox needs south,west,north,east")
    s, w, n, e = parts
    if not (s < n and w < e):
        raise ValueError("--bbox must be south,west,north,east with south<north and west<east")
    return s, w, n, e


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--place", help='place name, e.g. "Al Barsha, Dubai"')
    where.add_argument("--bbox", help="south,west,north,east in decimal degrees")
    p.add_argument("--radius", type=int,
                   help="search a circle of this many metres around the place's centre instead of its "
                        "boundary (point-only places use 2000 by default)")
    p.add_argument("--category", action="append", default=[], help="plain-English category (repeatable)")
    p.add_argument("--tag", action="append", default=[], help="raw OSM tag key=value (repeatable)")
    p.add_argument("--limit", type=int, default=200, help="max rows kept after dedupe (default 200)")
    p.add_argument("--require", choices=["website", "phone", "email", "any-contact"],
                   help="keep only rows that have this")
    p.add_argument("--emails", action="store_true", help="look up a role email on company websites")
    p.add_argument("--max-sites", type=int, default=25, help="cap on websites visited per run (default 25)")
    p.add_argument("--delay", type=float, default=2.0, help="seconds between requests to one host (min 1)")
    p.add_argument("--out", default="leads.csv", help="CSV path (default leads.csv)")
    p.add_argument("--preview", type=int, default=10, help="rows to print in the summary (default 10)")
    return p


def collect(args: argparse.Namespace, client: Optional[PoliteClient] = None) -> Dict:
    tags = [t for c in args.category for t in resolve(c)] + [parse_tag(t) for t in args.tag]
    if not tags:
        raise ValueError("give at least one --category or --tag")
    client = client or PoliteClient(min_delay=max(1.0, args.delay))

    if args.place:
        area = geocode(args.place, client, radius=args.radius)
    else:
        area = SearchArea(label=f"bbox {args.bbox}", bbox=parse_bbox(args.bbox))

    elements = search(area, tags, client)
    rows = [r for r in (element_to_row(el, tags) for el in elements) if r]
    unnamed = len(elements) - len(rows)
    rows = dedupe(rows)
    duplicates = len(elements) - unnamed - len(rows)
    rows.sort(key=lambda r: (not r["website"], not r["phone"], r["name"].lower()))

    # Same privacy rule for emails mappers put on OSM: role addresses only.
    osm_personal_dropped = 0
    for row in rows:
        if row["email"] and not is_role_address(row["email"]):
            row["email"], row["email_source"] = "", ""
            osm_personal_dropped += 1

    stats = LookupStats()
    if args.emails:
        # Company sites get a client of their own: same politeness, but only one retry,
        # so a dead domain or a "slow down" answer costs seconds, not minutes.
        web_client = client if client.opener else PoliteClient(min_delay=client.min_delay, max_retries=1)
        finder = EmailFinder(web_client)
        visited = 0
        for row in rows:
            if row["email"] or not row["website"]:
                continue
            if visited >= args.max_sites:
                stats.notes.append(f"stopped at --max-sites {args.max_sites}")
                break
            visited += 1
            email = finder.find(row["website"], stats)
            if email:
                row["email"], row["email_source"] = email, "company website"

    if args.require == "any-contact":
        rows = [r for r in rows if r["website"] or r["phone"] or r["email"]]
    elif args.require:
        rows = [r for r in rows if r[args.require]]
    rows = rows[: args.limit]

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for row in rows:
        row["source"], row["collected_at"] = SOURCE_NOTE, stamp
    write_csv(rows, args.out)

    return {
        "area": area.label,
        "search_mode": "admin area" if area.area_id else ("bounding box" if area.bbox else "radius"),
        "osm_tags": [f"{k}={v}" for k, v in tags],
        "features_returned": len(elements),
        "unnamed_skipped": unnamed,
        "duplicates_merged": duplicates,
        "rows_written": len(rows),
        "with_website": sum(1 for r in rows if r["website"]),
        "with_phone": sum(1 for r in rows if r["phone"]),
        "with_email": sum(1 for r in rows if r["email"]),
        "personal_emails_dropped_from_osm": osm_personal_dropped,
        "email_lookup": vars(stats) if args.emails else "off",
        "csv": args.out,
        "preview": [
            {k: r[k] for k in ("name", "phone", "email", "website", "address")} for r in rows[: args.preview]
        ],
        "attribution": "Data (c) OpenStreetMap contributors, ODbL. Credit OSM if you share it.",
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = collect(args)
    except (KeyError, ValueError, LookupError) as exc:
        print(json.dumps({"error": str(exc).strip("'\"")}), file=sys.stderr)
        return 2
    except (FetchError, RuntimeError) as exc:
        print(json.dumps({"error": f"network or Overpass problem: {exc}. Wait a minute and retry."}),
              file=sys.stderr)
        return 3
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

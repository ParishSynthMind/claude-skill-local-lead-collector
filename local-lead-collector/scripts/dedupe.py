"""Merge duplicate businesses.

OSM often has the same business twice: a point for the shop and an outline for
its building, or two mappers adding it. Two rows are the same business when
- they share a website domain and a similar name, or
- their names normalise to the same text and they sit within 150 m of each other.
The merged row keeps the first non-empty value of every field.
"""
from __future__ import annotations

import math
import re
import unicodedata
import urllib.parse
from typing import Dict, List

STOPWORDS = {
    "the", "and", "llc", "l.l.c", "fz", "fze", "fzco", "ltd", "limited", "co", "company",
    "center", "centre", "clinic", "clinics", "dental", "medical", "dr", "dmcc",
}


def norm_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.replace(".", ""))
    words = [w for w in text.split() if w not in STOPWORDS]
    return " ".join(words) or text.strip()


def site_domain(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    host = urllib.parse.urlsplit(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def distance_m(a: Dict[str, str], b: Dict[str, str]) -> float:
    try:
        lat1, lon1, lat2, lon2 = (float(a["lat"]), float(a["lon"]), float(b["lat"]), float(b["lon"]))
    except (KeyError, ValueError):
        return math.inf
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _similar(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def same_business(a: Dict[str, str], b: Dict[str, str], max_metres: float = 150.0) -> bool:
    na, nb = norm_name(a["name"]), norm_name(b["name"])
    da, db = site_domain(a.get("website", "")), site_domain(b.get("website", ""))
    if da and da == db and _similar(na, nb):
        return True
    return na == nb and distance_m(a, b) <= max_metres


def merge(a: Dict[str, str], b: Dict[str, str]) -> Dict[str, str]:
    out = dict(a)
    for key, value in b.items():
        if not out.get(key) and value:
            out[key] = value
    return out


def dedupe(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    kept: List[Dict[str, str]] = []
    for row in rows:
        for i, existing in enumerate(kept):
            if same_business(existing, row):
                kept[i] = merge(existing, row)
                break
        else:
            kept.append(dict(row))
    return kept

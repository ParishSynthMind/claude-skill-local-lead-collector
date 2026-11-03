"""Find businesses in OpenStreetMap: place name -> search area -> Overpass query -> rows.

Two free public services, no key or account:
- Nominatim (geocoding) turns "Al Barsha, Dubai" into an OSM area or a point.
  Usage policy: at most 1 request a second, identify yourself. We make ONE call per run.
- Overpass API returns map features with the tags we ask for.
  Usage policy: modest queries, back off when told to (429/504).
"""
from __future__ import annotations

import json
import os
import urllib.parse
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from polite_http import FetchError, PoliteClient

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
# The main public instance first, then a community mirror if the first can't be reached.
OVERPASS_URLS = [
    u.strip()
    for u in os.environ.get(
        "OVERPASS_URL", "https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter"
    ).split(",")
    if u.strip()
]

Tag = Tuple[str, str]


@dataclass
class SearchArea:
    """Where to search. Exactly one of area_id / bbox / around is used."""

    label: str
    area_id: Optional[int] = None
    bbox: Optional[Tuple[float, float, float, float]] = None  # south, west, north, east
    around: Optional[Tuple[float, float, int]] = None  # lat, lon, radius metres

    def filter(self) -> str:
        if self.area_id is not None:
            return "(area.searchArea)"
        if self.bbox is not None:
            s, w, n, e = self.bbox
            return f"({s},{w},{n},{e})"
        if self.around is not None:
            lat, lon, radius = self.around
            return f"(around:{int(radius)},{lat},{lon})"
        raise ValueError("search area has no area, bbox or point")


def geocode(place: str, client: PoliteClient, radius: Optional[int] = None) -> SearchArea:
    """Resolve a place name with one Nominatim call."""
    query = urllib.parse.urlencode({"q": place, "format": "jsonv2", "limit": 1})
    resp = client.request(f"{NOMINATIM_URL}?{query}", min_delay=1.0)
    results = json.loads(resp.text())
    if not results:
        raise LookupError(f"OpenStreetMap could not find a place called '{place}'")
    hit = results[0]
    return area_from_nominatim(hit, radius=radius)


def area_from_nominatim(hit: Dict, radius: Optional[int] = None) -> SearchArea:
    """radius=None: follow the place's own boundary. A radius: circle around its centre."""
    label = hit.get("display_name", "")
    if radius:
        return SearchArea(label=label, around=(float(hit["lat"]), float(hit["lon"]), int(radius)))
    osm_type, osm_id = hit.get("osm_type"), int(hit.get("osm_id", 0))
    bbox = None
    if hit.get("boundingbox"):
        s, n, w, e = (float(x) for x in hit["boundingbox"])
        bbox = (s, w, n, e)
    if osm_type == "relation":
        # Overpass area ids are the relation id + 3,600,000,000 (ways: + 2,400,000,000).
        return SearchArea(label=label, area_id=3_600_000_000 + osm_id, bbox=bbox)
    if osm_type == "way" and bbox:
        return SearchArea(label=label, bbox=bbox)
    # A point (e.g. a neighbourhood tagged only as a node): search a circle around it.
    return SearchArea(label=label, around=(float(hit["lat"]), float(hit["lon"]), 2000))


def build_query(area: SearchArea, tags: Sequence[Tag], timeout: int = 60) -> str:
    if not tags:
        raise ValueError("no tags to search for")
    lines = [f"[out:json][timeout:{int(timeout)}];"]
    if area.area_id is not None:
        lines.append(f"area(id:{area.area_id})->.searchArea;")
    lines.append("(")
    for key, value in tags:
        lines.append(f'  nwr["{key}"="{value}"]{area.filter()};')
    lines.append(");")
    lines.append("out center tags;")
    return "\n".join(lines)


def run_query(query: str, client: PoliteClient) -> List[Dict]:
    data = urllib.parse.urlencode({"data": query}).encode()
    last_error: Exception = FetchError("no Overpass endpoint configured")
    for url in OVERPASS_URLS:
        try:
            resp = client.request(url, data=data, min_delay=5.0, timeout=90)
            break
        except FetchError as exc:
            # Only move to the mirror when the server could not be reached at all.
            # A 429 "slow down" is retried inside the client and is not dodged by switching.
            if "could not reach" not in str(exc):
                raise
            last_error = exc
    else:
        raise last_error
    payload = json.loads(resp.text())
    remark = payload.get("remark") or ""
    if "runtime error" in remark.lower():
        raise RuntimeError(f"Overpass error: {remark}")
    return payload.get("elements", [])


def search(area: SearchArea, tags: Sequence[Tag], client: PoliteClient) -> List[Dict]:
    """Query the area; if an admin area returns nothing, retry once with its bounding box."""
    elements = run_query(build_query(area, tags), client)
    if not elements and area.area_id is not None and area.bbox is not None:
        fallback = SearchArea(label=area.label, bbox=area.bbox)
        elements = run_query(build_query(fallback, tags), client)
    return elements


def _first(tags: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = tags.get(key)
        if value:
            return value.split(";")[0].strip()
    return ""


def element_to_row(el: Dict, tags_searched: Sequence[Tag]) -> Optional[Dict[str, str]]:
    """Turn one Overpass element into a lead row. Unnamed features are skipped."""
    tags = el.get("tags", {}) or {}
    name = tags.get("name:en") or tags.get("name") or ""
    if not name.strip():
        return None
    lat = el.get("lat", (el.get("center") or {}).get("lat"))
    lon = el.get("lon", (el.get("center") or {}).get("lon"))
    category = next((f"{k}={v}" for k, v in tags_searched if tags.get(k) == v), "")
    address = ", ".join(
        part
        for part in (
            " ".join(p for p in (tags.get("addr:housenumber", ""), tags.get("addr:street", "")) if p),
            tags.get("addr:suburb", "") or tags.get("addr:district", ""),
            tags.get("addr:city", ""),
            tags.get("addr:postcode", ""),
        )
        if part
    )
    email = _first(tags, "email", "contact:email")
    return {
        "name": name.strip(),
        "category": category,
        "website": _first(tags, "website", "contact:website", "url"),
        "phone": _first(tags, "phone", "contact:phone", "contact:mobile"),
        "email": email,
        "email_source": "openstreetmap" if email else "",
        "address": address,
        "opening_hours": tags.get("opening_hours", ""),
        "lat": f"{lat:.6f}" if isinstance(lat, (int, float)) else "",
        "lon": f"{lon:.6f}" if isinstance(lon, (int, float)) else "",
        "osm_url": f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
    }

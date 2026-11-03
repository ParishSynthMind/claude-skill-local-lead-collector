"""Plain-English business categories mapped to OpenStreetMap tags.

OSM tags a business with key=value pairs (amenity=dentist, shop=bakery...).
A category can match several tags, because mappers are not always consistent.
Anything not listed here can still be searched with --tag key=value.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

Tag = Tuple[str, str]

CATEGORIES: Dict[str, List[Tag]] = {
    "dentist": [("amenity", "dentist"), ("healthcare", "dentist")],
    "doctor": [("amenity", "doctors"), ("healthcare", "doctor")],
    "clinic": [("amenity", "clinic"), ("healthcare", "clinic")],
    "pharmacy": [("amenity", "pharmacy"), ("healthcare", "pharmacy")],
    "veterinary": [("amenity", "veterinary")],
    "physiotherapist": [("healthcare", "physiotherapist")],
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "bar": [("amenity", "bar"), ("amenity", "pub")],
    "hotel": [("tourism", "hotel")],
    "gym": [("leisure", "fitness_centre")],
    "hairdresser": [("shop", "hairdresser")],
    "beauty": [("shop", "beauty")],
    "bakery": [("shop", "bakery")],
    "car_repair": [("shop", "car_repair")],
    "car_dealer": [("shop", "car")],
    "estate_agent": [("office", "estate_agent")],
    "lawyer": [("office", "lawyer")],
    "accountant": [("office", "accountant")],
    "insurance": [("office", "insurance")],
    "it_company": [("office", "it")],
    "architect": [("office", "architect")],
    "school": [("amenity", "school")],
    "kindergarten": [("amenity", "kindergarten")],
    "driving_school": [("amenity", "driving_school")],
    "florist": [("shop", "florist")],
    "optician": [("shop", "optician"), ("healthcare", "optometrist")],
    "electronics": [("shop", "electronics")],
    "furniture": [("shop", "furniture")],
    "supermarket": [("shop", "supermarket")],
}

ALIASES: Dict[str, str] = {
    "dentists": "dentist",
    "dental": "dentist",
    "dental clinic": "dentist",
    "dental clinics": "dentist",
    "doctors": "doctor",
    "gp": "doctor",
    "clinics": "clinic",
    "pharmacies": "pharmacy",
    "vet": "veterinary",
    "vets": "veterinary",
    "physio": "physiotherapist",
    "restaurants": "restaurant",
    "cafes": "cafe",
    "coffee shop": "cafe",
    "pubs": "bar",
    "hotels": "hotel",
    "gyms": "gym",
    "fitness": "gym",
    "salon": "hairdresser",
    "hair salon": "hairdresser",
    "beauty salon": "beauty",
    "garage": "car_repair",
    "real estate": "estate_agent",
    "real estate agent": "estate_agent",
    "estate agents": "estate_agent",
    "law firm": "lawyer",
    "lawyers": "lawyer",
    "accountants": "accountant",
    "accounting": "accountant",
    "it": "it_company",
    "software company": "it_company",
    "schools": "school",
    "nursery": "kindergarten",
    "opticians": "optician",
}


def resolve(category: str) -> List[Tag]:
    """Return the OSM tags for a category name, or raise KeyError with help."""
    key = category.strip().lower().replace("-", " ")
    key = ALIASES.get(key, key).replace(" ", "_")
    if key in CATEGORIES:
        return list(CATEGORIES[key])
    raise KeyError(
        f"unknown category '{category}'. Known: {', '.join(sorted(CATEGORIES))}. "
        "Or pass an OSM tag directly with --tag key=value."
    )


def parse_tag(text: str) -> Tag:
    if "=" not in text:
        raise ValueError(f"--tag must look like key=value, got '{text}'")
    key, value = text.split("=", 1)
    key, value = key.strip(), value.strip()
    if not key or not value or not _safe(key) or not _safe(value):
        raise ValueError(f"--tag has unsupported characters: '{text}'")
    return key, value


def _safe(part: str) -> bool:
    # Overpass QL is a query language; keep tag text to a harmless alphabet.
    return all(ch.isalnum() or ch in "_:-. " for ch in part)

import json
import urllib.error

import pytest

import overpass
from conftest import make_client
from overpass import SearchArea, area_from_nominatim, build_query, element_to_row

TAGS = [("amenity", "dentist"), ("healthcare", "dentist")]


def test_area_from_relation_uses_overpass_area_id(fixture_json):
    area = area_from_nominatim(fixture_json("nominatim_relation.json")[0])
    assert area.area_id == 3_600_000_000 + 4479752
    assert area.bbox == (25.07, 55.125, 25.095, 55.155)


def test_area_from_way_and_node():
    way = area_from_nominatim({"osm_type": "way", "osm_id": 5, "boundingbox": ["1", "2", "3", "4"]})
    assert way.bbox == (1.0, 3.0, 2.0, 4.0) and way.area_id is None
    node = area_from_nominatim({"osm_type": "node", "osm_id": 7, "lat": "25.1", "lon": "55.2"})
    assert node.around == (25.1, 55.2, 2000)


def test_explicit_radius_overrides_boundary(fixture_json):
    area = area_from_nominatim(fixture_json("nominatim_relation.json")[0], radius=3000)
    assert area.around == (25.0805, 55.1403, 3000) and area.area_id is None


def test_build_query_area_and_bbox():
    q = build_query(SearchArea("x", area_id=3600000001), TAGS)
    assert "area(id:3600000001)->.searchArea;" in q
    assert 'nwr["healthcare"="dentist"](area.searchArea);' in q
    assert q.endswith("out center tags;")
    q2 = build_query(SearchArea("x", bbox=(1, 2, 3, 4)), TAGS[:1])
    assert 'nwr["amenity"="dentist"](1,2,3,4);' in q2
    q3 = build_query(SearchArea("x", around=(25.1, 55.2, 900)), TAGS[:1])
    assert "(around:900,25.1,55.2)" in q3


def test_element_to_row(fixture_json):
    els = fixture_json("overpass_dentists.json")["elements"]
    row = element_to_row(els[0], TAGS)
    assert row["name"] == "Bright Smile Dental Clinic"
    assert row["address"] == "12 Harbour Walk, Sample City"
    assert row["category"] == "amenity=dentist"
    assert row["osm_url"] == "https://www.openstreetmap.org/node/101"
    way = element_to_row(els[1], TAGS)
    assert way["lat"] == "25.080200" and way["category"] == "healthcare=dentist"
    assert element_to_row(els[3], TAGS) is None  # unnamed
    email_row = element_to_row(els[4], TAGS)
    assert email_row["email"] == "hello@harbourdental.example" and email_row["email_source"] == "openstreetmap"


def test_search_falls_back_to_bbox_when_area_empty():
    bodies = [json.dumps({"elements": []}), json.dumps({"elements": [{"type": "node", "id": 1}]})]
    client, web = make_client({"https://overpass-api.de": lambda req: bodies.pop(0)})
    area = SearchArea("x", area_id=3600000001, bbox=(1, 2, 3, 4))
    assert len(overpass.search(area, TAGS, client)) == 1
    assert len(web.calls) == 2


def test_overpass_runtime_error_raises():
    client, _ = make_client({"https://overpass-api.de": json.dumps({"elements": [], "remark": "runtime error: timeout"})})
    with pytest.raises(RuntimeError):
        overpass.run_query("q", client)


def test_mirror_used_only_when_main_unreachable():
    client, web = make_client({
        "https://overpass-api.de": urllib.error.URLError("handshake failure"),
        "https://overpass.private.coffee": json.dumps({"elements": [{"id": 9}]}),
    }, max_retries=0)
    assert overpass.run_query("q", client) == [{"id": 9}]
    assert web.calls[-1].startswith("https://overpass.private.coffee")


def test_rate_limit_is_not_dodged_by_switching_mirror():
    client, web = make_client({"https://overpass-api.de": (429, b"", {"Retry-After": "1"})}, max_retries=1)
    with pytest.raises(Exception, match="429"):
        overpass.run_query("q", client)
    assert all(c.startswith("https://overpass-api.de") for c in web.calls)

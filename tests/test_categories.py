import pytest

from categories import parse_tag, resolve


def test_resolve_aliases():
    assert resolve("Dental Clinics") == resolve("dentist") == [("amenity", "dentist"), ("healthcare", "dentist")]
    assert resolve("real estate") == [("office", "estate_agent")]


def test_unknown_category_explains():
    with pytest.raises(KeyError, match="--tag"):
        resolve("unicorn farm")


def test_parse_tag_ok_and_rejects_query_injection():
    assert parse_tag("shop = bicycle") == ("shop", "bicycle")
    for bad in ['shop=a"];out;', "noequals", "=x", "shop=a(b)"]:
        with pytest.raises(ValueError):
            parse_tag(bad)

import csv
import json

import collect_leads
from conftest import make_client

SITE = "https://www.brightsmile.example"


def routes(fixture_text):
    return {
        "https://nominatim.openstreetmap.org": fixture_text("nominatim_relation.json"),
        "https://overpass-api.de": fixture_text("overpass_dentists.json"),
        SITE + "/robots.txt": "User-agent: *\nAllow: /\n",
        SITE + "/contact-us": fixture_text("brightsmile_contact.html"),
        SITE: fixture_text("brightsmile_home.html"),
        "https://harbourdental.example": "should not be fetched, email already known",
    }


def run(tmp_path, fixture_text, *extra):
    out = tmp_path / "leads.csv"
    args = collect_leads.build_parser().parse_args(
        ["--place", "Sample Marina", "--category", "dentists", "--out", str(out), *extra])
    client, web = make_client(routes(fixture_text))
    summary = collect_leads.collect(args, client=client)
    with open(out, newline="") as fh:
        return summary, list(csv.DictReader(fh)), web


def test_end_to_end_with_email_lookup(tmp_path, fixture_text):
    summary, rows, web = run(tmp_path, fixture_text, "--emails")
    assert summary["features_returned"] == 6
    assert summary["unnamed_skipped"] == 1 and summary["duplicates_merged"] == 1
    assert summary["rows_written"] == 4 and summary["search_mode"] == "admin area"
    bright = next(r for r in rows if r["name"].startswith("Bright Smile"))
    assert bright["email"] == "reception@brightsmile.example"
    assert bright["email_source"] == "company website"
    assert bright["opening_hours"] == "Mo-Sa 09:00-21:00"  # merged from the duplicate way
    assert summary["email_lookup"]["personal_addresses_dropped"] == 1
    assert summary["personal_emails_dropped_from_osm"] == 1
    assert not any("john.owner67" in v for r in rows for v in r.values())
    assert summary["email_lookup"]["skipped_social_or_map"] == 1
    assert not any("harbourdental" in c or "instagram" in c for c in web.calls)
    assert all(r["source"].startswith("OpenStreetMap") for r in rows)


def test_formula_cells_are_escaped(tmp_path, fixture_text):
    _, rows, _ = run(tmp_path, fixture_text)
    assert any(r["name"].startswith("'=HYPERLINK") for r in rows)
    assert not any(r["name"].startswith("=") for r in rows)


def test_require_and_limit(tmp_path, fixture_text):
    summary, rows, web = run(tmp_path, fixture_text, "--require", "email", "--limit", "5")
    assert [r["name"] for r in rows] == ["Harbour Dental Care"]
    assert not any(SITE in c for c in web.calls)  # no --emails, no site visits


def test_max_sites_cap(tmp_path, fixture_text):
    summary, _, web = run(tmp_path, fixture_text, "--emails", "--max-sites", "0")
    assert "stopped at --max-sites 0" in summary["email_lookup"]["notes"]
    assert not any("brightsmile" in c for c in web.calls)


def test_cli_exit_codes(capsys):
    assert collect_leads.main(["--place", "x", "--category", "unicorn"]) == 2
    assert "unknown category" in json.loads(capsys.readouterr().err)["error"]
    assert collect_leads.main(["--bbox", "3,2,1,4", "--tag", "shop=bakery"]) == 2


def test_phone_numbers_are_not_mangled():
    assert collect_leads.safe_cell("+971 4 360 0000") == "+971 4 360 0000"
    assert collect_leads.safe_cell("+1 (555) 010-0000") == "+1 (555) 010-0000"
    assert collect_leads.safe_cell("+cmd|' /C calc'!A0") == "'+cmd|' /C calc'!A0"
    assert collect_leads.safe_cell("-2+3") == "'-2+3"
    assert collect_leads.safe_cell("@SUM(A1)") == "'@SUM(A1)"

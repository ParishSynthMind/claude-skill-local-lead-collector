from conftest import make_client
from email_lookup import EmailFinder, LookupStats, contact_links, extract_emails, is_blocked, is_role_address

SITE = "https://www.brightsmile.example"


def test_role_vs_personal():
    for ok in ["info@x.ae", "reception@x.ae", "bookings2@x.ae", "info.dubai@x.ae", "contact+web@x.ae"]:
        assert is_role_address(ok), ok
    for ok in ["callcenter@x.ae", "patientcare@x.ae", "ajanvaraus@hammas.fi", "empfang@praxis.de", "smiledental@smiledental.ae", "kontakt@x.se"]:
        assert is_role_address(ok), ok
    for personal in ["jane.doe@x.ae", "dr.ali@x.ae", "ahmed@x.ae", "informal.joe@x.ae", "gmail@gmail.com",
                     "postman.pat@x.ae"]:
        assert not is_role_address(personal), personal


def test_extract_emails_filters_junk():
    page = 'a@b.png info@site.example mailto:INFO@site.example x@sentry.io sales [at] site.example'
    assert extract_emails(page) == ["info@site.example"]


def test_blocked_sites():
    assert is_blocked("https://www.instagram.com/x") and is_blocked("maps.app.goo.gl/abc")
    assert not is_blocked("https://brightsmile.example")


def test_contact_links_same_host_only(fixture_text):
    links = contact_links(fixture_text("brightsmile_home.html"), SITE + "/")
    assert links == [SITE + "/contact-us", SITE + "/about"]


def test_finds_role_email_and_drops_personal(fixture_text):
    client, web = make_client({
        SITE + "/robots.txt": "User-agent: *\nDisallow: /private\n",
        SITE + "/contact-us": fixture_text("brightsmile_contact.html"),
        SITE + "/about": "<p>about</p>",
        SITE: fixture_text("brightsmile_home.html"),
    })
    stats = LookupStats()
    assert EmailFinder(client).find(SITE, stats) == "reception@brightsmile.example"
    assert stats.personal_addresses_dropped == 1 and stats.emails_found == 1
    assert not any("other.example" in c for c in web.calls)


def test_robots_disallow_means_no_fetch():
    client, web = make_client({SITE + "/robots.txt": "User-agent: *\nDisallow: /\n", SITE: "info@brightsmile.example"})
    stats = LookupStats()
    assert EmailFinder(client).find(SITE, stats) == ""
    assert stats.blocked_by_robots == 1
    assert web.calls == [SITE + "/robots.txt"]


def test_robots_403_means_keep_out():
    client, web = make_client({SITE + "/robots.txt": (403, b""), SITE: "info@brightsmile.example"})
    assert EmailFinder(client).find(SITE, LookupStats()) == ""
    assert len(web.calls) == 1


def test_missing_robots_allows_and_social_never_fetched():
    client, web = make_client({SITE: "<a href='mailto:info@brightsmile.example'>x</a>"})
    assert EmailFinder(client).find(SITE, LookupStats()) == "info@brightsmile.example"
    stats = LookupStats()
    assert EmailFinder(client).find("https://instagram.com/x", stats) == ""
    assert stats.skipped_social_or_map == 1 and not any("instagram" in c for c in web.calls)


def test_network_error_does_not_raise():
    client, _ = make_client({SITE + "/robots.txt": "", SITE: (500, b"")}, max_retries=0)
    stats = LookupStats()
    assert EmailFinder(client).find(SITE, stats) == "" and stats.fetch_errors == 1


def test_dead_deep_link_falls_back_to_home_page():
    deep = SITE + "/clinics/branch-7"
    client, web = make_client({
        SITE + "/robots.txt": "",
        deep: (404, b""),
        SITE + "/": "<a href='mailto:info@brightsmile.example'>mail</a>",
    })
    stats = LookupStats()
    assert EmailFinder(client).find(deep, stats) == "info@brightsmile.example"
    assert stats.fetch_errors == 0


def test_429_stops_the_site_at_once():
    client, web = make_client({SITE + "/robots.txt": "", SITE: (429, b"", {"Retry-After": "1"})}, max_retries=0)
    stats = LookupStats()
    assert EmailFinder(client).find(SITE + "/x/y", stats) == ""
    assert stats.fetch_errors == 1 and len([c for c in web.calls if not c.endswith("robots.txt")]) == 1

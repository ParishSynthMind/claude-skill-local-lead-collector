from dedupe import dedupe, norm_name, same_business, site_domain


def row(name, website="", lat="25.0800", lon="55.1400", **kw):
    return {"name": name, "website": website, "lat": lat, "lon": lon, "phone": "", **kw}


def test_norm_and_domain():
    assert norm_name("Bright Smile Dental Clinic L.L.C.") == "bright smile"
    assert site_domain("https://www.Example.com:443/x") == "example.com"
    assert site_domain("example.com") == "example.com"


def test_same_site_similar_name_merges_and_fills_gaps():
    a = row("Bright Smile Dental Clinic", "https://www.brightsmile.example", phone="+1")
    b = row("Bright Smile Dental", "http://brightsmile.example/", lat="25.2", opening_hours="Mo-Fr")
    out = dedupe([a, b])
    assert len(out) == 1
    assert out[0]["phone"] == "+1" and out[0]["opening_hours"] == "Mo-Fr"


def test_same_name_far_apart_kept_separate():
    # Two branches of a chain without a website.
    a, b = row("Smile Co"), row("Smile Co", lat="25.1000")
    assert not same_business(a, b)
    assert len(dedupe([a, b])) == 2


def test_same_name_close_merges():
    assert len(dedupe([row("Smile Co"), row("SMILE CO.", lat="25.0805")])) == 1


def test_shared_domain_different_names_kept():
    # A hospital group site listed on two unrelated clinics.
    a, b = row("Alpha Dental", "group.example"), row("Zeta Orthodontics", "group.example", lat="25.2")
    assert len(dedupe([a, b])) == 2

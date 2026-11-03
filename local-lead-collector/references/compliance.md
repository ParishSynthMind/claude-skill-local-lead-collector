# What this Skill collects, and what it refuses to

## Collected

- Business facts that the business or OSM mappers published openly on
  OpenStreetMap: name, category, website, phone, email, address, opening hours,
  location. OSM data is licensed under the Open Database Licence (ODbL): you may
  use it commercially, but you must credit "OpenStreetMap contributors", and if you
  publish a database built from it, share that database under the ODbL too.
- With `--emails`: one role address (info@, contact@, reception@, bookings@...) taken
  from the company's own home page or its contact/about pages.

## Refused, in code

- Addresses that look like a named person (`jane.smith@`, `dr.ali@`, `ahmed1980@gmail.com`)
  are dropped and only counted, whether they came from a website or from OSM itself
  (some mappers enter an owner's private address). They are personal data, and under GDPR and the UAE PDPL a named
  person's email needs a lawful basis this tool can't judge for you.
- Social networks, Google and Google Maps, WhatsApp links, link-in-bio pages, Yelp
  and TripAdvisor are never fetched, even when a business lists one as its website.
  Their terms forbid scraping.
- Pages that robots.txt disallows are not fetched. A robots.txt that answers 401 or
  403 is treated as "keep out". No robots.txt at all is treated as allowed, which is
  the standard reading.
- No guessed addresses. If no email is published, the cell stays empty.

## Before anyone sends cold email

The rules depend on where the sender and the recipients are. Rough guide, not legal advice:

- EU / UK: B2B email to a generic company address is generally allowed with a
  clear opt-out and the sender's identity (UK PECR treats corporate subscribers more
  loosely than individuals; GDPR still applies to any named person).
- UAE: the TDRA and the PDPL expect consent for marketing messages; keep volumes low
  and always honour opt-outs.
- US: CAN-SPAM allows B2B cold email with a real address, honest subject line and
  a working unsubscribe.

Keep the `source` and `collected_at` columns: they record where and when each row came from.

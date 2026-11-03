"""Optional: find a public business email on the company's own website.

Rules, enforced in code:
- robots.txt is read and obeyed for every site (no robots.txt = allowed).
- Only the company's own site: the listed page, the home page and at most 2 contact/about pages
  on the same host. Social networks, map sites and directories are never fetched.
- At least 2 seconds between requests to one host; a cap on sites per run.
- Only HTML is read, at most 2 MB a page.
- Only ROLE addresses are kept (info@, contact@, reception@...). Addresses that
  look like a named person (jane.smith@...) are dropped and counted, not stored,
  because they are personal data. Free-mail addresses are only kept when they are
  the business's published contact and still a role-style local part.
"""
from __future__ import annotations

import html
import re
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from dedupe import site_domain
from polite_http import FetchError, PoliteClient, user_agent

BLOCKED_DOMAINS = (
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "tiktok.com",
    "google.com", "goo.gl", "maps.app.goo.gl", "wa.me", "whatsapp.com", "yelp.com",
    "tripadvisor.com", "linktr.ee", "youtube.com",
)

ROLE_PREFIXES = (
    "info", "contact", "hello", "hi", "enquiries", "enquiry", "inquiries", "inquiry",
    "reception", "frontdesk", "front.desk", "appointments", "appointment", "booking",
    "bookings", "reservations", "admin", "office", "sales", "support", "care",
    "customercare", "customerservice", "service", "team", "clinic", "dental", "help",
    "mail", "general", "marketing", "business", "partners", "media", "press", "hr",
    "careers", "jobs", "accounts", "billing", "callcenter", "callcentre", "concierge",
    "patient", "patients", "patientcare", "feedback", "frontoffice", "dentist", "doctor",
    # Common non-English role words (Finnish, Swedish, German, French, Spanish, Dutch, Italian)
    "toimisto", "vastaanotto", "ajanvaraus", "asiakaspalvelu", "myynti", "palvelu",
    "kontakt", "kontor", "kundservice", "bokning", "post", "buero", "buro", "empfang",
    "termin", "anfrage", "praxis", "accueil", "rdv", "secretariat", "contacto", "recepcion",
    "citas", "ventas", "reservas", "oficina", "afspraak", "receptie", "segreteria",
)

FREE_MAIL = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "live.com", "aol.com")

CONTACT_WORDS = ("contact", "about", "reach", "location", "appointment", "book")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
HREF_RE = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.I)
JUNK_EMAIL_DOMAINS = ("example.com", "sentry.io", "wixpress.com", "domain.com", "email.com")
JUNK_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")


def is_blocked(url: str) -> bool:
    host = site_domain(url)
    return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


def is_role_address(email: str) -> bool:
    local, _, domain = email.lower().partition("@")
    base = re.split(r"[+]", local)[0]
    # The business's own name as the mailbox (smiledental@smiledental.ae) is a business address.
    label = domain.split(".")[0]
    if domain not in FREE_MAIL and len(base) >= 4 and (base == label or base.replace(".", "").replace("-", "") == label.replace("-", "")):
        return True
    return any(base == p or base.startswith(p + ".") or base.startswith(p + "-") or base.startswith(p + "_")
               or re.fullmatch(rf"{re.escape(p)}\d*", base) for p in ROLE_PREFIXES)


def extract_emails(page_html: str) -> List[str]:
    text = html.unescape(page_html)
    text = text.replace("[at]", "@").replace("(at)", "@")
    found = []
    for raw in EMAIL_RE.findall(text):
        email = raw.strip(".").lower()
        if email.endswith(JUNK_SUFFIXES) or any(email.endswith("@" + d) for d in JUNK_EMAIL_DOMAINS):
            continue
        if email not in found:
            found.append(email)
    return found


def contact_links(page_html: str, base_url: str, limit: int = 2) -> List[str]:
    base_host = urllib.parse.urlsplit(base_url).netloc.lower()
    links: List[str] = []
    for href in HREF_RE.findall(page_html):
        url = urllib.parse.urljoin(base_url, href.strip())
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or parts.netloc.lower() != base_host:
            continue
        if not any(w in parts.path.lower() for w in CONTACT_WORDS):
            continue
        clean = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        if clean not in links and clean.rstrip("/") != base_url.rstrip("/"):
            links.append(clean)
        if len(links) >= limit:
            break
    return links


@dataclass
class LookupStats:
    sites_checked: int = 0
    blocked_by_robots: int = 0
    skipped_social_or_map: int = 0
    fetch_errors: int = 0
    emails_found: int = 0
    personal_addresses_dropped: int = 0
    notes: List[str] = field(default_factory=list)


class EmailFinder:
    def __init__(self, client: PoliteClient):
        self.client = client
        self._robots: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}

    def _robots_for(self, url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        parts = urllib.parse.urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root in self._robots:
            return self._robots[root]
        parser: Optional[urllib.robotparser.RobotFileParser] = urllib.robotparser.RobotFileParser()
        try:
            resp = self.client.request(root + "/robots.txt")
            parser.parse(resp.text().splitlines())
        except FetchError as exc:
            # 401/403 on robots.txt: treat the whole site as off limits. 404 or no answer: allowed.
            if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
                parser.disallow_all = True
            else:
                parser = None
        self._robots[root] = parser
        return parser

    def allowed(self, url: str) -> bool:
        parser = self._robots_for(url)
        return True if parser is None else parser.can_fetch(user_agent(), url)

    def _get_html(self, url: str) -> Optional[Tuple[str, str]]:
        resp = self.client.request(url)
        if "html" not in resp.content_type.lower():
            return None
        return resp.url, resp.text()

    def find(self, website: str, stats: LookupStats) -> str:
        """Return one role email for the site, or '' if none. Never raises on network trouble."""
        url = website if "://" in website else "https://" + website
        if is_blocked(url):
            stats.skipped_social_or_map += 1
            return ""
        stats.sites_checked += 1
        domain = site_domain(url)
        parts = urllib.parse.urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}/"
        # The listed page (often a branch page deep in the site), then the home page,
        # then at most 2 contact/about links found on those. One bad page doesn't end the site.
        queue = [url] if url.rstrip("/") == root.rstrip("/") else [url, root]
        pages: List[str] = []
        seen: set = set()
        errors: List[str] = []
        budget = len(queue) + 2
        while queue and len(seen) < budget:
            page_url = queue.pop(0)
            if page_url.rstrip("/") in seen:
                continue
            seen.add(page_url.rstrip("/"))
            try:
                if not self.allowed(page_url):
                    stats.blocked_by_robots += 1
                    continue
                got = self._get_html(page_url)
            except FetchError as exc:
                errors.append(str(exc))
                if "HTTP 429" in str(exc):
                    break  # the site asked us to slow down: stop here, don't push on
                continue
            if not got:
                continue
            final_url, page = got
            pages.append(page)
            if len(pages) <= 2:
                queue.extend(link for link in contact_links(page, final_url) if link.rstrip("/") not in seen)
        if errors and not pages:
            stats.fetch_errors += 1
            stats.notes.append(f"{domain}: {errors[-1]}")
            return ""
        best = ""
        dropped = set()
        for page_html in pages:
            for email in extract_emails(page_html):
                if not is_role_address(email):
                    dropped.add(email)
                    continue
                on_own_domain = site_domain("http://" + email.split("@", 1)[1]) == domain
                if not best or (on_own_domain and site_domain("http://" + best.split("@", 1)[1]) != domain):
                    best = email
        stats.personal_addresses_dropped += len(dropped)  # counted once each, never stored
        if best:
            stats.emails_found += 1
        return best

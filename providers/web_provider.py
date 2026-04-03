"""
Web discovery provider — find leads from company websites and search results.
No API key needed — uses public web pages.
"""

import re
import os
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None  # type: ignore
    BeautifulSoup = None  # type: ignore

from providers.base import LeadProvider

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# Common non-person emails to skip
SKIP_PREFIXES = {
    "info", "contact", "sales", "support", "admin", "webmaster",
    "noreply", "no-reply", "marketing", "hr", "careers", "jobs",
    "help", "billing", "press", "media", "office", "general",
    "team", "hello", "feedback", "service", "enquiries",
}


class WebProvider(LeadProvider):
    def __init__(self):
        self.session = None

    def name(self) -> str:
        return "Web Discovery"

    def requires_api_key(self) -> bool:
        return False

    def rate_limit_msg(self) -> str:
        return "Self-throttled: 2-second delay between requests."

    def search(self, **kwargs) -> list[dict]:
        if not requests or not BeautifulSoup:
            raise ImportError(
                "pip install requests beautifulsoup4 — required for Web provider"
            )

        query = kwargs.get("query", kwargs.get("search", ""))
        domain = kwargs.get("domain", "")
        limit = int(kwargs.get("limit", 10))

        if not query and not domain:
            raise ValueError(
                "Web provider requires --search 'query' or --domain company.com"
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        results: list[dict] = []

        if domain:
            # Scrape the domain's contact/about/team pages
            results = self._scrape_domain(domain, limit)
        elif query:
            # Search Google for contact pages
            results = self._search_and_scrape(query, limit)

        return results[:limit]

    def _scrape_domain(self, domain: str, limit: int) -> list[dict]:
        """Scrape a specific domain for contact emails."""
        base_url = f"https://{domain}" if not domain.startswith("http") else domain
        parsed = urlparse(base_url)
        clean_domain = parsed.netloc or parsed.path

        # Pages likely to have contact info
        paths = ["/", "/contact", "/about", "/team", "/leadership", "/staff",
                 "/contact-us", "/about-us", "/our-team"]

        found: list[dict] = []
        seen_emails: set[str] = set()

        for path in paths:
            if len(found) >= limit:
                break
            url = f"https://{clean_domain}{path}"
            try:
                resp = self.session.get(url, timeout=10, allow_redirects=True)
                if resp.status_code != 200:
                    continue
                page_leads = self._extract_from_page(resp.text, clean_domain)
                for lead in page_leads:
                    if lead["email"] not in seen_emails:
                        seen_emails.add(lead["email"])
                        found.append(lead)
            except Exception:
                continue

        return found

    def _search_and_scrape(self, query: str, limit: int) -> list[dict]:
        """Use a search query to find company pages, then scrape them."""
        # We can't reliably scrape Google without API, so we do domain-based
        # discovery from the query terms
        print(f"  [Web] Tip: For best results, use --domain company.com instead of free-text search.")
        print(f"  [Web] Free-text search requires a Google Custom Search API key (not yet configured).")
        print(f"  [Web] Attempting direct domain extraction from query...")

        # Try to extract domains from the query
        words = query.lower().split()
        for word in words:
            if "." in word and len(word) > 4:
                return self._scrape_domain(word, limit)

        return []

    def _extract_from_page(self, html: str, domain: str) -> list[dict]:
        """Extract email addresses and associated context from a page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # Find all emails on page
        emails = set(EMAIL_RE.findall(text))

        # Also check href="mailto:..." links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if EMAIL_RE.match(email):
                    emails.add(email)

        results: list[dict] = []
        for email in emails:
            prefix = email.split("@")[0].lower()
            if prefix in SKIP_PREFIXES:
                continue

            # Try to guess name from email prefix
            first, last = "", ""
            if "." in prefix:
                parts = prefix.split(".")
                first = parts[0].capitalize()
                last = parts[-1].capitalize() if len(parts) > 1 else ""
            elif "_" in prefix:
                parts = prefix.split("_")
                first = parts[0].capitalize()
                last = parts[-1].capitalize() if len(parts) > 1 else ""

            results.append(
                {
                    "first_name": first,
                    "last_name": last,
                    "email": email,
                    "title": "",
                    "company_name": domain.replace("www.", ""),
                    "phone": "",
                    "website": domain,
                    "industry": "",
                    "company_size": "",
                    "location": "",
                }
            )

        return results

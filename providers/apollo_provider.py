"""
Apollo.io provider — searches the Apollo Organizations API for target companies.
Free tier: Organization search available (People search requires paid plan).

Strategy: Apollo finds companies → use Hunter.io or web scraping for contacts.
Can also return basic company records for manual prospecting.

Docs: https://docs.apollo.io/
"""

import os
import time
import json
from typing import Any

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from providers.base import LeadProvider

APOLLO_BASE = "https://api.apollo.io"

# Endpoints available on free plan
ORG_SEARCH = "/v1/organizations/search"

# Endpoints requiring paid plan (for future upgrade)
PEOPLE_SEARCH = "/v1/mixed_people/search"
PEOPLE_MATCH = "/v1/people/match"


class ApolloProvider(LeadProvider):
    def __init__(self):
        self.api_key = os.getenv("APOLLO_API_KEY", "")

    def name(self) -> str:
        return "Apollo.io"

    def requires_api_key(self) -> bool:
        return True

    def rate_limit_msg(self) -> str:
        return "Free: org search only. Paid ($49/mo): people search + email credits"

    def search(self, **kwargs) -> list[dict]:
        if not requests:
            raise ImportError("pip install requests — required for Apollo provider")
        if not self.api_key:
            raise ValueError(
                "APOLLO_API_KEY not set in .env. "
                "Sign up free at https://apollo.io and add your API key."
            )

        location = kwargs.get("location", "")
        industry = kwargs.get("industry", "")
        limit = int(kwargs.get("limit", 25))
        company_size = kwargs.get("company_size", "51-100,101-200,201-500")
        search_query = kwargs.get("search", "")

        # Try people search first (paid plan)
        try:
            return self._search_people(search_query, location, industry, company_size, limit)
        except PermissionError:
            print("  [Apollo] People search requires paid plan. Using company search instead.")
            print("  [Apollo] Tip: Combine with --provider hunter to find contacts at these companies.\n")
            return self._search_organizations(location, industry, company_size, limit, search_query)

    def _search_people(self, title, location, industry, company_size, limit):
        """People search — requires paid plan."""
        payload: dict[str, Any] = {
            "page": 1,
            "per_page": min(limit, 100),
        }
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
        }

        if title:
            payload["person_titles"] = [t.strip() for t in title.split(",")]
        if location:
            payload["person_locations"] = [location]
        if company_size:
            payload["organization_num_employees_ranges"] = [
                s.strip() for s in company_size.split(",")
            ]

        resp = requests.post(
            f"{APOLLO_BASE}{PEOPLE_SEARCH}",
            json=payload, headers=headers, timeout=30,
        )

        if resp.status_code == 403:
            raise PermissionError("Paid plan required")

        resp.raise_for_status()
        data = resp.json()

        results = []
        for person in data.get("people", []):
            org = person.get("organization", {}) or {}
            loc_parts = [person.get("city", ""), person.get("state", ""), person.get("country", "")]
            results.append({
                "first_name": person.get("first_name", ""),
                "last_name": person.get("last_name", ""),
                "email": person.get("email", ""),
                "title": person.get("title", ""),
                "company_name": org.get("name", ""),
                "phone": person.get("phone_number", "") or "",
                "website": org.get("website_url", "") or "",
                "industry": org.get("industry", "") or "",
                "company_size": str(org.get("estimated_num_employees", "")),
                "location": ", ".join(p for p in loc_parts if p),
            })
        return results[:limit]

    def _search_organizations(self, location, industry, company_size, limit, keyword=""):
        """Organization search — available on free plan."""
        payload: dict[str, Any] = {
            "page": 1,
            "per_page": min(limit, 100),
        }
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.api_key,
        }

        if location:
            payload["organization_locations"] = [location]
        if company_size:
            payload["organization_num_employees_ranges"] = [
                s.strip() for s in company_size.split(",")
            ]
        if industry:
            payload["organization_industry_tag_ids"] = [industry]
        if keyword:
            payload["q_organization_keyword_tags"] = [keyword]

        results: list[dict] = []
        pages_needed = (limit + 99) // 100

        for page in range(1, pages_needed + 1):
            payload["page"] = page
            try:
                resp = requests.post(
                    f"{APOLLO_BASE}{ORG_SEARCH}",
                    json=payload, headers=headers, timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"  [Apollo] API error on page {page}: {e}")
                break

            orgs = data.get("organizations", [])
            if not orgs:
                break

            for org in orgs:
                loc_parts = [org.get("city", ""), org.get("state", "")]
                domain = (org.get("website_url", "") or "").replace("http://", "").replace("https://", "").strip("/")

                results.append({
                    "first_name": "",
                    "last_name": "",
                    "email": "",  # No contacts on free plan
                    "title": "",
                    "company_name": org.get("name", ""),
                    "phone": org.get("phone", "") or "",
                    "website": domain,
                    "industry": org.get("industry", "") or "",
                    "company_size": str(org.get("estimated_num_employees", "")),
                    "location": ", ".join(p for p in loc_parts if p),
                    "_apollo_id": org.get("id", ""),
                    "_domain": domain,  # Useful for Hunter.io follow-up
                })
                if len(results) >= limit:
                    break

            if len(results) >= limit:
                break

            if page < pages_needed:
                time.sleep(2)

        return results[:limit]

"""
Hunter.io provider — find emails by company domain.
Free tier: 25 searches/month.
Docs: https://hunter.io/api-documentation
"""

import os

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from providers.base import LeadProvider

HUNTER_BASE = "https://api.hunter.io/v2"


class HunterProvider(LeadProvider):
    def __init__(self):
        self.api_key = os.getenv("HUNTER_API_KEY", "")

    def name(self) -> str:
        return "Hunter.io"

    def requires_api_key(self) -> bool:
        return True

    def rate_limit_msg(self) -> str:
        return "Free tier: 25 searches/month, 50 verifications/month"

    def search(self, **kwargs) -> list[dict]:
        if not requests:
            raise ImportError("pip install requests — required for Hunter provider")
        if not self.api_key:
            raise ValueError(
                "HUNTER_API_KEY not set in .env. "
                "Sign up free at https://hunter.io and add your API key."
            )

        domain = kwargs.get("domain", "")
        limit = int(kwargs.get("limit", 25))

        if not domain:
            raise ValueError("Hunter provider requires --domain flag (e.g., --domain company.com)")

        results: list[dict] = []

        try:
            resp = requests.get(
                f"{HUNTER_BASE}/domain-search",
                params={
                    "domain": domain,
                    "api_key": self.api_key,
                    "limit": min(limit, 100),
                    "type": "personal",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  [Hunter] API error: {e}")
            return []

        org_name = data.get("data", {}).get("organization", domain)
        emails = data.get("data", {}).get("emails", [])

        for entry in emails[:limit]:
            results.append(
                {
                    "first_name": entry.get("first_name", ""),
                    "last_name": entry.get("last_name", ""),
                    "email": entry.get("value", ""),
                    "title": entry.get("position", "") or entry.get("seniority", ""),
                    "company_name": org_name,
                    "phone": entry.get("phone_number", "") or "",
                    "website": domain,
                    "industry": "",
                    "company_size": "",
                    "location": "",
                }
            )

        return results

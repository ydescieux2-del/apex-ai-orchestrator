"""
CSV provider — import leads from any CSV/TSV file.
Handles Chamber of Commerce exports, LinkedIn exports, WIZA exports, manual lists.
Auto-maps common column names to standard fields.
"""

import csv
import os
from pathlib import Path

from providers.base import LeadProvider

# Common column name aliases → standard field
COLUMN_ALIASES: dict[str, list[str]] = {
    "first_name": ["first_name", "first name", "firstname", "given name", "fname"],
    "last_name": ["last_name", "last name", "lastname", "surname", "family name", "lname"],
    "email": ["email", "email address", "e-mail", "work email", "business email", "email_address"],
    "title": ["title", "job title", "position", "role", "job_title", "designation"],
    "company_name": ["company_name", "company", "company name", "organization", "org", "employer"],
    "phone": ["phone", "phone number", "telephone", "mobile", "cell", "direct phone", "phone_number"],
    "website": ["website", "url", "web", "company url", "domain", "company_url"],
    "industry": ["industry", "sector", "vertical", "category"],
    "company_size": ["company_size", "company size", "employees", "num employees", "employee count", "headcount"],
    "location": ["location", "city, state", "address", "city state", "full location", "headquarters"],
    "city": ["city", "locality"],
    "state": ["state", "region", "province"],
    "country": ["country", "nation"],
}


def _build_column_map(headers: list[str]) -> dict[str, str]:
    """Map CSV column headers to standard field names."""
    mapping: dict[str, str] = {}
    lower_headers = {h.lower().strip(): h for h in headers}

    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_headers:
                mapping[field] = lower_headers[alias]
                break

    # Special case: "Name" or "Full Name" → split into first/last
    for name_col in ["name", "full name", "contact name", "contact_name"]:
        if name_col in lower_headers and "first_name" not in mapping:
            mapping["_full_name"] = lower_headers[name_col]
            break

    return mapping


class CSVProvider(LeadProvider):
    def __init__(self):
        pass

    def name(self) -> str:
        return "CSV Import"

    def requires_api_key(self) -> bool:
        return False

    def rate_limit_msg(self) -> str:
        return "No rate limit — local file processing."

    def search(self, **kwargs) -> list[dict]:
        filepath = kwargs.get("file", "")
        limit = int(kwargs.get("limit", 9999))

        if not filepath:
            raise ValueError("CSV provider requires --file flag (e.g., --file contacts.csv)")

        path = Path(filepath).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Detect delimiter
        with open(path, "r", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            f.seek(0)
            reader = csv.DictReader(f, dialect=dialect)

            if not reader.fieldnames:
                raise ValueError(f"No headers found in {path}")

            col_map = _build_column_map(list(reader.fieldnames))
            if "email" not in col_map:
                print(f"  [CSV] WARNING: No email column found. Headers: {reader.fieldnames}")
                print(f"  [CSV] Mapped columns: {col_map}")

            results: list[dict] = []
            for row in reader:
                # Extract mapped fields
                first = row.get(col_map.get("first_name", ""), "").strip()
                last = row.get(col_map.get("last_name", ""), "").strip()

                # Handle full name split
                if not first and "_full_name" in col_map:
                    full = row.get(col_map["_full_name"], "").strip()
                    parts = full.split(None, 1)
                    first = parts[0] if parts else ""
                    last = parts[1] if len(parts) > 1 else ""

                email = row.get(col_map.get("email", ""), "").strip()
                if not email:
                    continue  # Skip rows without email

                # Build location from city + state if no full location
                location = row.get(col_map.get("location", ""), "").strip()
                if not location:
                    city = row.get(col_map.get("city", ""), "").strip()
                    state = row.get(col_map.get("state", ""), "").strip()
                    country = row.get(col_map.get("country", ""), "").strip()
                    parts = [p for p in [city, state, country] if p]
                    location = ", ".join(parts)

                results.append(
                    {
                        "first_name": first,
                        "last_name": last,
                        "email": email,
                        "title": row.get(col_map.get("title", ""), "").strip(),
                        "company_name": row.get(col_map.get("company_name", ""), "").strip(),
                        "phone": row.get(col_map.get("phone", ""), "").strip(),
                        "website": row.get(col_map.get("website", ""), "").strip(),
                        "industry": row.get(col_map.get("industry", ""), "").strip(),
                        "company_size": row.get(col_map.get("company_size", ""), "").strip(),
                        "location": location,
                    }
                )

                if len(results) >= limit:
                    break

        return results

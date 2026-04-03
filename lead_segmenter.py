"""
lead_segmenter.py — Auto-assign leads to segments (SEG-1..SEG-8).
Maps title + industry keywords to list_name values that send_emails.py expects.
"""

# ── Segment definitions ──────────────────────────────────────────────────
# Each segment has: label, target list_name, and matching rules

SEGMENTS = [
    {
        "id": "SEG-1",
        "label": "IT Procurement / IT Manager",
        "list_name": "IT Manager/Supervisor and Purchasing",
        "title_keywords": [
            "it manager", "it director", "it supervisor",
            "information technology", "information systems",
            "it procurement", "technology procurement",
            "systems administrator", "network administrator",
            "infrastructure", "data center", "asset management",
            "director of it", "director of tech",
            "vp of it", "vp it", "cio", "cto",
        ],
        "industry_keywords": [],  # Any industry
    },
    {
        "id": "SEG-2",
        "label": "EHS California",
        "list_name": "EHS California",
        "title_keywords": [
            "ehs", "environmental health", "environmental safety",
            "environmental compliance", "sustainability",
            "health and safety", "safety manager", "safety director",
            "environmental manager", "environmental director",
        ],
        "industry_keywords": [],
    },
    {
        "id": "SEG-3",
        "label": "Government / Procurement Admin",
        "list_name": "Procurement Gov Admin CA,WA,OR,AZ,NV,TX,CO,FL",
        "title_keywords": [
            "procurement", "purchasing", "contracting officer",
            "contracts manager", "contracts director",
            "sourcing manager", "sourcing director",
            "supply chain", "vendor management",
            "category manager", "buyer",
        ],
        "industry_keywords": [
            "government", "public administration", "municipal",
            "county", "state", "federal", "civic",
        ],
    },
    {
        "id": "SEG-4",
        "label": "Financial / Banks / CFO",
        "list_name": "Financial Analyst/ CFO - Banks & Accountants",
        "title_keywords": [
            "cfo", "chief financial", "controller", "comptroller",
            "treasurer", "finance director", "finance manager",
            "financial analyst", "vp of finance",
        ],
        "industry_keywords": [
            "financial", "banking", "bank", "insurance",
            "accounting", "credit union", "investment",
        ],
    },
    {
        "id": "SEG-5",
        "label": "Education / Higher Ed",
        "list_name": "Procurement - Education Management",
        "title_keywords": [
            "procurement", "purchasing", "facilities",
            "operations", "it manager", "it director",
            "director of technology", "cto",
        ],
        "industry_keywords": [
            "higher education", "university", "college",
            "education management", "charter school",
        ],
    },
    {
        "id": "SEG-6",
        "label": "CEOs of Nonprofits — LA",
        "list_name": "CEO of Nonprofits in Los Angeles",
        "title_keywords": [
            "ceo", "chief executive", "executive director",
            "president", "founder", "co-founder",
        ],
        "industry_keywords": [
            "nonprofit", "non-profit", "charity", "foundation",
            "community", "social services",
        ],
    },
    {
        "id": "SEG-7",
        "label": "Hospitality",
        "list_name": "Procurement Hospitality",
        "title_keywords": [
            "procurement", "purchasing", "facilities",
            "operations", "it manager", "it director",
            "general manager", "director of operations",
        ],
        "industry_keywords": [
            "hospitality", "hotel", "resort", "restaurant",
            "food service", "lodging", "travel",
        ],
    },
    {
        "id": "SEG-8",
        "label": "K-12 School Districts",
        "list_name": "Procurement Education",
        "title_keywords": [
            "procurement", "purchasing", "it director",
            "technology director", "facilities",
            "superintendent", "business manager",
            "ehs", "environmental health",
        ],
        "industry_keywords": [
            "k-12", "school district", "elementary", "secondary",
            "primary education", "education",
        ],
    },
]


def segment_lead(lead: dict) -> tuple[str, str, str]:
    """
    Auto-assign a lead to a segment based on title + industry.
    Returns (segment_id, list_name, segment_label).
    Falls back to SEG-1 (IT Procurement) as default since it's the broadest.
    """
    title = lead.get("title", "").lower()
    industry = lead.get("industry", "").lower()
    company = lead.get("company_name", "").lower()

    best_match: tuple[str, str, str] | None = None
    best_score = 0

    for seg in SEGMENTS:
        score = 0

        # Title match
        for kw in seg["title_keywords"]:
            if kw in title:
                score += 2
                break

        # Industry match
        if seg["industry_keywords"]:
            for kw in seg["industry_keywords"]:
                if kw in industry or kw in company:
                    score += 3  # Industry is more specific
                    break
        else:
            # Segments without industry keywords (SEG-1, SEG-2) only need title
            if score > 0:
                score += 1

        if score > best_score:
            best_score = score
            best_match = (seg["id"], seg["list_name"], seg["label"])

    if best_match:
        return best_match

    # Default fallback: SEG-1 (broadest segment)
    return ("SEG-1", "IT Manager/Supervisor and Purchasing", "IT Procurement / IT Manager")


def get_segment_info(segment_id: str) -> dict | None:
    """Get full segment info by ID."""
    for seg in SEGMENTS:
        if seg["id"] == segment_id:
            return seg
    return None

"""
lead_scorer.py — ICP scoring engine for ITAD outreach.
Scores leads 0-100 across 5 dimensions:
  Title match    (0-30)
  SoCal location (0-25)
  Company size   (0-20)
  Industry fit   (0-15)
  Email verified (0-10)
"""

from typing import Literal

# ── Title scoring (0-30) ────────────────────────────────────────────────

TITLE_EXACT = [
    "it manager", "it director", "it supervisor",
    "procurement manager", "procurement director",
    "facilities manager", "facilities director",
    "director of it", "director of technology",
    "it procurement", "technology procurement",
    "purchasing manager", "purchasing director",
]  # 30 points

TITLE_STRONG = [
    "cio", "cto", "coo", "cfo", "ceo",
    "chief information", "chief technology", "chief operating",
    "vp of it", "vp it", "vp of tech",
    "vice president of it", "vice president of operations",
    "operations manager", "operations director",
    "infrastructure", "asset management",
    "data center", "systems administrator",
    "network administrator",
    "ehs", "environmental health", "environmental compliance",
    "sustainability",
]  # 20 points

TITLE_PARTIAL = [
    "manager", "director", "supervisor", "coordinator",
    "administrator", "analyst", "specialist",
    "procurement", "purchasing", "contracting",
    "supply chain", "vendor management",
    "office manager", "office administrator",
    "comptroller", "treasurer", "controller",
]  # 10 points

# ── Geography scoring (0-25) ─────────────────────────────────────────────

SOCAL_STRONG = [
    "greater los angeles", "los angeles metropolitan", "los angeles area",
    "los angeles, ca", "los angeles, california",
    "inland empire", "orange county", "san gabriel valley",
    "san fernando valley", "southern california", "socal",
    "los angeles", "irvine", "anaheim", "santa ana", "long beach",
    "huntington beach", "san diego", "san bernardino",
    "rancho cucamonga", "fontana", "moreno valley", "temecula",
    "oxnard", "thousand oaks", "simi valley", "camarillo",
    "palmdale", "lancaster", "santa clarita",
    "chula vista", "escondido", "el cajon", "oceanside",
    "corona", "riverside", "ontario",
    "ventura", "santa barbara",
]  # 25 points

CA_OTHER = [
    "california", ", ca",
    "san francisco", "sacramento", "san jose", "oakland",
    "fresno", "bakersfield", "stockton", "modesto",
]  # 15 points

WEST_COAST = [
    "oregon", "washington", "nevada", "arizona",
    "portland", "seattle", "las vegas", "phoenix",
    "reno", "tucson", "boise",
    ", or", ", wa", ", nv", ", az",
]  # 10 points

# ── Company size scoring (0-20) ──────────────────────────────────────────

SIZE_SCORE_MAP = {
    # label → score
    "1 to 10": 5,
    "11 to 20": 8,
    "21 to 50": 12,
    "51 to 100": 18,
    "101 to 200": 20,
    "201 to 500": 20,
    "501 to 1000": 15,
    "1001 to 2000": 12,
    "2001 to 5000": 10,
    "5001 to 10000": 8,
    "10001+": 5,
}

# ── Industry scoring (0-15) ──────────────────────────────────────────────

INDUSTRY_EXACT = [
    "healthcare", "hospital", "medical",
    "education", "higher education", "school",
    "government", "public administration",
    "financial services", "banking", "insurance",
    "manufacturing", "industrial",
    "nonprofit", "non-profit", "charity",
    "hospitality", "hotel", "resort",
    "biotechnology", "pharmaceutical",
    "defense", "aerospace",
]  # 15 points

INDUSTRY_ADJACENT = [
    "technology", "information technology", "software",
    "real estate", "construction",
    "retail", "consumer goods",
    "professional services", "consulting",
    "logistics", "transportation",
    "energy", "utilities",
    "telecommunications",
    "media", "entertainment",
]  # 8 points


def score_lead(lead: dict) -> dict:
    """
    Score a lead against ICP. Returns dict with total + breakdown.
    lead should have: title, location, company_size, industry, email_status
    """
    title_score = _score_title(lead.get("title", ""))
    geo_score = _score_geography(lead.get("location", ""))
    size_score = _score_size(lead.get("company_size", ""))
    industry_score = _score_industry(lead.get("industry", ""))
    email_score = _score_email(lead.get("email_status", ""))

    total = title_score + geo_score + size_score + industry_score + email_score

    return {
        "total": total,
        "title": title_score,
        "geography": geo_score,
        "company_size": size_score,
        "industry": industry_score,
        "email": email_score,
    }


def _score_title(title: str) -> int:
    t = title.lower().strip()
    if not t:
        return 0
    for kw in TITLE_EXACT:
        if kw in t:
            return 30
    for kw in TITLE_STRONG:
        if kw in t:
            return 20
    for kw in TITLE_PARTIAL:
        if kw in t:
            return 10
    return 0


def _score_geography(location: str) -> int:
    loc = location.lower().strip()
    if not loc:
        return 0
    for kw in SOCAL_STRONG:
        if kw in loc:
            return 25
    for kw in CA_OTHER:
        if kw in loc:
            return 15
    for kw in WEST_COAST:
        if kw in loc:
            return 10
    # US but not West Coast
    if "united states" in loc or ", us" in loc:
        return 5
    return 0


def _score_size(size: str) -> int:
    s = size.strip()
    if not s:
        return 0
    # Direct match
    if s in SIZE_SCORE_MAP:
        return SIZE_SCORE_MAP[s]
    # Try parsing number ranges like "50-200" or "201 to 500"
    s_lower = s.lower().replace(",", "")
    for label, score in SIZE_SCORE_MAP.items():
        if label.lower() in s_lower:
            return score
    # Try to extract a number
    import re
    nums = re.findall(r"\d+", s)
    if nums:
        n = int(nums[0])
        if 50 <= n <= 500:
            return 20
        elif n > 500:
            return 15
        elif 10 <= n < 50:
            return 10
        else:
            return 5
    return 0


def _score_industry(industry: str) -> int:
    ind = industry.lower().strip()
    if not ind:
        return 0
    for kw in INDUSTRY_EXACT:
        if kw in ind:
            return 15
    for kw in INDUSTRY_ADJACENT:
        if kw in ind:
            return 8
    return 0


def _score_email(status: str) -> int:
    s = status.lower().strip()
    if s in ("valid", "verified"):
        return 10
    elif s in ("catch-all", "catchall"):
        return 5
    return 0

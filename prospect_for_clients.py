#!/usr/bin/env python3
"""
prospect_for_clients.py — Meta-prospecting engine for Apex AI Consulting.

Uses the Apex outreach infrastructure to find businesses that NEED outreach
services — then onboards them as clients using scaffold_client.py.

This is the self-feeding growth loop:
  1. Identify industries / company types that need B2B outreach
  2. Generate prospect lists (Google Places, web scraping, LinkedIn signals)
  3. Score prospects by fit (size, industry, pain signals)
  4. Generate personalized outreach templates
  5. Queue for Apex outreach

Usage:
    python prospect_for_clients.py --scan                    # scan for prospects
    python prospect_for_clients.py --generate-config LEAD-ID # auto-gen client config YAML
    python prospect_for_clients.py --list-icp                # show ideal client profiles
    python prospect_for_clients.py --pipeline                # show full prospect pipeline

Ideal Client Profiles (ICPs):
  - Small ITAD/e-waste companies (competitors to DataTech, ZS Recycling)
  - MSPs (Managed Service Providers) doing hardware lifecycle
  - Environmental services / hazmat disposal companies
  - Commercial cleaning / facility management companies
  - Staffing agencies (high-volume outreach, bad at it)
  - Real estate brokerages (lead gen dependent)
  - Insurance agencies (outbound prospecting)
  - SaaS companies without SDR teams
  - Accounting/bookkeeping firms (seasonal outreach)
  - Home services (HVAC, plumbing, roofing) — local lead gen
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROSPECTS_PATH = SCRIPT_DIR / "data" / "apex_prospects.json"
CONFIG_PATH = SCRIPT_DIR / "company_config.json"

# ─────────────────────────────────────────────────────────────
# Ideal Client Profiles — who benefits most from Apex outreach
# ─────────────────────────────────────────────────────────────

ICP_PROFILES = [
    {
        "id": "ICP-01",
        "name": "ITAD / E-Waste Companies",
        "description": "IT asset disposition and electronics recycling firms. Already proven model (DataTech, ZS Recycling).",
        "signals": ["No outbound email program", "Small team (<50)", "SoCal or major metro", "R2 or e-Stewards certified"],
        "segments_template": ["IT Procurement", "Healthcare IT", "Education Tech"],
        "compliance_hooks": ["HIPAA", "FERPA", "NIST 800-88", "CalRecycle"],
        "revenue_per_client": {"setup": 500, "monthly": 500},
        "fit_score": 95,
        "search_queries": [
            "e-waste recycling company Los Angeles",
            "IT asset disposition Southern California",
            "certified electronics recycling {city}",
            "R2 certified recycler {state}",
        ],
    },
    {
        "id": "ICP-02",
        "name": "MSPs / IT Service Providers",
        "description": "Managed service providers handling hardware lifecycle. Need outreach to acquire new clients.",
        "signals": ["Under 100 employees", "No dedicated sales team", "Website has 'contact us' but no outbound"],
        "segments_template": ["SMB IT Decision Makers", "CFOs of Mid-Market Companies"],
        "compliance_hooks": ["SOC 2", "NIST CSF"],
        "revenue_per_client": {"setup": 500, "monthly": 500},
        "fit_score": 85,
        "search_queries": [
            "managed service provider {city}",
            "IT support company {city}",
            "MSP {state} small business",
        ],
    },
    {
        "id": "ICP-03",
        "name": "Staffing / Recruiting Agencies",
        "description": "High-volume outreach need, typically bad at it. Pain point is candidate AND client acquisition.",
        "signals": ["Under 200 employees", "Multiple job boards presence", "No automated outreach"],
        "segments_template": ["HR Directors", "Hiring Managers by Industry"],
        "compliance_hooks": ["EEOC", "OFCCP"],
        "revenue_per_client": {"setup": 750, "monthly": 750},
        "fit_score": 80,
        "search_queries": [
            "staffing agency {city}",
            "recruiting firm {city} IT",
            "temp agency Southern California",
        ],
    },
    {
        "id": "ICP-04",
        "name": "Commercial Real Estate Brokerages",
        "description": "Outbound prospecting is core to CRE. Most brokerages do it manually or with outdated tools.",
        "signals": ["Independent brokerage", "Under 50 agents", "No CRM automation visible"],
        "segments_template": ["Property Owners", "Investors by Asset Class"],
        "compliance_hooks": ["CAN-SPAM", "CCPA"],
        "revenue_per_client": {"setup": 500, "monthly": 500},
        "fit_score": 75,
        "search_queries": [
            "commercial real estate brokerage {city}",
            "CRE firm {city}",
            "commercial property management {state}",
        ],
    },
    {
        "id": "ICP-05",
        "name": "Home Services Companies",
        "description": "HVAC, plumbing, roofing, solar. Need local lead gen, rarely have marketing automation.",
        "signals": ["Under 50 employees", "Google Ads but no email", "Service area business"],
        "segments_template": ["Homeowners by Zip", "Property Managers", "HOA Boards"],
        "compliance_hooks": ["CAN-SPAM", "TCPA"],
        "revenue_per_client": {"setup": 500, "monthly": 300},
        "fit_score": 70,
        "search_queries": [
            "HVAC company {city}",
            "roofing contractor {city}",
            "solar installer {state}",
        ],
    },
    {
        "id": "ICP-06",
        "name": "Accounting / Bookkeeping Firms",
        "description": "Seasonal outreach needs (tax season, year-end). High-value clients, low outbound capability.",
        "signals": ["CPA firm", "Under 30 employees", "No visible outbound program"],
        "segments_template": ["Small Business Owners", "CFOs of Mid-Market", "Startup Founders"],
        "compliance_hooks": ["CAN-SPAM", "SOC 2"],
        "revenue_per_client": {"setup": 500, "monthly": 500},
        "fit_score": 72,
        "search_queries": [
            "CPA firm {city}",
            "bookkeeping service {city}",
            "accounting firm small business {state}",
        ],
    },
]

# Target metros for initial prospecting
TARGET_METROS = [
    "Los Angeles", "San Diego", "San Francisco", "Phoenix", "Las Vegas",
    "Denver", "Dallas", "Houston", "Austin", "Miami",
]


def list_icps():
    """Print all Ideal Client Profiles."""
    print(f"\n{'='*62}")
    print(f"  APEX AI — Ideal Client Profiles")
    print(f"{'='*62}\n")
    for icp in ICP_PROFILES:
        print(f"  {icp['id']}  {icp['name']}")
        print(f"         {icp['description']}")
        print(f"         Fit Score : {icp['fit_score']}/100")
        print(f"         Revenue   : ${icp['revenue_per_client']['setup']} setup + "
              f"${icp['revenue_per_client']['monthly']}/mo")
        print(f"         Signals   : {', '.join(icp['signals'][:3])}")
        print(f"         Segments  : {', '.join(icp['segments_template'])}")
        print()

    # Revenue projection
    total_monthly = sum(i["revenue_per_client"]["monthly"] for i in ICP_PROFILES)
    print(f"  Revenue at 1 client per ICP: ${total_monthly}/mo (${total_monthly * 12}/yr)")
    total_5 = total_monthly * 5
    print(f"  Revenue at 5 clients per ICP: ${total_5}/mo (${total_5 * 12}/yr)")
    print()


def generate_client_config(prospect: dict, icp: dict) -> str:
    """Generate a client_config YAML from a prospect record."""
    company_name = prospect.get("company_name", "New Client")
    key = company_name.lower().replace(" ", "_").replace(".", "").replace(",", "")[:30]

    # Find next available segment IDs
    config = json.load(open(CONFIG_PATH))
    existing_segs = set(config.get("segment_registry", {}).keys())
    seg_counter = max(int(s.replace("SEG-", "")) for s in existing_segs if s.startswith("SEG-")) + 1

    segments_yaml = ""
    for i, seg_name in enumerate(icp.get("segments_template", ["General Outreach"])):
        seg_id = f"SEG-{seg_counter + i}"
        hook = icp.get("compliance_hooks", ["CAN-SPAM"])[0] if icp.get("compliance_hooks") else "CAN-SPAM"
        segments_yaml += f"""
  - id: "{seg_id}"
    name: "{seg_name}"
    list_name: "{seg_name} - {prospect.get('location', 'SoCal')}"
    compliance_hook: "{hook}"
    template:
      subject: "[CUSTOMIZE] Outreach subject for {{company}}"
      body: |
        Hi {{first_name}},

        [CUSTOMIZE — Write personalized email body for {company_name}'s target audience]

        -- {{sender_name}}
        {company_name}
        {{sender_email}} | {{sender_phone}}
        {{sender_website}}
"""

    return f"""# Auto-generated by prospect_for_clients.py
# ICP: {icp['name']} (Fit Score: {icp['fit_score']}/100)
# Generated: {datetime.now().strftime('%Y-%m-%d')}

company:
  key: {key}
  name: "{company_name}"
  contact: "{prospect.get('contact_name', 'TBD')}"
  email_account: "{prospect.get('email', 'TBD')}"
  industry: "{icp['name']}"
  website: "{prospect.get('website', '')}"
  phone: "{prospect.get('phone', '')}"
  tagline: "{company_name}"

harness:
  repo_path: "~/{key}-outreach-harness"
  dashboard_port: {8082 + len(config.get('companies', {}))}
  copy_industry_modules: false

segments:{segments_yaml}

billing:
  setup_fee: {icp['revenue_per_client']['setup']}
  monthly_retainer: {icp['revenue_per_client']['monthly']}

design_tokens:
  colors:
    primary: "#00C9B1"
    secondary: "#2E86DE"
    accent: "#FF6B35"
    dark: "#0B1929"
    card: "#1A3A5C"
  font_family: "'Inter', system-ui, sans-serif"
"""


def show_pipeline():
    """Show the full prospect pipeline with revenue projections."""
    print(f"\n{'='*62}")
    print(f"  APEX AI — Client Acquisition Pipeline")
    print(f"{'='*62}\n")

    # Load existing clients
    config = json.load(open(CONFIG_PATH))
    companies = config.get("companies", {})
    active = {k: v for k, v in companies.items() if v.get("status") == "active"}
    setup = {k: v for k, v in companies.items() if v.get("status") == "setup"}
    pending = {k: v for k, v in companies.items() if v.get("status") == "pending"}

    billing = config.get("apex_billing", {})
    client_billing = config.get("client_billing", {})

    current_mrr = 0
    for key, co in companies.items():
        if co.get("status") in ("active", "setup"):
            cb = client_billing.get(key, {})
            current_mrr += cb.get("monthly_retainer", billing.get("monthly_retainer_per_company", 300))

    print(f"  Current State:")
    print(f"    Active   : {len(active)} clients")
    print(f"    Setup    : {len(setup)} clients")
    print(f"    Pending  : {len(pending)} clients")
    print(f"    MRR      : ${current_mrr}/mo")
    print(f"    ARR      : ${current_mrr * 12}/yr")

    print(f"\n  Growth Projections:")
    for target in [5, 10, 20, 50]:
        avg_retainer = 450  # blended average
        projected_mrr = target * avg_retainer
        print(f"    {target:>3} clients → ${projected_mrr:>7,}/mo → ${projected_mrr * 12:>9,}/yr")

    print(f"\n  Next Steps:")
    print(f"    1. python prospect_for_clients.py --list-icp")
    print(f"    2. Source leads for top ICPs (Google Places, LinkedIn, web)")
    print(f"    3. python prospect_for_clients.py --generate-config <lead>")
    print(f"    4. python scaffold_client.py --config <generated.yaml>")
    print(f"    5. python auto_campaign.py --company <key> --source csv --file <leads.csv>")
    print()

    print(f"  Automated Onboarding Flow:")
    print(f"    YAML config → scaffold_client.py → auto_campaign.py → orchestrate.py")
    print(f"    Time: ~15 minutes from signed contract to first dry-run")
    print(f"    Human input: Fill YAML + provide Gmail credentials + approve dry-run")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Meta-prospecting engine for Apex AI Consulting.",
    )
    parser.add_argument("--list-icp", action="store_true", help="Show Ideal Client Profiles")
    parser.add_argument("--pipeline", action="store_true", help="Show client acquisition pipeline")
    parser.add_argument("--scan", action="store_true", help="Scan for prospects (requires API keys)")
    parser.add_argument("--generate-config", metavar="LEAD_ID", help="Generate client config YAML from prospect")
    args = parser.parse_args()

    if args.list_icp:
        list_icps()
    elif args.pipeline:
        show_pipeline()
    elif args.scan:
        print("\n  [INFO] Scanning requires Google Places API or web scraping setup.")
        print("  Use lead_sourcer.py with targeted queries from ICP search_queries.")
        print("  Example:")
        for icp in ICP_PROFILES[:3]:
            query = icp["search_queries"][0].format(city="Los Angeles", state="California")
            print(f"    python lead_sourcer.py --provider web --search \"{query}\"")
        print()
    elif args.generate_config:
        # Load prospect from apex_prospects.json
        if not PROSPECTS_PATH.exists():
            print(f"  [ERROR] No prospects file at {PROSPECTS_PATH}")
            print(f"  Run --scan first or create manually.")
            sys.exit(1)
        with open(PROSPECTS_PATH) as f:
            prospects = json.load(f)
        match = [p for p in prospects if p.get("id") == args.generate_config]
        if not match:
            print(f"  [ERROR] Prospect {args.generate_config} not found.")
            sys.exit(1)
        prospect = match[0]
        icp_id = prospect.get("icp_id", "ICP-01")
        icp = next((i for i in ICP_PROFILES if i["id"] == icp_id), ICP_PROFILES[0])
        yaml_content = generate_client_config(prospect, icp)
        out_path = SCRIPT_DIR / "client_configs" / f"{prospect.get('company_name', 'new').lower().replace(' ', '_')}.yaml"
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(yaml_content)
        print(f"  Generated: {out_path}")
        print(f"  Next: python scaffold_client.py --config {out_path} --dry-run")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

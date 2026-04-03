#!/usr/bin/env python3
"""
lead_sourcer.py — Provider-agnostic lead sourcing pipeline.

Searches any provider → normalizes → verifies email → scores ICP →
auto-segments → deduplicates → appends to harness leads.json.

Usage:
  python3 lead_sourcer.py --provider apollo --search "IT Manager" --location "Los Angeles" --limit 50
  python3 lead_sourcer.py --provider hunter --domain company.com
  python3 lead_sourcer.py --provider csv --file contacts.csv
  python3 lead_sourcer.py --provider web --domain company.com
  python3 lead_sourcer.py --score-existing
  python3 lead_sourcer.py --status
  python3 lead_sourcer.py --providers   (list available providers)

Flags:
  --dry-run         Preview without writing to leads.json
  --threshold N     Minimum ICP score to accept (default: 50)
  --harness PATH    Target harness directory (default: ~/james-outreach-harness)
  --skip-verify     Skip email verification step
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from lead_verifier import verify_email
from lead_scorer import score_lead
from lead_segmenter import segment_lead

# Load .env from orchestrator and harness
load_dotenv(Path(__file__).parent / ".env")
load_dotenv(Path.home() / "james-outreach-harness" / ".env")

# ── Constants ────────────────────────────────────────────────────────────

DEFAULT_HARNESS = Path.home() / "james-outreach-harness"
SOURCING_LOG = Path(__file__).parent / "sourcing_log.json"
DEFAULT_THRESHOLD = 50

# ── Helpers ──────────────────────────────────────────────────────────────


def load_json(path: Path, default=None):
    if default is None:
        default = []
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_next_lead_id(leads: list[dict]) -> int:
    """Find the highest LEAD-XXXX number and return next."""
    max_id = 0
    for lead in leads:
        lid = lead.get("id", "")
        if lid.startswith("LEAD-"):
            try:
                num = int(lid.split("-")[1])
                if num > max_id:
                    max_id = num
            except (ValueError, IndexError):
                pass
    return max_id + 1


def get_all_existing_emails(harness_path: Path) -> set[str]:
    """Load ALL existing emails from target harness + orchestrator ledgers."""
    emails: set[str] = set()

    # Target harness leads
    leads_file = harness_path / "leads.json"
    if leads_file.exists():
        leads = load_json(leads_file)
        for lead in leads:
            e = lead.get("email", "").lower().strip()
            if e:
                emails.add(e)

    # Also check other known harnesses
    for harness_name in ["ez-recycling-harness"]:
        other = Path.home() / harness_name / "leads.json"
        if other.exists():
            for lead in load_json(other):
                e = lead.get("email", "").lower().strip()
                if e:
                    emails.add(e)

    # Check send_ledger for cross-company dedup
    ledger_file = Path(__file__).parent / "send_ledger.json"
    if ledger_file.exists():
        for entry in load_json(ledger_file):
            e = entry.get("email", "").lower().strip()
            if e:
                emails.add(e)

    return emails


# ── Normalize ────────────────────────────────────────────────────────────


def normalize_lead(raw: dict, source: str, lead_id: int) -> dict:
    """Convert raw provider output to standard 22-field lead format."""
    first = raw.get("first_name", "").strip()
    last = raw.get("last_name", "").strip()
    contact = f"{first} {last}".strip() if first or last else ""

    return {
        "id": f"LEAD-{lead_id:04d}",
        "company_name": raw.get("company_name", "").strip(),
        "contact_name": contact,
        "first_name": first,
        "last_name": last,
        "title": raw.get("title", "").strip(),
        "email": raw.get("email", "").strip().lower(),
        "email_type": "work",
        "email_status": "unverified",
        "phone": raw.get("phone", "").strip(),
        "website": raw.get("website", "").strip(),
        "industry": raw.get("industry", "").strip(),
        "company_size": raw.get("company_size", "").strip(),
        "location": raw.get("location", "").strip(),
        "locality": "",
        "region": "",
        "country": raw.get("country", "United States").strip() or "United States",
        "list_name": "",  # Set by segmenter
        "status": "new",
        "notes": "",
        "date_added": date.today().isoformat(),
        "source": source,
    }


# ── Pipeline ─────────────────────────────────────────────────────────────


def run_pipeline(
    raw_leads: list[dict],
    source: str,
    harness_path: Path,
    threshold: int = DEFAULT_THRESHOLD,
    dry_run: bool = False,
    skip_verify: bool = False,
) -> dict:
    """
    Run the full sourcing pipeline. Returns stats dict.
    """
    leads_file = harness_path / "leads.json"
    existing_leads = load_json(leads_file)
    existing_emails = get_all_existing_emails(harness_path)
    next_id = get_next_lead_id(existing_leads)

    stats = {
        "provider": source,
        "raw_count": len(raw_leads),
        "normalized": 0,
        "verified": 0,
        "scored": 0,
        "passed_threshold": 0,
        "duplicates_skipped": 0,
        "no_email_skipped": 0,
        "added": 0,
        "dry_run": dry_run,
        "threshold": threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    new_leads: list[dict] = []
    log_entries: list[dict] = []
    companies_found: list[dict] = []

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing {len(raw_leads)} raw leads from {source}...")
    print(f"  Existing leads in harness: {len(existing_leads)}")
    print(f"  Known emails (all sources): {len(existing_emails)}")
    print(f"  ICP threshold: {threshold}/100\n")

    for i, raw in enumerate(raw_leads):
        email = raw.get("email", "").strip().lower()

        # If no email, check if it's a company-only record (Apollo free plan)
        if not email:
            domain = raw.get("_domain", "") or raw.get("website", "")
            if domain and raw.get("company_name"):
                # Save company for Hunter follow-up
                companies_found.append({
                    "company": raw.get("company_name", ""),
                    "domain": domain,
                    "industry": raw.get("industry", ""),
                    "size": raw.get("company_size", ""),
                    "location": raw.get("location", ""),
                })
            stats["no_email_skipped"] += 1
            continue

        # Dedup check
        if email in existing_emails:
            stats["duplicates_skipped"] += 1
            continue

        # Normalize
        lead = normalize_lead(raw, source, next_id)
        stats["normalized"] += 1

        # Verify email
        if not skip_verify:
            status, detail = verify_email(email)
            lead["email_status"] = status
            if status == "invalid":
                log_entries.append({
                    "email": email, "action": "rejected",
                    "reason": f"invalid email: {detail}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue
            stats["verified"] += 1
        else:
            lead["email_status"] = "unverified"
            stats["verified"] += 1

        # Score
        scores = score_lead(lead)
        lead["notes"] = f"ICP score: {scores['total']}/100 (T:{scores['title']} G:{scores['geography']} S:{scores['company_size']} I:{scores['industry']} E:{scores['email']})"
        stats["scored"] += 1

        # Threshold filter
        if scores["total"] < threshold:
            log_entries.append({
                "email": email, "action": "below_threshold",
                "score": scores["total"], "threshold": threshold,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            continue
        stats["passed_threshold"] += 1

        # Auto-segment
        seg_id, list_name, seg_label = segment_lead(lead)
        lead["list_name"] = list_name

        # Add to new leads
        new_leads.append(lead)
        existing_emails.add(email)  # Prevent within-batch dupes
        next_id += 1

        # Print progress
        score_str = f"{scores['total']:3d}/100"
        print(f"  ✓ [{score_str}] {seg_id} | {lead['first_name']} {lead['last_name']} — {lead['title']} @ {lead['company_name']}")

        log_entries.append({
            "email": email, "action": "added",
            "score": scores["total"], "segment": seg_id,
            "company": lead["company_name"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    stats["added"] = len(new_leads)

    # Write results
    if not dry_run and new_leads:
        existing_leads.extend(new_leads)
        save_json(leads_file, existing_leads)
        print(f"\n  ✅ Added {len(new_leads)} leads to {leads_file}")
    elif dry_run and new_leads:
        print(f"\n  [DRY RUN] Would add {len(new_leads)} leads to {leads_file}")
    else:
        print(f"\n  ⚠ No new leads passed all filters.")

    # Show companies found (Apollo free plan, no emails)
    if companies_found:
        companies_file = Path(__file__).parent / "discovered_companies.json"
        existing_companies = load_json(companies_file)
        seen_domains = {c.get("domain", "").lower() for c in existing_companies}
        new_companies = [c for c in companies_found if c["domain"].lower() not in seen_domains]
        if new_companies:
            existing_companies.extend(new_companies)
            save_json(companies_file, existing_companies)
        print(f"\n  🏢 Found {len(companies_found)} companies (no contacts on free plan)")
        print(f"     Saved {len(new_companies)} new companies to discovered_companies.json")
        print(f"     Next step: find contacts with Hunter.io:")
        for c in companies_found[:5]:
            d = c['domain'].replace('www.', '')
            print(f"       python3 lead_sourcer.py --provider hunter --domain {d}")
        if len(companies_found) > 5:
            print(f"       ... and {len(companies_found) - 5} more")

    # Update sourcing log
    sourcing_log = load_json(SOURCING_LOG)
    sourcing_log.append({"stats": stats, "entries": log_entries})
    save_json(SOURCING_LOG, sourcing_log)

    # Summary
    print(f"\n{'─' * 60}")
    print(f"  Pipeline Summary:")
    print(f"    Raw leads:          {stats['raw_count']}")
    print(f"    No email (skipped): {stats['no_email_skipped']}")
    print(f"    Duplicates:         {stats['duplicates_skipped']}")
    print(f"    Email verified:     {stats['verified']}")
    print(f"    Scored:             {stats['scored']}")
    print(f"    Passed threshold:   {stats['passed_threshold']}")
    print(f"    Added to harness:   {stats['added']}")
    print(f"{'─' * 60}\n")

    return stats


# ── Score existing leads ─────────────────────────────────────────────────


def score_existing(harness_path: Path):
    """Re-score all existing leads and print distribution."""
    leads_file = harness_path / "leads.json"
    leads = load_json(leads_file)

    if not leads:
        print("No leads found.")
        return

    print(f"\nScoring {len(leads)} existing leads...\n")

    buckets = {"90-100": 0, "70-89": 0, "50-69": 0, "30-49": 0, "0-29": 0}
    total_score = 0
    segment_counts: dict[str, int] = {}

    for lead in leads:
        scores = score_lead(lead)
        s = scores["total"]
        total_score += s

        if s >= 90:
            buckets["90-100"] += 1
        elif s >= 70:
            buckets["70-89"] += 1
        elif s >= 50:
            buckets["50-69"] += 1
        elif s >= 30:
            buckets["30-49"] += 1
        else:
            buckets["0-29"] += 1

        seg_id, _, _ = segment_lead(lead)
        segment_counts[seg_id] = segment_counts.get(seg_id, 0) + 1

    avg = total_score / len(leads) if leads else 0

    print(f"  ICP Score Distribution:")
    print(f"    90-100 (🔥 Hot):     {buckets['90-100']:5d}")
    print(f"    70-89  (✓ Strong):   {buckets['70-89']:5d}")
    print(f"    50-69  (~ Moderate): {buckets['50-69']:5d}")
    print(f"    30-49  (↓ Weak):     {buckets['30-49']:5d}")
    print(f"    0-29   (✗ Poor):     {buckets['0-29']:5d}")
    print(f"    Average score:       {avg:.1f}/100")

    print(f"\n  Segment Distribution:")
    for seg in sorted(segment_counts):
        print(f"    {seg}: {segment_counts[seg]} leads")

    print()


# ── Status ───────────────────────────────────────────────────────────────


def show_status():
    """Show sourcing activity stats."""
    log = load_json(SOURCING_LOG)

    if not log:
        print("\nNo sourcing activity yet. Run a search to get started.\n")
        return

    total_added = sum(entry["stats"]["added"] for entry in log)
    total_raw = sum(entry["stats"]["raw_count"] for entry in log)
    total_dupes = sum(entry["stats"]["duplicates_skipped"] for entry in log)

    providers_used = set()
    for entry in log:
        providers_used.add(entry["stats"]["provider"])

    print(f"\n{'─' * 60}")
    print(f"  Lead Sourcing Status")
    print(f"{'─' * 60}")
    print(f"  Total runs:        {len(log)}")
    print(f"  Raw leads found:   {total_raw}")
    print(f"  Leads added:       {total_added}")
    print(f"  Duplicates caught: {total_dupes}")
    print(f"  Providers used:    {', '.join(sorted(providers_used))}")

    # Last 5 runs
    print(f"\n  Recent runs:")
    for entry in log[-5:]:
        s = entry["stats"]
        ts = s.get("timestamp", "")[:16]
        dr = " [DRY RUN]" if s.get("dry_run") else ""
        print(f"    {ts} | {s['provider']:8s} | +{s['added']} added, {s['raw_count']} raw{dr}")

    print(f"{'─' * 60}\n")


# ── List providers ───────────────────────────────────────────────────────


def list_providers():
    """Show all available providers."""
    from providers import PROVIDER_REGISTRY

    print(f"\n{'─' * 60}")
    print(f"  Available Lead Providers")
    print(f"{'─' * 60}")

    for key, cls in PROVIDER_REGISTRY.items():
        p = cls()
        api = "🔑 API key required" if p.requires_api_key() else "🆓 No API key needed"
        print(f"\n  {key}")
        print(f"    Name:       {p.name()}")
        print(f"    Auth:       {api}")
        print(f"    Rate limit: {p.rate_limit_msg()}")

    print(f"\n{'─' * 60}\n")


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Lead Sourcing Agent — find, verify, score, and segment leads"
    )
    parser.add_argument("--provider", choices=["apollo", "hunter", "csv", "web"],
                        help="Data provider to search")
    parser.add_argument("--search", help="Search query (title, keywords)")
    parser.add_argument("--location", help="Location filter")
    parser.add_argument("--domain", help="Company domain (for Hunter/Web)")
    parser.add_argument("--file", help="CSV file path (for CSV provider)")
    parser.add_argument("--industry", help="Industry filter")
    parser.add_argument("--company-size", help="Company size range (e.g., '51-100,101-200')")
    parser.add_argument("--limit", type=int, default=25, help="Max leads to fetch (default: 25)")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                        help=f"Min ICP score to accept (default: {DEFAULT_THRESHOLD})")
    parser.add_argument("--harness", type=Path, default=DEFAULT_HARNESS,
                        help="Target harness directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--skip-verify", action="store_true", help="Skip email verification")
    parser.add_argument("--score-existing", action="store_true", help="Re-score existing leads")
    parser.add_argument("--status", action="store_true", help="Show sourcing stats")
    parser.add_argument("--providers", action="store_true", help="List available providers")

    args = parser.parse_args()

    # Status / info commands
    if args.status:
        show_status()
        return
    if args.providers:
        list_providers()
        return
    if args.score_existing:
        score_existing(args.harness)
        return

    # Provider search
    if not args.provider:
        parser.print_help()
        print("\n  ERROR: --provider is required for search mode.\n")
        sys.exit(1)

    from providers import PROVIDER_REGISTRY

    if args.provider not in PROVIDER_REGISTRY:
        print(f"Unknown provider: {args.provider}")
        sys.exit(1)

    provider = PROVIDER_REGISTRY[args.provider]()
    print(f"\n🔍 Sourcing leads via {provider.name()}...")

    # Build search kwargs
    search_kwargs = {
        "search": args.search or "",
        "location": args.location or "",
        "domain": args.domain or "",
        "file": args.file or "",
        "industry": args.industry or "",
        "company_size": args.company_size or "",
        "limit": args.limit,
    }

    try:
        raw_leads = provider.search(**search_kwargs)
    except (ValueError, ImportError, FileNotFoundError) as e:
        print(f"\n  ❌ {e}\n")
        sys.exit(1)

    if not raw_leads:
        print(f"\n  No leads found. Try adjusting your search criteria.\n")
        return

    print(f"  Found {len(raw_leads)} raw leads from {provider.name()}")

    # Run pipeline
    run_pipeline(
        raw_leads=raw_leads,
        source=args.provider,
        harness_path=args.harness,
        threshold=args.threshold,
        dry_run=args.dry_run,
        skip_verify=args.skip_verify,
    )


if __name__ == "__main__":
    main()

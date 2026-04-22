#!/usr/bin/env python3
from __future__ import annotations
"""
auto_campaign.py — Automated campaign launcher for Apex AI Orchestrator.

Takes a scaffolded harness from zero to launch in one command:
  1. Source leads (CSV import, Apollo, or crawler)
  2. Score & segment leads
  3. Verify emails (ZeroBounce)
  4. Deconflict against all companies
  5. Dry-run preview
  6. Launch (with confirmation gate)

Usage:
    python auto_campaign.py --company acme_corp --source csv --file leads.csv
    python auto_campaign.py --company acme_corp --source csv --file leads.csv --auto-launch
    python auto_campaign.py --company acme_corp --status
    python auto_campaign.py --company acme_corp --activate

Requires: scaffold_client.py must have been run first.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "company_config.json"


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def save_config(config: dict) -> None:
    config["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def resolve_repo(company: dict) -> Path:
    return Path(company["repo"].replace("~", str(Path.home())))


def step_banner(step: int, total: int, title: str) -> None:
    print(f"\n{'━'*62}")
    print(f"  Step {step}/{total}: {title}")
    print(f"{'━'*62}")


# ─────────────────────────────────────────────────────────────
# Step 1: Import leads from CSV
# ─────────────────────────────────────────────────────────────

def import_csv_leads(csv_path: str, company: dict, config: dict) -> int:
    """Import leads from a CSV file into the harness leads.json."""
    repo = resolve_repo(company)
    leads_path = repo / "leads.json"

    # Load existing leads
    existing = []
    if leads_path.exists():
        with open(leads_path) as f:
            existing = json.load(f)
    existing_emails = {(l.get("email") or "").lower().strip() for l in existing}

    # Auto-detect CSV columns
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        raw_fields = reader.fieldnames or []

        # Column alias mapping (handles WIZA, Apollo, Hunter, generic exports)
        ALIASES = {
            "email": ["email", "email_address", "e-mail", "contact_email", "work_email", "email address"],
            "first_name": ["first_name", "first name", "firstname", "given_name", "given name"],
            "last_name": ["last_name", "last name", "lastname", "surname", "family_name"],
            "contact_name": ["contact_name", "full_name", "full name", "name", "contact name"],
            "title": ["title", "job_title", "job title", "position", "role"],
            "company_name": ["company_name", "company", "company name", "organization", "org"],
            "phone": ["phone", "phone_number", "phone number", "direct_phone", "mobile"],
            "website": ["website", "company_website", "url", "domain"],
            "industry": ["industry", "industry_name"],
            "location": ["location", "city_state", "address", "city"],
            "company_size": ["company_size", "employees", "headcount", "size"],
        }

        def find_col(target: str) -> str | None:
            aliases = ALIASES.get(target, [target])
            for alias in aliases:
                for field in raw_fields:
                    if field.strip().lower() == alias.lower():
                        return field
            return None

        # Determine segment from company config
        seg_ids = company.get("owned_segments", [])
        seg_names = company.get("segment_names", [])
        default_list_name = seg_names[0] if seg_names else "Imported"
        default_seg = seg_ids[0] if seg_ids else "UNKNOWN"

        new_leads = []
        lead_counter = len(existing)
        today = datetime.now().strftime("%Y-%m-%d")

        for row in reader:
            email_col = find_col("email")
            email = (row.get(email_col, "") if email_col else "").strip()
            if not email or email.lower() in existing_emails:
                continue

            lead_counter += 1
            first_col = find_col("first_name")
            last_col = find_col("last_name")
            name_col = find_col("contact_name")

            first_name = (row.get(first_col, "") if first_col else "").strip()
            last_name = (row.get(last_col, "") if last_col else "").strip()
            full_name = (row.get(name_col, "") if name_col else "").strip()

            if not first_name and full_name:
                parts = full_name.split()
                first_name = parts[0] if parts else ""
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

            contact_name = f"{first_name} {last_name}".strip() or full_name

            title_col = find_col("title")
            company_col = find_col("company_name")
            phone_col = find_col("phone")
            website_col = find_col("website")
            industry_col = find_col("industry")
            location_col = find_col("location")
            size_col = find_col("company_size")

            lead = {
                "id": f"LEAD-{lead_counter:04d}",
                "contact_name": contact_name,
                "first_name": first_name,
                "last_name": last_name,
                "title": (row.get(title_col, "") if title_col else "").strip(),
                "company_name": (row.get(company_col, "") if company_col else "").strip(),
                "email": email,
                "email_status": "unknown",
                "phone": (row.get(phone_col, "") if phone_col else "").strip(),
                "website": (row.get(website_col, "") if website_col else "").strip(),
                "industry": (row.get(industry_col, "") if industry_col else "").strip(),
                "location": (row.get(location_col, "") if location_col else "").strip(),
                "company_size": (row.get(size_col, "") if size_col else "").strip(),
                "list_name": default_list_name,
                "source": "csv_import",
                "date_added": today,
                "status": "new",
                "notes": "",
            }
            new_leads.append(lead)
            existing_emails.add(email.lower())

    if not new_leads:
        print("  No new leads found (all duplicates or no emails).")
        return 0

    # Merge and save
    all_leads = existing + new_leads
    with open(leads_path, "w") as f:
        json.dump(all_leads, f, indent=2)

    # Update segment registry lead count
    config_updated = load_config()
    for seg_id in seg_ids:
        if seg_id in config_updated.get("segment_registry", {}):
            seg_leads = [l for l in all_leads if l.get("list_name") in
                         (config_updated["segment_registry"][seg_id].get("name", ""),
                          *company.get("segment_names", []))]
            config_updated["segment_registry"][seg_id]["lead_count"] = len(all_leads)
    save_config(config_updated)

    print(f"  Imported {len(new_leads)} new leads ({len(existing)} existing, {len(all_leads)} total)")
    print(f"  Saved to {leads_path}")
    return len(new_leads)


# ─────────────────────────────────────────────────────────────
# Step 2: Verify emails
# ─────────────────────────────────────────────────────────────

def verify_leads(company: dict) -> dict:
    """Run ZeroBounce verification on unverified leads. Returns stats."""
    repo = resolve_repo(company)
    verifier = SCRIPT_DIR / "lead_verifier.py"

    if not verifier.exists():
        print("  [SKIP] lead_verifier.py not found. Manual verification required.")
        return {"verified": 0, "skipped": True}

    leads_path = repo / "leads.json"
    result = subprocess.run(
        ["python3", str(verifier), "--file", str(leads_path), "--unverified-only"],
        capture_output=True, text=True,
    )

    if result.returncode == 0:
        print(f"  {result.stdout.strip()}")
    else:
        print(f"  [WARN] Verification returned errors. Check lead_verifier.py output.")
        if result.stderr:
            print(f"  {result.stderr.strip()[:200]}")

    # Count verification status
    with open(leads_path) as f:
        leads = json.load(f)
    stats = {
        "total": len(leads),
        "valid": sum(1 for l in leads if l.get("email_status") == "valid" or l.get("zb_status") == "valid"),
        "invalid": sum(1 for l in leads if l.get("email_status") == "invalid" or l.get("zb_status") == "invalid"),
        "unknown": sum(1 for l in leads if l.get("email_status", "unknown") == "unknown" and not l.get("zb_status")),
    }
    print(f"  Status: {stats['valid']} valid, {stats['invalid']} invalid, {stats['unknown']} unverified")
    return stats


# ─────────────────────────────────────────────────────────────
# Step 3: Deconflict
# ─────────────────────────────────────────────────────────────

def deconflict(company_key: str) -> int:
    """Run deconfliction against all companies. Returns number of conflicts found."""
    deconflict_script = SCRIPT_DIR / "deconflict.py"
    if not deconflict_script.exists():
        print("  [SKIP] deconflict.py not found.")
        return 0

    result = subprocess.run(
        ["python3", str(deconflict_script), "--company", company_key],
        capture_output=True, text=True, cwd=str(SCRIPT_DIR),
    )

    if result.returncode == 0:
        output = result.stdout.strip()
        if output:
            print(f"  {output[:500]}")
        return 0
    else:
        print(f"  [WARN] Deconfliction check returned issues.")
        if result.stdout:
            print(f"  {result.stdout.strip()[:300]}")
        return 1


# ─────────────────────────────────────────────────────────────
# Step 4: Dry-run preview
# ─────────────────────────────────────────────────────────────

def dry_run_preview(company: dict, company_key: str, segment: str, limit: int = 3) -> bool:
    """Run a dry-run send preview. Returns True if successful."""
    result = subprocess.run(
        ["python3", str(SCRIPT_DIR / "orchestrate.py"),
         "--company", company_key,
         "--segment", segment,
         "--dry-run",
         "--limit", str(limit)],
        cwd=str(SCRIPT_DIR),
    )
    return result.returncode == 0


# ─────────────────────────────────────────────────────────────
# Step 5: Activate company
# ─────────────────────────────────────────────────────────────

def activate_company(company_key: str) -> None:
    """Move company status from setup to active."""
    config = load_config()
    if company_key not in config["companies"]:
        print(f"  [ERROR] Unknown company: {company_key}")
        return

    company = config["companies"][company_key]
    if company["status"] == "active":
        print(f"  {company['name']} is already active.")
        return

    company["status"] = "active"
    save_config(config)
    print(f"  {company['name']} activated. Ready for live sends.")


# ─────────────────────────────────────────────────────────────
# Status report
# ─────────────────────────────────────────────────────────────

def campaign_status(company: dict, company_key: str, config: dict) -> None:
    """Print campaign readiness status for a company."""
    repo = resolve_repo(company)
    leads_path = repo / "leads.json"
    log_path = repo / "email_log.json"
    env_path = repo / ".env"

    print(f"\n{'━'*62}")
    print(f"  Campaign Status: {company['name']}")
    print(f"{'━'*62}\n")

    # Check credentials
    has_env = env_path.exists()
    env_has_password = False
    if has_env:
        with open(env_path) as f:
            env_content = f.read()
            env_has_password = "EMAIL_APP_PASSWORD=" in env_content and "xxxx" not in env_content
    print(f"  Credentials   : {'OK' if env_has_password else 'MISSING — fill in .env'}")

    # Check leads
    lead_count = 0
    verified_count = 0
    if leads_path.exists():
        with open(leads_path) as f:
            leads = json.load(f)
            lead_count = len(leads)
            verified_count = sum(1 for l in leads if
                                 l.get("email_status") == "valid" or l.get("zb_status") == "valid")
    print(f"  Leads         : {lead_count} total, {verified_count} verified")

    # Check sends
    sent_count = 0
    if log_path.exists():
        with open(log_path) as f:
            log = json.load(f)
            sent_count = sum(1 for e in log if e.get("status") == "sent")
    print(f"  Sent          : {sent_count}")

    # Check segments
    print(f"  Segments      : {', '.join(company.get('owned_segments', []))}")
    print(f"  Status        : {company.get('status', 'unknown').upper()}")

    # Readiness
    checks = {
        "Credentials": env_has_password,
        "Leads imported": lead_count > 0,
        "Leads verified": verified_count > 0,
        "Company active": company.get("status") == "active",
    }
    all_ready = all(checks.values())

    print(f"\n  Launch Readiness:")
    for check, passed in checks.items():
        icon = "\u2705" if passed else "\u274c"
        print(f"    {icon}  {check}")

    if all_ready:
        print(f"\n  READY TO LAUNCH. Run:")
        for seg in company.get("owned_segments", []):
            print(f"    python orchestrate.py --company {company_key} --segment {seg} --dry-run")
    else:
        print(f"\n  NOT READY — complete the items above first.")
    print()


# ─────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────

def run_pipeline(company_key: str, source: str, file_path: str | None,
                 auto_launch: bool = False, skip_verify: bool = False) -> None:
    """Run the full automated campaign pipeline."""
    config = load_config()

    if company_key not in config["companies"]:
        print(f"[ERROR] Unknown company: {company_key}")
        print(f"  Valid: {', '.join(config['companies'].keys())}")
        sys.exit(1)

    company = config["companies"][company_key]
    total_steps = 5

    print(f"\n{'='*62}")
    print(f"  AUTO-CAMPAIGN PIPELINE")
    print(f"  Company : {company['name']}")
    print(f"  Source  : {source}")
    print(f"  File    : {file_path or 'N/A'}")
    print(f"{'='*62}")

    # Step 1: Import leads
    step_banner(1, total_steps, "Import Leads")
    if source == "csv" and file_path:
        imported = import_csv_leads(file_path, company, config)
        if imported == 0:
            print("  No new leads to process. Pipeline complete.")
            return
    else:
        print(f"  Source '{source}' — manual import. Skipping.")

    # Step 2: Verify emails
    step_banner(2, total_steps, "Verify Emails (ZeroBounce)")
    if skip_verify:
        print("  [SKIP] --skip-verify flag set.")
    else:
        verify_leads(company)

    # Step 3: Deconflict
    step_banner(3, total_steps, "Cross-Company Deconfliction")
    deconflict(company_key)

    # Step 4: Dry-run preview
    step_banner(4, total_steps, "Dry-Run Preview")
    first_seg = company["owned_segments"][0] if company["owned_segments"] else None
    if first_seg:
        success = dry_run_preview(company, company_key, first_seg)
        if not success:
            print("  [BLOCKED] Dry-run failed. Fix issues before launching.")
            return
    else:
        print("  [SKIP] No segments assigned.")

    # Step 5: Activate & launch gate
    step_banner(5, total_steps, "Activate & Launch")
    if company.get("status") != "active":
        if auto_launch:
            activate_company(company_key)
        else:
            print(f"  Company status is '{company['status']}'. To activate:")
            print(f"    python auto_campaign.py --company {company_key} --activate")
            print(f"  Or re-run with --auto-launch to activate automatically.")
            return

    print(f"\n{'='*62}")
    print(f"  PIPELINE COMPLETE")
    print(f"  {company['name']} is ready for live outreach.")
    print(f"  Launch with:")
    for seg in company.get("owned_segments", []):
        print(f"    python orchestrate.py --company {company_key} --segment {seg}")
    print(f"{'='*62}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Automated campaign pipeline for Apex AI Orchestrator.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python auto_campaign.py --company acme_corp --source csv --file leads.csv\n"
            "  python auto_campaign.py --company acme_corp --source csv --file leads.csv --auto-launch\n"
            "  python auto_campaign.py --company acme_corp --status\n"
            "  python auto_campaign.py --company acme_corp --activate\n"
        ),
    )
    parser.add_argument("--company", required=True, help="Company key from company_config.json")
    parser.add_argument("--source", choices=["csv", "apollo", "hunter", "manual"], default="manual",
                        help="Lead source type")
    parser.add_argument("--file", metavar="PATH", help="CSV file path (for --source csv)")
    parser.add_argument("--auto-launch", action="store_true",
                        help="Auto-activate company and launch (no manual gate)")
    parser.add_argument("--skip-verify", action="store_true",
                        help="Skip ZeroBounce verification step")
    parser.add_argument("--status", action="store_true", help="Show campaign readiness status")
    parser.add_argument("--activate", action="store_true", help="Activate company for live sends")
    args = parser.parse_args()

    config = load_config()

    if args.company not in config["companies"]:
        print(f"[ERROR] Unknown company: {args.company}")
        print(f"  Valid: {', '.join(config['companies'].keys())}")
        sys.exit(1)

    company = config["companies"][args.company]

    if args.status:
        campaign_status(company, args.company, config)
        return

    if args.activate:
        activate_company(args.company)
        return

    run_pipeline(
        company_key=args.company,
        source=args.source,
        file_path=args.file,
        auto_launch=args.auto_launch,
        skip_verify=args.skip_verify,
    )


if __name__ == "__main__":
    main()

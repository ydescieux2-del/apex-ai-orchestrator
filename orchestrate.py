#!/usr/bin/env python3
"""
orchestrate.py — Apex AI Consulting outreach orchestration layer
Wraps send_emails.py with segment ownership enforcement.

Usage:
  python orchestrate.py --company datatech --segment SEG-1 --dry-run
  python orchestrate.py --company ez_recycling --segment SEG-6
  python orchestrate.py --status          # show all companies + segments
  python orchestrate.py --audit           # cross-company dedup check
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

CONFIG_PATH = Path(__file__).parent / "company_config.json"
MASTER_LOG  = Path(__file__).parent / "master_send_log.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def print_status(config):
    print(f"\n{'─'*60}")
    print(f"  APEX AI OUTREACH ORCHESTRATION")
    print(f"  {config['orchestrator']}")
    print(f"{'─'*60}\n")
    for key, co in config["companies"].items():
        status_icon = {"active": "●", "setup": "◎", "pending": "○"}.get(co["status"], "?")
        print(f"  {status_icon}  {co['name']}  [{co['status'].upper()}]")
        print(f"       Contact : {co['contact']}")
        print(f"       Account : {co['email_account']}")
        for seg_id in co["owned_segments"]:
            seg = config["segment_registry"][seg_id]
            lead_count = seg['lead_count'] if seg['lead_count'] != 'TBD' else 'TBD'
            print(f"       {seg_id}: {seg['name']} — {lead_count} leads")
        if co.get("notes"):
            print(f"       Note    : {co['notes']}")
        print()

    rules = config.get("global_rules", {})
    print(f"  Global Rules:")
    print(f"    No cross-company sends : {rules.get('no_cross_company_sends', True)}")
    print(f"    Dry run required first : {rules.get('require_dry_run_before_live', True)}")
    print(f"    ZeroBounce required    : {rules.get('zerobounce_verify_before_large_send', True)}")
    print(f"    Send delay             : {rules.get('min_delay_between_sends_seconds')}–"
          f"{rules.get('max_delay_between_sends_seconds')}s\n")


def enforce_ownership(config, company_key, segment_id):
    """Raise if company does not own the requested segment."""
    company = config["companies"].get(company_key)
    if not company:
        print(f"\n[ERROR] Unknown company key: '{company_key}'")
        print(f"        Valid keys: {', '.join(config['companies'].keys())}")
        sys.exit(1)

    if segment_id not in company["owned_segments"]:
        owner_key  = config["segment_registry"].get(segment_id, {}).get("owner", "unknown")
        owner_name = config["companies"].get(owner_key, {}).get("name", owner_key)
        print(f"\n[BLOCKED] Segment ownership violation")
        print(f"  Company      : {company['name']}")
        print(f"  Requested    : {segment_id}")
        print(f"  Owns         : {', '.join(company['owned_segments'])}")
        print(f"  Actual owner : {owner_name}")
        print(f"\n  This send has been blocked. Each segment is exclusive to one company.")
        sys.exit(1)

    print(f"\n[OK] Ownership verified: {company['name']} owns {segment_id}")


def log_send(company_key, company_name, segment_id, dry_run, result):
    """Append send event to master cross-company log."""
    log = []
    if MASTER_LOG.exists():
        with open(MASTER_LOG) as f:
            try:
                log = json.load(f)
            except json.JSONDecodeError:
                log = []

    log.append({
        "timestamp":    datetime.utcnow().isoformat() + "Z",
        "company_key":  company_key,
        "company_name": company_name,
        "segment":      segment_id,
        "dry_run":      dry_run,
        "result":       result,
    })

    with open(MASTER_LOG, "w") as f:
        json.dump(log, f, indent=2)


def run_audit(config):
    """Check for leads that may appear in multiple company segments."""
    print(f"\n[AUDIT] Cross-company dedup check")
    print(f"  Rule: A single lead/email must appear in exactly ONE company's segment.\n")

    all_emails: dict[str, list[str]] = {}

    for key, co in config["companies"].items():
        repo_path = Path(co["repo"].replace("~", str(Path.home())))
        for seg_id in co["owned_segments"]:
            # Try both leads.json and CSV paths
            leads_json = repo_path / "leads.json"
            leads_csv  = repo_path / "leads" / f"{seg_id.lower().replace('-','')}-*.csv"

            emails_found = set()

            if leads_json.exists():
                import json as _json
                with open(leads_json) as f:
                    try:
                        leads = _json.load(f)
                        seg_registry = config["segment_registry"].get(seg_id, {})
                        for lead in leads:
                            email = (lead.get("email") or "").strip().lower()
                            if email:
                                emails_found.add(email)
                    except Exception:
                        pass

            for email in emails_found:
                if email not in all_emails:
                    all_emails[email] = []
                all_emails[email].append(f"{key}/{seg_id}")

    # Find duplicates
    dupes = {e: owners for e, owners in all_emails.items() if len(owners) > 1}

    # Print ownership map
    print(f"  Segment ownership map:")
    for seg_id, seg in config["segment_registry"].items():
        owner     = seg["owner"]
        owner_name = config["companies"].get(owner, {}).get("name", owner)
        status    = config["companies"].get(owner, {}).get("status", "unknown")
        print(f"    {seg_id:8} → {owner_name:35} [{seg['lead_count']} leads] [{status}]")

    print()
    if dupes:
        print(f"  [WARNING] {len(dupes)} duplicate email(s) found across segments:")
        for email, owners in list(dupes.items())[:20]:
            print(f"    {email}  →  {', '.join(owners)}")
        if len(dupes) > 20:
            print(f"    ... and {len(dupes) - 20} more")
    else:
        print(f"  [OK] No cross-company email duplicates detected in checked sources.")

    print(f"\n  Note: CSV-based leads (ez-recycling-harness) not yet checked — add leads first.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Apex AI outreach orchestration layer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python orchestrate.py --status\n"
            "  python orchestrate.py --audit\n"
            "  python orchestrate.py --company datatech --segment SEG-1 --dry-run\n"
            "  python orchestrate.py --company ez_recycling --segment SEG-6 --dry-run\n"
            "  python orchestrate.py --company ez_recycling --segment SEG-6\n"
        ),
    )
    parser.add_argument("--company",  help="Company key (datatech, ez_recycling, company_3, company_4)")
    parser.add_argument("--segment",  help="Segment ID (SEG-1 through SEG-7)")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without sending")
    parser.add_argument("--limit",    metavar="N", type=int, default=None, help="Cap leads processed")
    parser.add_argument("--status",   action="store_true", help="Show all companies and segments")
    parser.add_argument("--audit",    action="store_true", help="Cross-company dedup check")
    args = parser.parse_args()

    config = load_config()

    if args.status:
        print_status(config)
        return

    if args.audit:
        run_audit(config)
        return

    if not args.company or not args.segment:
        parser.print_help()
        sys.exit(1)

    # Enforce segment ownership — the primary guardrail
    enforce_ownership(config, args.company, args.segment)

    company = config["companies"][args.company]

    if company["status"] == "pending":
        print(f"\n[BLOCKED] {company['name']} is not yet active.")
        print(f"  Status: {company['status']}")
        print(f"  Complete setup before sending.\n")
        sys.exit(1)

    # Build and run the send command for this company's harness
    harness_path = Path(company["repo"].replace("~", str(Path.home())))
    send_script  = harness_path / "send_emails.py"

    if not send_script.exists():
        print(f"\n[ERROR] send_emails.py not found at {send_script}")
        print(f"  Run harness setup for {company['name']} first.\n")
        sys.exit(1)

    cmd = ["python3", str(send_script), "--segment", args.segment]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.limit is not None:
        cmd += ["--limit", str(args.limit)]

    mode = "DRY RUN" if args.dry_run else "LIVE SEND"
    print(f"\n{'─'*60}")
    print(f"  Company  : {company['name']}")
    print(f"  Segment  : {args.segment}")
    print(f"  Mode     : {mode}")
    print(f"  Account  : {company['email_account']}")
    print(f"  Harness  : {harness_path}")
    print(f"{'─'*60}\n")

    result = subprocess.run(cmd, cwd=harness_path)
    outcome = "success" if result.returncode == 0 else "error"
    log_send(args.company, company["name"], args.segment, args.dry_run, outcome)

    if outcome == "error":
        print(f"\n[ORCHESTRATOR] Send exited with error. Logged to master_send_log.json.")
    else:
        print(f"\n[ORCHESTRATOR] Complete. Logged to master_send_log.json.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
deconflict.py — Cross-company lead deconfliction for ITAD outreach

Central coordination layer that ensures:
  1. No lead receives solicitation from more than one company on the same day
  2. No lead receives more than one solicitation across ALL companies in a 5-day window
  3. Lead assignment includes randomness (shuffled batches)
  4. All sends are logged to a single master ledger for audit

Usage:
  # Request a deconflicted batch of leads for a company/segment
  python deconflict.py --company datatech --segment SEG-1 --batch-size 20

  # Check if a specific email is clear to contact
  python deconflict.py --check-email someone@example.com

  # View cooldown status across all companies
  python deconflict.py --status

  # Purge expired cooldowns (older than 5 days)
  python deconflict.py --purge

Library usage (imported by orchestrate.py):
  from deconflict import is_clear_to_send, record_send, get_deconflicted_batch
"""

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

COOLDOWN_DAYS = 5
LEDGER_PATH = Path(__file__).parent / "send_ledger.json"
CONFIG_PATH = Path(__file__).parent / "company_config.json"


# ─── Ledger I/O ──────────────────────────────────────────────

def load_ledger() -> list[dict]:
    if not LEDGER_PATH.exists():
        return []
    with open(LEDGER_PATH) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_ledger(ledger: list[dict]) -> None:
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)


# ─── Core deconfliction logic ────────────────────────────────

def _parse_ts(ts: str) -> datetime | None:
    """Parse a timestamp string into a timezone-aware datetime, or None."""
    if not ts:
        return None
    try:
        # Full ISO with offset: "2026-03-30T15:34:21Z" or "2026-03-30T15:34:21+00:00"
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        pass
    try:
        # Date-only: "2026-03-30"
        dt = datetime.strptime(ts[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def get_recent_sends(ledger: list[dict], days: int = COOLDOWN_DAYS) -> dict[str, dict]:
    """Return {email: {company, segment, timestamp}} for all sends within cooldown window."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent = {}
    for entry in ledger:
        sent_at = _parse_ts(entry.get("timestamp", ""))
        if sent_at is None:
            continue
        if sent_at >= cutoff:
            email = entry.get("email", "").lower().strip()
            if email:
                # Keep the most recent send per email
                existing_ts = _parse_ts(recent[email]["timestamp"]) if email in recent else None
                if existing_ts is None or sent_at > existing_ts:
                    recent[email] = entry
    return recent


def is_clear_to_send(email: str, company_key: str, ledger: list[dict] | None = None) -> tuple[bool, str]:
    """Check if an email address is clear to receive outreach.

    Returns (True, "") if clear, or (False, reason) if blocked.
    """
    if ledger is None:
        ledger = load_ledger()

    email = email.lower().strip()
    if not email:
        return False, "empty email"

    recent = get_recent_sends(ledger)

    if email in recent:
        entry = recent[email]
        sent_at = entry["timestamp"]
        sent_by = entry.get("company_key", "unknown")
        sent_seg = entry.get("segment", "?")

        # Calculate days remaining in cooldown
        ts = _parse_ts(sent_at)
        if ts:
            expires = ts + timedelta(days=COOLDOWN_DAYS)
            remaining = max(0, (expires - datetime.now(timezone.utc)).days)
        else:
            remaining = "?"

        if sent_by == company_key:
            return False, f"already contacted by {sent_by} ({sent_seg}) — {remaining}d cooldown remaining"
        else:
            return False, f"contacted by {sent_by} ({sent_seg}) — {remaining}d cooldown remaining (cross-company block)"

    return True, ""


def record_send(email: str, company_key: str, company_name: str, segment: str,
                lead_id: str = "", contact_name: str = "", company_target: str = "",
                dry_run: bool = False) -> None:
    """Record a send event to the master deconfliction ledger."""
    ledger = load_ledger()
    ledger.append({
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "email": email.lower().strip(),
        "company_key": company_key,
        "company_name": company_name,
        "segment": segment,
        "lead_id": lead_id,
        "contact_name": contact_name,
        "company_target": company_target,
        "dry_run": dry_run,
    })
    save_ledger(ledger)


def get_deconflicted_batch(
    leads: list[dict],
    company_key: str,
    segment: str,
    batch_size: int = 20,
    ledger: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return (eligible, blocked) leads after deconfliction.

    - Shuffles eligible leads for randomness
    - Caps at batch_size
    - Returns blocked leads separately for reporting
    """
    if ledger is None:
        ledger = load_ledger()

    eligible = []
    blocked = []

    for lead in leads:
        email = (lead.get("email") or "").lower().strip()
        if not email:
            continue

        clear, reason = is_clear_to_send(email, company_key, ledger)
        if clear:
            eligible.append(lead)
        else:
            blocked.append({"lead": lead, "reason": reason})

    # Randomize the eligible pool
    random.shuffle(eligible)

    # Cap to batch size
    batch = eligible[:batch_size]
    overflow = eligible[batch_size:]

    return batch, blocked


# ─── Cross-company email log collection ──────────────────────

def collect_all_email_logs(config: dict) -> list[dict]:
    """Scan all company harnesses and collect email_log.json entries.

    This is used to backfill the ledger from existing per-company logs.
    """
    all_entries = []
    for key, co in config.get("companies", {}).items():
        repo = Path(co["repo"].replace("~", str(Path.home())))
        log_path = repo / "email_log.json"
        if log_path.exists():
            try:
                with open(log_path) as f:
                    entries = json.load(f)
                for entry in entries:
                    if entry.get("status") in ("sent", "dry-run"):
                        email = (
                            entry.get("to_email") or
                            entry.get("contact_email") or
                            entry.get("email") or ""
                        ).lower().strip()
                        if email:
                            all_entries.append({
                                "email": email,
                                "company_key": key,
                                "company_name": co["name"],
                                "segment": entry.get("segment", ""),
                                "lead_id": entry.get("lead_id", ""),
                                "contact_name": entry.get("contact_name", ""),
                                "company_target": entry.get("company_name", ""),
                                "timestamp": entry.get("sent_at") or entry.get("date_created", ""),
                                "dry_run": entry.get("status") == "dry-run",
                            })
            except (json.JSONDecodeError, KeyError):
                pass
    return all_entries


def sync_ledger_from_logs(config: dict) -> int:
    """Backfill send_ledger.json from all company email_log.json files.

    Only adds entries not already in the ledger (by email+timestamp).
    Returns count of new entries added.
    """
    ledger = load_ledger()
    existing = {
        (e.get("email", ""), e.get("timestamp", ""))
        for e in ledger
    }

    new_entries = collect_all_email_logs(config)
    added = 0
    for entry in new_entries:
        key = (entry["email"], entry["timestamp"])
        if key not in existing:
            ledger.append(entry)
            existing.add(key)
            added += 1

    if added:
        save_ledger(ledger)
    return added


# ─── CLI ──────────────────────────────────────────────────────

def cmd_status():
    """Show cooldown status across all companies."""
    ledger = load_ledger()
    recent = get_recent_sends(ledger)

    print(f"\n{'─'*65}")
    print(f"  DECONFLICTION STATUS — {COOLDOWN_DAYS}-Day Cooldown Window")
    print(f"{'─'*65}")
    print(f"  Total ledger entries : {len(ledger)}")
    print(f"  Active cooldowns     : {len(recent)}")

    # Group by company
    by_company: dict[str, int] = {}
    for entry in recent.values():
        ck = entry.get("company_key", "unknown")
        by_company[ck] = by_company.get(ck, 0) + 1

    if by_company:
        print(f"\n  Active cooldowns by company:")
        for ck, count in sorted(by_company.items()):
            print(f"    {ck:20} : {count} leads in cooldown")

    # Show most recent sends
    if ledger:
        print(f"\n  Last 10 sends:")
        for entry in ledger[-10:]:
            ts = entry.get("timestamp", "?")[:16]
            em = entry.get("email", "?")
            ck = entry.get("company_key", "?")
            seg = entry.get("segment", "?")
            dr = " [DRY]" if entry.get("dry_run") else ""
            print(f"    {ts}  {ck:15} {seg:6} → {em}{dr}")

    print()


def cmd_check_email(email: str):
    """Check if a specific email is clear to contact."""
    ledger = load_ledger()
    clear, reason = is_clear_to_send(email, "any", ledger)
    if clear:
        print(f"\n  [CLEAR] {email} — no active cooldown, safe to contact.\n")
    else:
        print(f"\n  [BLOCKED] {email} — {reason}\n")


def cmd_batch(company_key: str, segment: str, batch_size: int):
    """Request a deconflicted batch of leads."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)

    company = config["companies"].get(company_key)
    if not company:
        print(f"\n[ERROR] Unknown company: {company_key}")
        sys.exit(1)

    # Sync ledger from all company logs first
    synced = sync_ledger_from_logs(config)
    if synced:
        print(f"  Synced {synced} entries from company email logs into ledger.")

    # Load leads from the company's harness
    repo = Path(company["repo"].replace("~", str(Path.home())))
    leads_path = repo / "leads.json"

    if not leads_path.exists():
        print(f"\n[ERROR] No leads.json at {leads_path}")
        sys.exit(1)

    with open(leads_path) as f:
        all_leads = json.load(f)

    # Filter to segment
    seg_registry = config.get("segment_registry", {}).get(segment, {})
    # Get list_names for this segment from the harness's SEGMENT_MAP
    # We'll filter by list_name matching the segment's known lists
    segment_leads = [
        l for l in all_leads
        if l.get("email", "").strip()
    ]

    ledger = load_ledger()
    batch, blocked = get_deconflicted_batch(
        segment_leads, company_key, segment, batch_size, ledger
    )

    print(f"\n{'─'*65}")
    print(f"  DECONFLICTED BATCH — {company['name']} / {segment}")
    print(f"{'─'*65}")
    print(f"  Total leads in pool : {len(segment_leads)}")
    print(f"  Blocked (cooldown)  : {len(blocked)}")
    print(f"  Eligible            : {len(segment_leads) - len(blocked)}")
    print(f"  Batch size          : {len(batch)} (requested {batch_size})")
    print(f"  Randomized          : Yes")
    print()

    if batch:
        print(f"  Batch leads:")
        for i, lead in enumerate(batch, 1):
            name = lead.get("contact_name") or lead.get("first_name", "?")
            co = lead.get("company_name", "?")
            email = lead.get("email", "?")
            print(f"    {i:3}. {name:25} {co:30} {email}")

    if blocked:
        print(f"\n  Blocked leads (sample, first 5):")
        for b in blocked[:5]:
            lead = b["lead"]
            name = lead.get("contact_name") or lead.get("first_name", "?")
            print(f"    {name:25} — {b['reason']}")

    print()


def cmd_purge():
    """Remove ledger entries older than the cooldown window."""
    ledger = load_ledger()
    cutoff = datetime.now(timezone.utc) - timedelta(days=COOLDOWN_DAYS)
    before = len(ledger)

    active = []
    for entry in ledger:
        ts = entry.get("timestamp", "")
        try:
            sent_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if sent_at >= cutoff:
                active.append(entry)
        except (ValueError, AttributeError):
            active.append(entry)  # keep entries we can't parse

    save_ledger(active)
    removed = before - len(active)
    print(f"\n  Purged {removed} expired entries. {len(active)} active entries remain.\n")


def cmd_sync():
    """Sync ledger from all company email logs."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    added = sync_ledger_from_logs(config)
    print(f"\n  Synced {added} new entries into send_ledger.json from company email logs.\n")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Cross-company lead deconfliction for ITAD outreach.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python deconflict.py --status\n"
            "  python deconflict.py --check-email someone@co.com\n"
            "  python deconflict.py --company datatech --segment SEG-1 --batch-size 20\n"
            "  python deconflict.py --sync\n"
            "  python deconflict.py --purge\n"
        ),
    )
    parser.add_argument("--company", help="Company key for batch request")
    parser.add_argument("--segment", help="Segment ID for batch request")
    parser.add_argument("--batch-size", type=int, default=20, help="Max leads in batch (default: 20)")
    parser.add_argument("--check-email", metavar="EMAIL", help="Check cooldown for a specific email")
    parser.add_argument("--status", action="store_true", help="Show deconfliction status")
    parser.add_argument("--purge", action="store_true", help="Remove expired cooldown entries")
    parser.add_argument("--sync", action="store_true", help="Sync ledger from all company email logs")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.check_email:
        cmd_check_email(args.check_email)
    elif args.purge:
        cmd_purge()
    elif args.sync:
        cmd_sync()
    elif args.company and args.segment:
        cmd_batch(args.company, args.segment, args.batch_size)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

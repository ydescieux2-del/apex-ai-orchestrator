#!/usr/bin/env python3
"""
Calendly Link Generator — APEX AI Orchestrator
Generates single-use Calendly scheduling links per prospect and tracks them.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT             = Path(__file__).parent
TRACKER_FILE     = ROOT / "scheduling_tracker.json"
COMPANY_CFG      = ROOT / "company_config.json"

# Default Calendly event type URIs per company — update with real URIs from Calendly dashboard
DEFAULT_EVENT_TYPES = {
    "zs_recycling": "https://api.calendly.com/event_types/ZS_RECYCLING_30MIN",
    "datatech":     "https://api.calendly.com/event_types/DATATECH_30MIN",
}

# Fallback public booking links if single-use creation fails
PUBLIC_BOOKING_LINKS = {
    "zs_recycling": "https://calendly.com/zs-recycling/30min",
    "datatech":     "https://calendly.com/datatechdisposition/30min",
}


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def get_booking_link(email: str, name: str, company_key: str = "zs_recycling") -> dict:
    """
    Returns a scheduling link for the prospect.
    Tries single-use Calendly link first, falls back to public link.

    Returns:
        {
          "email": str,
          "name": str,
          "link": str,
          "type": "single_use" | "public",
          "created_at": str,
          "company": str,
        }
    """
    tracker = load_json(TRACKER_FILE, [])

    # Check if we already have an unused link for this email
    existing = next((t for t in tracker
                     if t.get("email","").lower() == email.lower()
                     and t.get("company") == company_key
                     and not t.get("booked")), None)
    if existing:
        print(f"  ♻️  Reusing existing link for {email}: {existing['link']}")
        return existing

    # Try to generate single-use link via Calendly MCP
    # In MCP context, this would call: create_single_use_scheduling_link(max_event_count=1)
    # For now we log the intent and use the public link
    link_type  = "public"
    link       = PUBLIC_BOOKING_LINKS.get(company_key,
                     "https://calendly.com/zs-recycling/30min")

    # TODO: Replace with actual MCP call:
    # result = mcp__calendly__scheduling_links-create_single_use_scheduling_link(
    #     max_event_count=1,
    #     owner=DEFAULT_EVENT_TYPES[company_key],
    #     owner_type="EventType"
    # )
    # link = result["resource"]["booking_url"]
    # link_type = "single_use"

    record = {
        "email":      email,
        "name":       name,
        "company":    company_key,
        "link":       link,
        "type":       link_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "booked":     False,
        "booked_at":  None,
    }

    tracker.append(record)
    save_json(TRACKER_FILE, tracker)
    print(f"  🔗 Scheduling link for {name} <{email}>: {link}")
    return record


def mark_booked(email: str, company_key: str = "zs_recycling"):
    """Mark a prospect's link as booked (call when Calendly webhook fires)."""
    tracker = load_json(TRACKER_FILE, [])
    changed = 0
    for t in tracker:
        if t.get("email","").lower() == email.lower() and t.get("company") == company_key:
            t["booked"]    = True
            t["booked_at"] = datetime.now(timezone.utc).isoformat()
            changed += 1
    save_json(TRACKER_FILE, tracker)
    if changed:
        print(f"  ✅ Marked {email} as BOOKED in scheduling tracker")
    return changed


def inject_link_into_template(template: str, email: str, name: str,
                               company_key: str = "zs_recycling") -> str:
    """Replace [CALENDLY_LINK] placeholder in an email template."""
    record = get_booking_link(email, name, company_key)
    return template.replace("[CALENDLY_LINK]", record["link"])


def show_status():
    tracker = load_json(TRACKER_FILE, [])
    total   = len(tracker)
    booked  = sum(1 for t in tracker if t.get("booked"))
    pending = total - booked

    print(f"\n📅 Scheduling Tracker: {total} links generated")
    print(f"   Booked : {booked}")
    print(f"   Pending: {pending}")

    if tracker:
        print(f"\n   Recent links:")
        for t in tracker[-5:]:
            status = "✅ BOOKED" if t.get("booked") else "⏳ pending"
            print(f"   {t['name']:<25} {t['email']:<35} {status}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Calendly Link Manager")
    parser.add_argument("--create",  nargs=2, metavar=("EMAIL", "NAME"),
                        help="Generate a scheduling link for EMAIL 'Full Name'")
    parser.add_argument("--booked",  metavar="EMAIL",
                        help="Mark EMAIL as having booked a meeting")
    parser.add_argument("--company", default="zs_recycling",
                        choices=list(DEFAULT_EVENT_TYPES.keys()),
                        help="Company context (default: zs_recycling)")
    parser.add_argument("--status",  action="store_true",
                        help="Show tracker summary")
    args = parser.parse_args()

    if args.create:
        email, name = args.create
        get_booking_link(email, name, args.company)

    elif args.booked:
        mark_booked(args.booked, args.company)

    elif args.status:
        show_status()

    else:
        parser.print_help()

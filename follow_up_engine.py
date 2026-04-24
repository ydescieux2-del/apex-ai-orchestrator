#!/usr/bin/env python3
"""
Follow-Up Sequence Engine — DataTech Disposition / ZS Recycling
Sends multi-touch follow-ups on Day 3, 7, 14 from original send.
Respects deconfliction, reply detection, and opt-out rules.
"""
import json
import os
import sys
import time
import random
import smtplib
import ssl
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

ROOT          = Path(__file__).parent
FOLLOWUP_LOG  = ROOT / "follow_up_log.json"
COMPANY_CFG   = ROOT / "company_config.json"

# Orchestrator paths
ORCH_ROOT      = Path(__file__).parent
INBOX_LEDGER   = ORCH_ROOT / "inbox_ledger.json"
SEND_LEDGER    = ORCH_ROOT / "send_ledger.json"

# Follow-up schedule (days after initial send)
FOLLOWUP_DAYS = [3, 7, 14]

# Delay between sends (seconds)
MIN_DELAY = 90
MAX_DELAY = 240

# ── Follow-up templates by day ────────────────────────────────────────────────

TEMPLATES = {
    3: {
        "subject": "Quick follow-up — IT asset pickup for {company}",
        "body": """Hi {first_name},

Just following up on my note from earlier this week about IT asset disposition for {company}.

We specialize in compliant e-waste recycling and data destruction — zero landfill, full chain-of-custody, and certificates of destruction for every job.

If timing isn't right, no worries at all — happy to reconnect whenever it makes sense.

Best,
{sender_name}"""
    },
    7: {
        "subject": "Are you planning any IT refresh in Q2? — {company}",
        "body": """Hi {first_name},

Circling back one more time. I wanted to ask specifically: is {company} planning any IT equipment refresh or decommissioning in the next 90 days?

We've helped similar organizations in your industry clear out:
• Retired laptops, desktops, servers
• End-of-life networking gear
• Storage devices (with certified data destruction)

Happy to give you a quick quote — no commitment. Just reply and I'll set something up.

Best,
{sender_name}"""
    },
    14: {
        "subject": "Last note — e-waste and data disposition for {company}",
        "body": """Hi {first_name},

I'll keep this short — last outreach from me on this topic.

If {company} ever has a need for compliant IT asset disposal, data destruction, or e-waste recycling, I'd love to be your first call. We make the process fast, documented, and cost-effective.

Feel free to reach out anytime:
📧 {sender_email}

Thanks for your time.

{sender_name}"""
    }
}


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def has_replied(email: str) -> bool:
    """Check if prospect has sent ANY reply (suppresses all follow-ups)."""
    ledger = load_json(INBOX_LEDGER, [])
    return any(e.get("from_email","").lower() == email.lower() for e in ledger)


def is_opted_out(email: str) -> bool:
    """Check opt-out across the send ledger."""
    ledger = load_json(SEND_LEDGER, [])
    return any(e.get("email","").lower() == email.lower() and e.get("opted_out")
               for e in ledger)


def get_initial_send_date(email: str, email_log: list[dict] = None) -> datetime | None:
    """Find the earliest send date for this email in the log."""
    log = email_log if email_log is not None else []
    dates = []
    for entry in log:
        addr = (entry.get("to_email") or entry.get("contact_email") or entry.get("email") or "").lower()
        if addr != email.lower():
            continue
        ts = entry.get("sent_at") or entry.get("timestamp") or entry.get("date_created")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dates.append(dt)
            except Exception:
                pass
    return min(dates) if dates else None


def get_followup_history(email: str) -> list[int]:
    """Returns list of follow-up days already sent to this email."""
    log = load_json(FOLLOWUP_LOG, [])
    return [e["sequence_day"] for e in log
            if e.get("email","").lower() == email.lower()]


def get_due_followups(leads: list, email_log: list[dict] = None) -> list[dict]:
    """
    Returns leads that are due for a follow-up today.
    Each entry: {lead, day}
    """
    due   = []
    now   = datetime.now(timezone.utc)

    for lead in leads:
        email = (lead.get("email") or "").lower().strip()
        if not email:
            continue
        if is_opted_out(email):
            continue
        if has_replied(email):
            continue

        initial = get_initial_send_date(email, email_log)
        if not initial:
            continue

        days_since = (now - initial).days
        already_sent = get_followup_history(email)

        for day in FOLLOWUP_DAYS:
            if day in already_sent:
                continue
            if days_since >= day:
                due.append({"lead": lead, "day": day})
                break  # only one follow-up per run per lead

    return due


def render_template(day: int, lead: dict, sender_name: str, sender_email: str) -> dict:
    tmpl    = TEMPLATES[day]
    first   = lead.get("first_name") or lead.get("contact_name", "").split()[0] or "there"
    company = lead.get("company_name", "your organization")

    subject = tmpl["subject"].format(first_name=first, company=company,
                                      sender_name=sender_name, sender_email=sender_email)
    body    = tmpl["body"].format(first_name=first, company=company,
                                   sender_name=sender_name, sender_email=sender_email)
    return {"subject": subject, "body": body}


def send_followup_email(lead: dict, day: int, smtp_user: str, smtp_pass: str,
                         sender_name: str, dry_run: bool = False) -> bool:
    email = (lead.get("email") or "").strip()
    if not email:
        return False

    rendered = render_template(day, lead, sender_name, smtp_user)

    if dry_run:
        print(f"  [DRY RUN] Day {day} → {email}: {rendered['subject']}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = rendered["subject"]
        msg["From"]    = f"{sender_name} <{smtp_user}>"
        msg["To"]      = email
        msg.attach(MIMEText(rendered["body"], "plain"))

        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, [email], msg.as_string())

        print(f"  ✅ Day {day} sent → {email}")
        return True

    except Exception as exc:
        print(f"  ❌ Failed to send to {email}: {exc}")
        return False


def log_followup(lead: dict, day: int, success: bool):
    log = load_json(FOLLOWUP_LOG, [])
    log.append({
        "lead_id":      lead.get("id", ""),
        "email":        (lead.get("email") or "").lower(),
        "company":      lead.get("company_name", ""),
        "sequence_day": day,
        "sent_at":      datetime.now(timezone.utc).isoformat(),
        "success":      success,
    })
    save_json(FOLLOWUP_LOG, log)


def load_all_company_data(company_filter: str = None) -> tuple[list[dict], list[dict], dict]:
    """Load leads and email logs from all active company harnesses.

    Returns (all_leads, all_email_log_entries, company_sender_map).
    company_sender_map: {company_key: {smtp_user, smtp_pass, sender_name}}
    """
    cfg = load_json(COMPANY_CFG, {})
    all_leads = []
    all_log = []
    sender_map = {}

    for key, co in cfg.get("companies", {}).items():
        if co.get("status") not in ("active", "setup"):
            continue
        if company_filter and key != company_filter:
            continue

        repo = Path(co["repo"].replace("~", str(Path.home())))
        leads_file = repo / "leads.json"
        log_file = repo / "email_log.json"

        if leads_file.exists():
            leads = load_json(leads_file, [])
            # Tag each lead with its company_key for routing
            for l in leads:
                l["_company_key"] = key
                l["_company_name"] = co["name"]
            all_leads.extend(leads)

        if log_file.exists():
            all_log.extend(load_json(log_file, []))

        # Load company-specific .env for credentials
        env_file = repo / ".env"
        if env_file.exists():
            creds = {}
            for line in env_file.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    creds[k.strip()] = v.strip()
            sender_map[key] = {
                "smtp_user": creds.get("EMAIL_ADDRESS", ""),
                "smtp_pass": creds.get("EMAIL_APP_PASSWORD", ""),
                "sender_name": creds.get("SENDER_NAME", co.get("contact", "Outreach Team")),
            }

    return all_leads, all_log, sender_map


def run_due_followups(dry_run: bool = False, company: str = None):
    # Load credentials from .env as fallback
    from dotenv import load_dotenv
    load_dotenv()
    smtp_user   = os.getenv("GMAIL_USER", "")
    smtp_pass   = os.getenv("GMAIL_APP_PASSWORD", "")
    sender_name = os.getenv("SENDER_NAME", "Outreach Team")

    # Load leads and logs from all active companies
    leads, email_log, sender_map = load_all_company_data(company_filter=company)
    due = get_due_followups(leads, email_log)

    company_label = f" ({company})" if company else " (all companies)"
    print(f"\n📬 Follow-Up Engine — {datetime.now().strftime('%Y-%m-%d %H:%M')}{company_label}")
    print(f"   Mode    : {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"   Leads   : {len(leads)} total")
    print(f"   Due     : {len(due)} follow-up(s) today")

    if not due:
        print("   ✅ Nothing due — check back tomorrow.")
        return

    # Shuffle order
    random.shuffle(due)

    sent = skipped = failed = 0
    for item in due:
        lead, day = item["lead"], item["day"]
        print(f"\n  → Day {day}: {lead.get('company_name','')} <{lead.get('email','')}>")

        success = send_followup_email(lead, day, smtp_user, smtp_pass,
                                       sender_name, dry_run=dry_run)
        if success:
            sent += 1
            log_followup(lead, day, True)
        else:
            failed += 1
            log_followup(lead, day, False)

        # Delay between sends
        if not dry_run and item != due[-1]:
            delay = random.randint(MIN_DELAY, MAX_DELAY)
            print(f"  ⏳ Waiting {delay}s before next send...")
            time.sleep(delay)

    print(f"\n📊 Follow-Up Results:")
    print(f"   Sent   : {sent}")
    print(f"   Failed : {failed}")
    print(f"   Total  : {sent + failed}")


def show_status(company: str = None):
    log = load_json(FOLLOWUP_LOG, [])
    leads, email_log, _ = load_all_company_data(company_filter=company)

    by_day = {}
    for e in log:
        d = e.get("sequence_day")
        by_day[d] = by_day.get(d, 0) + 1

    company_label = f" ({company})" if company else " (all companies)"
    print(f"\n📊 Follow-Up Status{company_label}")
    print(f"   Total leads: {len(leads)}")
    print(f"   Follow-ups sent: {len(log)}")
    for d in sorted(by_day):
        print(f"   Day {d:2d}: {by_day[d]} sent")

    # Show what's due
    due = get_due_followups(leads, email_log)
    print(f"\n   Currently due: {len(due)} follow-up(s)")
    for item in due[:5]:
        l = item["lead"]
        print(f"   Day {item['day']}: {l.get('company_name','')} <{l.get('email','')}>")
    if len(due) > 5:
        print(f"   ... and {len(due)-5} more")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Cross-company Follow-Up Sequence Engine",
        epilog=(
            "Examples:\n"
            "  python follow_up_engine.py --status\n"
            "  python follow_up_engine.py --status --company zs_recycling\n"
            "  python follow_up_engine.py --dry-run\n"
            "  python follow_up_engine.py --dry-run --company datatech\n"
            "  python follow_up_engine.py --run-due --company zs_recycling\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--run-due",  action="store_true", help="Send all due follow-ups")
    parser.add_argument("--dry-run",  action="store_true", help="Preview without sending")
    parser.add_argument("--status",   action="store_true", help="Show follow-up stats")
    parser.add_argument("--company",  metavar="KEY",       help="Filter to a single company (datatech, zs_recycling)")
    args = parser.parse_args()

    if args.status:
        show_status(company=args.company)
    elif args.run_due or args.dry_run:
        run_due_followups(dry_run=args.dry_run, company=args.company)
    else:
        parser.print_help()

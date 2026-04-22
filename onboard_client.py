#!/usr/bin/env python3
"""
onboard_client.py — Apex AI Orchestrator: New Client Auto-Onboarding

Creates a client folder, fills in config, initializes data files,
generates a Claude-drafted welcome email, and prints a next-steps checklist.

Usage:
    python3 onboard_client.py --name "Company Name" --industry "ITAD" \
        --contact "email@co.com" --rate 1500

Requirements:
    pip install anthropic pyyaml
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required. Run: pip install pyyaml")
    sys.exit(1)

try:
    import anthropic
except ImportError:
    print("ERROR: Anthropic SDK required. Run: pip install anthropic")
    sys.exit(1)

# ─── Paths ─────────────────────────────────────────────────────────────────

SCRIPT_DIR   = Path(__file__).parent.resolve()
CLIENTS_DIR  = SCRIPT_DIR / "clients"
TEMPLATE_SRC = SCRIPT_DIR / "client_config_template.yaml"


# ─── Helpers ───────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert company name to a safe directory slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def print_section(title: str) -> None:
    width = 60
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}")


def print_ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def print_info(msg: str) -> None:
    print(f"  [--]  {msg}")


# ─── Step 1 — Create client folder ─────────────────────────────────────────

def create_client_folder(slug: str) -> Path:
    client_dir = CLIENTS_DIR / slug
    if client_dir.exists():
        print(f"  [WARN] Client folder already exists: {client_dir}")
        print(f"         Continuing — existing files will NOT be overwritten.")
    else:
        client_dir.mkdir(parents=True, exist_ok=True)
        print_ok(f"Created: {client_dir}")
    return client_dir


# ─── Step 2 — Write filled config ──────────────────────────────────────────

def write_config(client_dir: Path, args: argparse.Namespace, slug: str) -> None:
    config_dest = client_dir / "client_config.yaml"
    if config_dest.exists():
        print_info(f"Config already exists — skipping: {config_dest.name}")
        return

    # Load template if it exists, otherwise write minimal config
    if TEMPLATE_SRC.exists():
        with open(TEMPLATE_SRC) as f:
            template_text = f.read()
        # We write a clean filled config alongside the template reference

    today = date.today().isoformat()
    config = {
        "client_name":    args.name,
        "client_slug":    slug,
        "industry":       args.industry,
        "target_market":  args.market,
        "contact_email":  args.contact,
        "monthly_rate":   args.rate,
        "start_date":     today,
        "status":         "active",
        "onboarded_by":   "onboard_client.py",
        "template_ref":   str(TEMPLATE_SRC),
    }

    with open(config_dest, "w") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print_ok(f"Wrote config: {config_dest.name}")


# ─── Step 3 — Initialize data files ────────────────────────────────────────

def init_data_files(client_dir: Path) -> None:
    files = {
        "leads.json":          [],
        "send_log.json":       [],
        "campaign_state.json": {
            "status":          "initialized",
            "active_segments": [],
            "emails_sent":     0,
            "last_send":       None,
            "created_at":      date.today().isoformat(),
        },
    }

    for filename, initial_value in files.items():
        dest = client_dir / filename
        if dest.exists():
            print_info(f"Already exists — skipping: {filename}")
        else:
            with open(dest, "w") as f:
                json.dump(initial_value, f, indent=2)
            print_ok(f"Created: {filename}")


# ─── Step 4 — Generate welcome email via Claude API ────────────────────────

def generate_welcome_email(client_dir: Path, args: argparse.Namespace) -> None:
    dest = client_dir / "welcome_email.txt"
    if dest.exists():
        print_info(f"Welcome email already exists — skipping.")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [WARN] ANTHROPIC_API_KEY not set — skipping AI email generation.")
        _write_fallback_email(dest, args)
        return

    print_info("Generating welcome email via Claude API...")

    prompt = f"""Write a professional, warm onboarding email from Von Descieux at Apex AI Consulting
to a new client. The email should:

- Open with genuine congratulations and a clear statement that their outreach campaign is being set up now
- Be confident, direct, and human — not corporate-robotic
- Briefly describe the 3 things that happen in the first week:
  (1) lead sourcing and verification, (2) campaign configuration and test send, (3) live campaign launch
- Mention the monthly rate of ${args.rate}/month and that they're locked in at the founding client rate
- End with Von's direct contact info placeholder and a strong closing line
- Tone: peer-to-peer executive communication. No buzzword soup.
- Length: ~200–250 words. No subject line needed.

Client details:
- Company: {args.name}
- Industry: {args.industry}
- Contact email: {args.contact}
- Monthly rate: ${args.rate}
- Start date: {date.today().isoformat()}
"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        email_body = message.content[0].text.strip()

        subject = f"Welcome to Apex AI — {args.name} campaign is live"
        full_email = f"To: {args.contact}\nSubject: {subject}\n\n{email_body}"

        with open(dest, "w") as f:
            f.write(full_email)

        print_ok(f"Welcome email saved: {dest.name}")
        print()
        print("  ┌─ DRAFT PREVIEW ─────────────────────────────────────────")
        for line in full_email.splitlines():
            print(f"  │ {line}")
        print("  └─────────────────────────────────────────────────────────")

    except Exception as e:
        print(f"  [WARN] Claude API error: {e}")
        print(f"         Falling back to template email.")
        _write_fallback_email(dest, args)


def _write_fallback_email(dest: Path, args: argparse.Namespace) -> None:
    today = date.today().strftime("%B %d, %Y")
    body = f"""To: {args.contact}
Subject: Welcome to Apex AI — {args.name} campaign is live

Hi,

Congratulations — {args.name} is officially onboarded with Apex AI Consulting as of {today}.

Here's what happens in your first week:

1. Lead sourcing and verification — we build and verify your first prospect list against your ICP.
2. Campaign configuration and test send — messaging is configured, tested, and reviewed before going live.
3. Live campaign launch — first emails go out, and you start seeing replies.

Your monthly rate is locked at ${args.rate}/month as a founding Apex client. That rate holds.

I'll be in touch with your first campaign report within 5 business days. If anything comes up before then, reply directly to this email.

Let's build something.

— Von Descieux
Apex AI Consulting
ydescieux@msn.com
"""
    with open(dest, "w") as f:
        f.write(body)
    print_ok(f"Fallback welcome email saved: {dest.name}")


# ─── Step 5 — Print checklist ───────────────────────────────────────────────

def print_checklist(client_dir: Path, args: argparse.Namespace, slug: str) -> None:
    print_section("NEXT STEPS CHECKLIST")
    steps = [
        f"[ ] Source leads for {args.name} — run: python3 lead_sourcer.py --company {slug}",
        f"[ ] Verify leads          — run: python3 lead_verifier.py --company {slug}",
        f"[ ] Configure segments    — edit: clients/{slug}/client_config.yaml",
        f"[ ] Review & send welcome — file: clients/{slug}/welcome_email.txt",
        f"[ ] Set up campaign       — run: python3 orchestrate.py --company {slug} --dry-run",
        f"[ ] Go live               — run: python3 orchestrate.py --company {slug} --live",
        f"[ ] Register in company_config.json if not already listed",
    ]
    for step in steps:
        print(f"  {step}")

    print()
    print(f"  Client folder: {client_dir}")
    print()


# ─── Main ───────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apex AI: Onboard a new outreach client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 onboard_client.py --name "Acme Corp" --industry "ITAD" \\
      --contact "john@acme.com" --rate 1500

  python3 onboard_client.py --name "Test Client" --industry "Technology" \\
      --contact "ydescieux@msn.com" --rate 1500
""",
    )
    parser.add_argument("--name",     required=True, help="Company display name")
    parser.add_argument("--industry", required=True, help="Industry vertical (e.g. ITAD, Healthcare, Technology)")
    parser.add_argument("--contact",  required=True, help="Primary contact email")
    parser.add_argument("--rate",     required=True, type=int, help="Monthly retainer in USD (e.g. 1500)")
    parser.add_argument("--market",   default="Southern California SMBs",
                        help="Target market description (default: 'Southern California SMBs')")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slug = slugify(args.name)

    print_section(f"APEX AI — ONBOARDING: {args.name.upper()}")
    print_info(f"Slug:     {slug}")
    print_info(f"Industry: {args.industry}")
    print_info(f"Contact:  {args.contact}")
    print_info(f"Rate:     ${args.rate:,}/month")

    print_section("Step 1 — Create client folder")
    client_dir = create_client_folder(slug)

    print_section("Step 2 — Write client config")
    write_config(client_dir, args, slug)

    print_section("Step 3 — Initialize data files")
    init_data_files(client_dir)

    print_section("Step 4 — Generate welcome email")
    generate_welcome_email(client_dir, args)

    print_checklist(client_dir, args, slug)

    print("  Onboarding complete.\n")


if __name__ == "__main__":
    main()

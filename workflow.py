#!/usr/bin/env python3
"""
workflow.py — Campaign workflow engine for Apex AI outreach orchestrator.

Adds preflight checks, workflow pipelines, campaign state tracking,
and readiness dashboards on top of orchestrate.py.

Usage:
  python workflow.py readiness                              # What's ready, what's blocked
  python workflow.py preflight datatech SEG-1               # Run all checks before send
  python workflow.py pipeline  datatech SEG-1               # Full pipeline: preflight → dry-run → gate → send
  python workflow.py dry-run   datatech SEG-1               # Dry run + record result
  python workflow.py approve   datatech SEG-1               # Mark dry run as reviewed/approved
  python workflow.py send      datatech SEG-1               # Live send (only if approved)
  python workflow.py history                                # Show all campaign events
  python workflow.py batch-dry-run                          # Dry run all eligible segments
  python workflow.py reset     datatech SEG-1               # Reset campaign state for a segment
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

CONFIG_PATH  = Path(__file__).parent / "company_config.json"
STATE_PATH   = Path(__file__).parent / "campaign_state.json"
ORCHESTRATOR = Path(__file__).parent / "orchestrate.py"

# ──────────────────────────────────────────────
# State management
# ──────────────────────────────────────────────

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"campaigns": {}, "history": []}


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def campaign_key(company, segment):
    return f"{company}:{segment}"


def get_campaign(state, company, segment):
    key = campaign_key(company, segment)
    if key not in state["campaigns"]:
        state["campaigns"][key] = {
            "company": company,
            "segment": segment,
            "preflight_passed": False,
            "preflight_errors": [],
            "dry_run_completed": False,
            "dry_run_timestamp": None,
            "dry_run_approved": False,
            "approved_by": None,
            "approved_timestamp": None,
            "sent": False,
            "sent_timestamp": None,
            "send_result": None,
        }
    return state["campaigns"][key]


def record_event(state, company, segment, event_type, detail=None):
    state["history"].append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "company": company,
        "segment": segment,
        "event": event_type,
        "detail": detail,
    })


# ──────────────────────────────────────────────
# Preflight checks
# ──────────────────────────────────────────────

def run_preflight(config, company_key, segment_id, verbose=True):
    """Run all preflight checks. Returns (passed: bool, errors: list[str])."""
    errors = []
    warnings = []
    company = config["companies"].get(company_key)

    if verbose:
        print(f"\n{'─'*60}")
        print(f"  PREFLIGHT CHECK: {company_key} / {segment_id}")
        print(f"{'─'*60}\n")

    # 1. Company exists
    if not company:
        errors.append(f"Unknown company: {company_key}")
        if verbose:
            print(f"  ✗ Company '{company_key}' not found in config")
        return False, errors

    if verbose:
        print(f"  ✓ Company found: {company['name']}")

    # 2. Company status
    if company["status"] == "pending":
        errors.append(f"{company['name']} status is 'pending' — not ready for sends")
        if verbose:
            print(f"  ✗ Company status: {company['status']} (must be 'active' or 'setup')")
    elif company["status"] == "setup":
        warnings.append(f"{company['name']} is still in setup — verify credentials before live send")
        if verbose:
            print(f"  ⚠ Company status: {company['status']} (dry run OK, verify before live send)")
    else:
        if verbose:
            print(f"  ✓ Company status: {company['status']}")

    # 3. Segment ownership
    if segment_id not in company["owned_segments"]:
        actual_owner = config["segment_registry"].get(segment_id, {}).get("owner", "unknown")
        actual_name = config["companies"].get(actual_owner, {}).get("name", actual_owner)
        errors.append(f"Ownership violation: {company['name']} does not own {segment_id} (owned by {actual_name})")
        if verbose:
            print(f"  ✗ Segment ownership: {segment_id} belongs to {actual_name}, not {company['name']}")
    else:
        if verbose:
            print(f"  ✓ Segment ownership: {company['name']} owns {segment_id}")

    # 4. Segment exists in registry
    seg = config["segment_registry"].get(segment_id)
    if not seg:
        errors.append(f"Segment {segment_id} not found in registry")
        if verbose:
            print(f"  ✗ Segment {segment_id} not in registry")
    else:
        if verbose:
            lead_info = f"{seg['lead_count']} leads" if seg['lead_count'] != 'TBD' else "TBD leads"
            print(f"  ✓ Segment registered: {seg['name']} ({lead_info})")

        # 5. Lead count check
        if seg["lead_count"] == "TBD":
            warnings.append(f"{segment_id} lead count is TBD — leads may not be loaded yet")
            if verbose:
                print(f"  ⚠ Lead count is TBD — verify leads are loaded before sending")

    # 6. Email account configured
    if not company.get("email_account") or company["email_account"].startswith("TBD"):
        errors.append(f"Email account not configured for {company['name']}")
        if verbose:
            print(f"  ✗ Email account: {company['email_account']} (not ready)")
    else:
        if verbose:
            print(f"  ✓ Email account: {company['email_account']}")

    # 7. Harness directory exists
    repo_path = Path(company["repo"].replace("~", str(Path.home())))
    if not repo_path.exists():
        errors.append(f"Harness directory not found: {repo_path}")
        if verbose:
            print(f"  ✗ Harness directory: {repo_path} (not found)")
    else:
        if verbose:
            print(f"  ✓ Harness directory: {repo_path}")

        # 8. send_emails.py exists
        send_script = repo_path / "send_emails.py"
        if not send_script.exists():
            errors.append(f"send_emails.py not found in {repo_path}")
            if verbose:
                print(f"  ✗ send_emails.py not found in harness")
        else:
            if verbose:
                print(f"  ✓ send_emails.py present")

    # 9. Company-specific notes/warnings
    notes = company.get("notes", "")
    if "pending" in notes.lower() or "do not send" in notes.lower():
        warnings.append(f"Config note: {notes}")
        if verbose:
            print(f"  ⚠ Note: {notes}")

    # Summary
    passed = len(errors) == 0
    if verbose:
        print()
        if warnings:
            for w in warnings:
                print(f"  ⚠ {w}")
        if passed:
            print(f"\n  ✓ PREFLIGHT PASSED ({len(warnings)} warning(s))")
        else:
            print(f"\n  ✗ PREFLIGHT FAILED — {len(errors)} error(s):")
            for e in errors:
                print(f"    • {e}")
        print()

    return passed, errors


# ──────────────────────────────────────────────
# Workflow actions
# ──────────────────────────────────────────────

def action_preflight(config, company, segment):
    state = load_state()
    campaign = get_campaign(state, company, segment)
    passed, errors = run_preflight(config, company, segment)

    campaign["preflight_passed"] = passed
    campaign["preflight_errors"] = errors
    record_event(state, company, segment, "preflight", "passed" if passed else f"failed: {errors}")
    save_state(state)
    return passed


def action_dry_run(config, company, segment):
    state = load_state()
    campaign = get_campaign(state, company, segment)

    # Must pass preflight first
    if not campaign["preflight_passed"]:
        print(f"\n  [BLOCKED] Preflight not passed for {company}/{segment}.")
        print(f"  Run: python workflow.py preflight {company} {segment}\n")
        return False

    print(f"\n  Running dry run via orchestrate.py...")
    result = subprocess.run(
        ["python3", str(ORCHESTRATOR), "--company", company, "--segment", segment, "--dry-run"],
        capture_output=False,
    )

    success = result.returncode == 0
    campaign["dry_run_completed"] = success
    campaign["dry_run_timestamp"] = datetime.utcnow().isoformat() + "Z"
    record_event(state, company, segment, "dry_run", "success" if success else "failed")
    save_state(state)

    if success:
        print(f"\n  ✓ Dry run completed. Next step:")
        print(f"    python workflow.py approve {company} {segment}\n")
    else:
        print(f"\n  ✗ Dry run failed. Check output above.\n")

    return success


def action_approve(config, company, segment):
    state = load_state()
    campaign = get_campaign(state, company, segment)

    if not campaign["dry_run_completed"]:
        print(f"\n  [BLOCKED] Dry run not completed for {company}/{segment}.")
        print(f"  Run: python workflow.py dry-run {company} {segment}\n")
        return False

    campaign["dry_run_approved"] = True
    campaign["approved_timestamp"] = datetime.utcnow().isoformat() + "Z"
    record_event(state, company, segment, "approved", "dry run reviewed and approved")
    save_state(state)

    print(f"\n  ✓ Dry run approved for {company}/{segment}.")
    print(f"  Ready for live send:")
    print(f"    python workflow.py send {company} {segment}\n")
    return True


def action_send(config, company, segment):
    state = load_state()
    campaign = get_campaign(state, company, segment)

    # Enforce full pipeline
    if not campaign["preflight_passed"]:
        print(f"\n  [BLOCKED] Preflight not passed. Run preflight first.\n")
        return False
    if not campaign["dry_run_completed"]:
        print(f"\n  [BLOCKED] Dry run not completed. Run dry-run first.\n")
        return False
    if not campaign["dry_run_approved"]:
        print(f"\n  [BLOCKED] Dry run not approved. Run approve first.\n")
        return False
    if campaign["sent"]:
        print(f"\n  [BLOCKED] Already sent on {campaign['sent_timestamp']}.")
        print(f"  Run: python workflow.py reset {company} {segment}  to re-enable.\n")
        return False

    # Re-run preflight before live send (conditions may have changed)
    print(f"  Re-running preflight before live send...")
    passed, errors = run_preflight(config, company, segment, verbose=False)
    if not passed:
        print(f"\n  [BLOCKED] Preflight no longer passes:")
        for e in errors:
            print(f"    • {e}")
        print(f"\n  Fix issues and re-run: python workflow.py preflight {company} {segment}\n")
        campaign["preflight_passed"] = False
        campaign["preflight_errors"] = errors
        save_state(state)
        return False

    print(f"\n  ✓ Preflight re-verified. Executing live send...\n")

    result = subprocess.run(
        ["python3", str(ORCHESTRATOR), "--company", company, "--segment", segment],
        capture_output=False,
    )

    success = result.returncode == 0
    campaign["sent"] = success
    campaign["sent_timestamp"] = datetime.utcnow().isoformat() + "Z"
    campaign["send_result"] = "success" if success else "failed"
    record_event(state, company, segment, "live_send", "success" if success else "failed")
    save_state(state)

    return success


def action_pipeline(config, company, segment):
    """Full pipeline: preflight → dry run → approval gate → send."""
    print(f"\n{'═'*60}")
    print(f"  FULL PIPELINE: {company} / {segment}")
    print(f"{'═'*60}")

    # Step 1: Preflight
    print(f"\n  ── Step 1/4: Preflight ──")
    if not action_preflight(config, company, segment):
        print(f"  Pipeline stopped at preflight.\n")
        return False

    # Step 2: Dry run
    print(f"  ── Step 2/4: Dry Run ──")
    if not action_dry_run(config, company, segment):
        print(f"  Pipeline stopped at dry run.\n")
        return False

    # Step 3: Approval gate (requires human)
    print(f"  ── Step 3/4: Approval Gate ──")
    print(f"\n  Pipeline paused — human review required.")
    print(f"  Review the dry run output above, then run:")
    print(f"    python workflow.py approve {company} {segment}")
    print(f"    python workflow.py send {company} {segment}")
    print()
    return True


def action_reset(state, company, segment):
    key = campaign_key(company, segment)
    if key in state["campaigns"]:
        del state["campaigns"][key]
        record_event(state, company, segment, "reset", "campaign state cleared")
        save_state(state)
        print(f"\n  ✓ Campaign state reset for {company}/{segment}.\n")
    else:
        print(f"\n  No campaign state found for {company}/{segment}.\n")


# ──────────────────────────────────────────────
# Readiness dashboard
# ──────────────────────────────────────────────

def show_readiness(config):
    state = load_state()

    print(f"\n{'═'*60}")
    print(f"  CAMPAIGN READINESS DASHBOARD")
    print(f"{'═'*60}\n")

    for co_key, company in config["companies"].items():
        status_icon = {"active": "●", "setup": "◎", "pending": "○"}.get(company["status"], "?")
        print(f"  {status_icon} {company['name']}  [{company['status'].upper()}]")

        for seg_id in company["owned_segments"]:
            seg = config["segment_registry"].get(seg_id, {})
            key = campaign_key(co_key, seg_id)
            campaign = state["campaigns"].get(key)

            lead_info = seg.get("lead_count", "?")
            seg_name = seg.get("name", "Unknown")

            # Determine blockers
            blockers = []
            passed, errors = run_preflight(config, co_key, seg_id, verbose=False)
            if not passed:
                blockers = errors

            # Determine pipeline stage
            if campaign and campaign.get("sent"):
                stage = "SENT"
                icon = "✓"
            elif campaign and campaign.get("dry_run_approved"):
                stage = "APPROVED → ready to send"
                icon = "▶"
            elif campaign and campaign.get("dry_run_completed"):
                stage = "DRY RUN DONE → needs approval"
                icon = "◆"
            elif campaign and campaign.get("preflight_passed"):
                stage = "PREFLIGHT OK → needs dry run"
                icon = "◇"
            elif blockers:
                stage = "BLOCKED"
                icon = "✗"
            else:
                stage = "NOT STARTED"
                icon = "·"

            print(f"    {icon} {seg_id}: {seg_name} ({lead_info} leads)")
            print(f"      Stage: {stage}")

            if blockers:
                for b in blockers:
                    print(f"      ✗ {b}")

            # Show next action
            if stage == "BLOCKED":
                print(f"      → Fix blockers above")
            elif stage == "NOT STARTED":
                print(f"      → python workflow.py preflight {co_key} {seg_id}")
            elif "PREFLIGHT OK" in stage:
                print(f"      → python workflow.py dry-run {co_key} {seg_id}")
            elif "DRY RUN DONE" in stage:
                print(f"      → python workflow.py approve {co_key} {seg_id}")
            elif "APPROVED" in stage:
                print(f"      → python workflow.py send {co_key} {seg_id}")
            print()

    # Global rules reminder
    rules = config.get("global_rules", {})
    print(f"  {'─'*50}")
    print(f"  Pipeline: preflight → dry-run → approve → send")
    print(f"  Send delay: {rules.get('min_delay_between_sends_seconds')}–{rules.get('max_delay_between_sends_seconds')}s")
    print(f"  ZeroBounce required: {rules.get('zerobounce_verify_before_large_send', True)}")
    print()


def show_history():
    state = load_state()
    history = state.get("history", [])

    print(f"\n{'═'*60}")
    print(f"  CAMPAIGN HISTORY")
    print(f"{'═'*60}\n")

    if not history:
        print(f"  No events recorded yet.\n")
        return

    for event in history:
        ts = event["timestamp"][:19].replace("T", " ")
        print(f"  [{ts}] {event['company']}/{event['segment']}: {event['event']}")
        if event.get("detail"):
            detail = event["detail"]
            if len(str(detail)) > 80:
                detail = str(detail)[:80] + "..."
            print(f"    {detail}")
    print()


def action_batch_dry_run(config):
    """Dry run all segments that have passed preflight but not yet been dry-run."""
    state = load_state()
    eligible = []

    for co_key, company in config["companies"].items():
        for seg_id in company["owned_segments"]:
            key = campaign_key(co_key, seg_id)
            campaign = state["campaigns"].get(key)

            # Must have passed preflight, not yet dry-run
            if campaign and campaign.get("preflight_passed") and not campaign.get("dry_run_completed"):
                eligible.append((co_key, seg_id))

            # Or: auto-preflight and dry-run if eligible
            if not campaign:
                passed, _ = run_preflight(config, co_key, seg_id, verbose=False)
                if passed:
                    # Record preflight
                    campaign = get_campaign(state, co_key, seg_id)
                    campaign["preflight_passed"] = True
                    record_event(state, co_key, seg_id, "preflight", "passed (batch)")
                    eligible.append((co_key, seg_id))

    save_state(state)

    if not eligible:
        print(f"\n  No segments eligible for batch dry run.")
        print(f"  Run 'python workflow.py readiness' to see what's blocking.\n")
        return

    print(f"\n  Batch dry run: {len(eligible)} segment(s) eligible\n")
    for co_key, seg_id in eligible:
        print(f"  {'─'*40}")
        action_dry_run(config, co_key, seg_id)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Campaign workflow engine for Apex AI outreach.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Commands:\n"
            "  readiness                        Show what's ready, what's blocked\n"
            "  preflight  <company> <segment>   Run all pre-send checks\n"
            "  dry-run    <company> <segment>   Execute dry run + record result\n"
            "  approve    <company> <segment>   Mark dry run as reviewed\n"
            "  send       <company> <segment>   Live send (requires full pipeline)\n"
            "  pipeline   <company> <segment>   Full pipeline: preflight → dry-run → gate\n"
            "  history                          Show all campaign events\n"
            "  batch-dry-run                    Dry run all eligible segments\n"
            "  reset      <company> <segment>   Reset campaign state\n"
        ),
    )
    parser.add_argument("command", help="Workflow command")
    parser.add_argument("company", nargs="?", help="Company key")
    parser.add_argument("segment", nargs="?", help="Segment ID")
    args = parser.parse_args()

    config = load_config()
    cmd = args.command.lower()

    if cmd == "readiness":
        show_readiness(config)
    elif cmd == "history":
        show_history()
    elif cmd == "batch-dry-run":
        action_batch_dry_run(config)
    elif cmd in ("preflight", "dry-run", "approve", "send", "pipeline", "reset"):
        if not args.company or not args.segment:
            print(f"\n  Usage: python workflow.py {cmd} <company> <segment>\n")
            sys.exit(1)

        if cmd == "preflight":
            action_preflight(config, args.company, args.segment)
        elif cmd == "dry-run":
            action_dry_run(config, args.company, args.segment)
        elif cmd == "approve":
            action_approve(config, args.company, args.segment)
        elif cmd == "send":
            action_send(config, args.company, args.segment)
        elif cmd == "pipeline":
            action_pipeline(config, args.company, args.segment)
        elif cmd == "reset":
            state = load_state()
            action_reset(state, args.company, args.segment)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

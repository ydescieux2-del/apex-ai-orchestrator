#!/usr/bin/env python3
"""
apex_brain.py — Apex AI Autonomous Orchestrator
Von Descieux / Descieux Digital / Apex AI Consulting

The single entry point for autonomous system control.

USAGE:
  # Natural language command → full autonomous execution:
  python apex_brain.py "Run DataTech SEG-1 campaign and optimize for replies"

  # One autonomous cycle (what cron calls):
  python apex_brain.py --cycle

  # Start continuous autonomous loop:
  python apex_brain.py --loop

  # Show what the brain would decide right now (no execution):
  python apex_brain.py --status

  # Dry run: plan and log without executing sends:
  python apex_brain.py --cycle --dry-run

  # Show recent cycle history:
  python apex_brain.py --history

  # Add a strategy note for the brain:
  python apex_brain.py --note "SEG-1 subject lines with 'quick question' are outperforming"
"""

import argparse
import json
import os
import sys

# Ensure repo root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from brain.decision_engine import load_state, decide_next_action
from brain.planner          import plan, plan_from_decision
from brain.executor         import Executor
from brain.memory_manager   import (
    reflect, load_memory, update_memory,
    add_strategy_note, get_recent_learnings
)
from brain.run_loop         import run_cycle, start_loop, get_loop_history

BANNER = """
╔══════════════════════════════════════════════════════════╗
║          APEX AI — AUTONOMOUS ORCHESTRATOR               ║
║          Von Descieux / Descieux Digital                 ║
╚══════════════════════════════════════════════════════════╝
"""


def cmd_run_command(command: str, dry_run: bool = False):
    """Process a natural language command end-to-end."""
    print(BANNER)
    print(f"  Command: {command}\n")

    # Load current state for planner context
    print("[1/4] Loading system state...")
    state = load_state()

    print("[2/4] Planning tasks via Claude...")
    tasks = plan(command, context={
        "lead_inventory": state.get("lead_inventory", {}),
        "send_metrics":   state.get("send_metrics", {}),
        "reply_metrics":  state.get("reply_metrics", {}),
    })

    print(f"\n  Plan ({len(tasks)} steps):")
    for t in tasks:
        flag = "⚠️  DRY RUN" if dry_run and t.get("tool") in ("orchestrate_run",) else ""
        print(f"  {t.get('step','?')}. [{t.get('tool')}] {t.get('task')}  {flag}")
        if t.get("rationale"):
            print(f"     → {t.get('rationale')}")

    print("\n[3/4] Executing...")
    executor = Executor(dry_run=dry_run, verbose=True)
    results  = executor.run_plan(tasks)

    print("\n[4/4] Reflecting...")
    # Build a synthetic decision for reflection
    decision = {
        "action":  "user_command",
        "reason":  command,
        "command": command,
    }
    reflection = reflect(decision, results)
    print(f"\n  {reflection}")

    _print_summary(results)


def cmd_status():
    """Show what the brain would decide right now."""
    print(BANNER)
    print("  BRAIN STATUS\n")

    state    = load_state()
    decision = decide_next_action(state)
    memory   = load_memory()

    print("── CURRENT DECISION ─────────────────────────────────────")
    print(f"  Action:   {decision['action']}  (priority {decision['priority']})")
    print(f"  Target:   {decision.get('company','?')} / {decision.get('segment','?')}")
    print(f"  Reason:   {decision['reason']}")

    print("\n── SYSTEM METRICS ───────────────────────────────────────")
    inv   = state.get("lead_inventory", {})
    sends = state.get("send_metrics",   {})
    rep   = state.get("reply_metrics",  {})
    print(f"  Leads queued:   {inv.get('queued', 'n/a')}")
    print(f"  Total sent:     {sends.get('total_sent', 0)}")
    print(f"  Sent today:     {sends.get('today', 0)}")
    print(f"  Total replies:  {rep.get('total', 0)}")
    print(f"  Interested:     {rep.get('interested', 0)}")
    urgent = rep.get("urgent_followup", [])
    if urgent:
        print(f"  ⚠️  URGENT:     {len(urgent)} warm lead(s) need follow-up")

    print("\n── MEMORY ───────────────────────────────────────────────")
    gs = memory.get("global_stats", {})
    print(f"  All-time sends:    {gs.get('total_sends', 0)}")
    print(f"  All-time replies:  {gs.get('total_replies', 0)}")
    print(f"  Meetings booked:   {gs.get('total_meetings', 0)}")
    print(f"  Revenue tracked:   ${gs.get('total_revenue', 0):,}")

    recent = get_recent_learnings(3)
    if recent:
        print("\n── RECENT LEARNINGS ─────────────────────────────────────")
        for l in reversed(recent):
            print(f"  [{l.get('timestamp','?')[:16]}] {l.get('action','?')}")
            if l.get("reflection"):
                print(f"    {l['reflection'][:120]}...")

    print("\n── SEGMENTS ─────────────────────────────────────────────")
    for seg_id, seg in memory.get("segments", {}).items():
        rate = f"{seg.get('reply_rate', 0):.1%}" if seg.get("sends", 0) > 0 else "no data yet"
        print(f"  {seg_id} ({seg.get('name','?')}): {seg.get('sends',0)} sent, reply rate {rate}")

    print()


def cmd_history(n: int = 10):
    """Show recent autonomous cycle history."""
    print(BANNER)
    history = get_loop_history(n)
    if not history:
        print("  No cycle history yet. Run --cycle or --loop to start.\n")
        return
    print(f"  LAST {len(history)} CYCLES\n")
    for h in reversed(history):
        status = "✓" if h.get("failures", 0) == 0 else "✗"
        print(f"  {status} [{h.get('timestamp','?')[:16]}] {h.get('action','?')}")
        print(f"    {h.get('successes',0)}/{h.get('tasks_run',0)} tasks | {h.get('duration_s',0):.0f}s | P{h.get('priority','?')}")
        if h.get("reflection"):
            print(f"    → {h['reflection'][:120]}")
        print()


def _print_summary(results: list[dict]):
    successes = [r for r in results if r.get("success")]
    failures  = [r for r in results if not r.get("success")]
    print(f"\n{'─'*50}")
    print(f"  COMPLETE: {len(successes)}/{len(results)} tasks succeeded")
    if failures:
        print(f"  FAILED:   {[r['tool'] for r in failures]}")
    print(f"{'─'*50}\n")


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Apex AI — Autonomous Orchestrator Brain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("command",    nargs="?",        help="Natural language command to execute")
    parser.add_argument("--cycle",    action="store_true", help="Run one autonomous decision cycle")
    parser.add_argument("--loop",     action="store_true", help="Start continuous autonomous loop")
    parser.add_argument("--status",   action="store_true", help="Show brain status and current decision")
    parser.add_argument("--history",  action="store_true", help="Show recent cycle history")
    parser.add_argument("--dry-run",  action="store_true", help="Plan but don't execute sends")
    parser.add_argument("--interval", type=int, default=15,  help="Loop interval in minutes (default 15)")
    parser.add_argument("--note",     type=str,             help="Add a strategy note to memory")

    args = parser.parse_args()

    if args.note:
        add_strategy_note(args.note)
        print(f"✓ Note saved: {args.note}\n")

    elif args.status:
        cmd_status()

    elif args.history:
        cmd_history()

    elif args.loop:
        start_loop(interval_minutes=args.interval, dry_run=args.dry_run)

    elif args.cycle:
        run_cycle(dry_run=args.dry_run, verbose=True)

    elif args.command:
        cmd_run_command(args.command, dry_run=args.dry_run)

    else:
        # Default: show status
        cmd_status()


if __name__ == "__main__":
    main()

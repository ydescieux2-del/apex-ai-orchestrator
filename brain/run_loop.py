"""
run_loop.py — The Autonomous Heartbeat

This is the heart of the system. It runs on a cron schedule (every 15 min)
and executes one full cycle:

    Load state → Decide → Plan → Execute → Reflect → Learn → Sleep

Can also be triggered ad-hoc by apex_brain.py for one-shot commands.

Usage:
    # One autonomous cycle (called by cron):
    python brain/run_loop.py

    # Continuous loop (called by apex_brain.py --loop):
    from brain.run_loop import start_loop
    start_loop(interval_minutes=15)
"""

import json
import os
import sys
import time
from datetime import datetime

# Make sure parent is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.decision_engine import load_state, decide
from brain.planner          import plan_from_decision
from brain.executor         import Executor
from brain.memory_manager   import reflect, update_memory, load_memory

LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "memory", "loop_log.json")


# ─── Single cycle ─────────────────────────────────────────────────────────────

def run_cycle(dry_run: bool = False, verbose: bool = True) -> dict:
    """
    Execute one full autonomous cycle.

    Returns a summary dict with decision, results, and reflection.
    """
    cycle_start = datetime.now()
    if verbose:
        print(f"\n{'='*60}")
        print(f"  APEX BRAIN — Autonomous Cycle")
        print(f"  {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")

    # ── Step 1: Load full system state ──────────────────────────────────────
    if verbose:
        print("\n[1/5] Loading system state...")
    state = load_state()
    _log_state_summary(state, verbose)

    # ── Step 2: Decide what to do ────────────────────────────────────────────
    if verbose:
        print("\n[2/5] Deciding next action...")
    decision = decide(state)
    if verbose:
        print(f"  Action:   {decision['action']} (priority {decision['priority']})")
        print(f"  Reason:   {decision['reason']}")
        if decision.get('company'):
            print(f"  Target:   {decision['company']} / {decision.get('segment', 'all')}")

    # ── Step 3: Plan the execution ────────────────────────────────────────────
    if verbose:
        print("\n[3/5] Planning tasks...")
    tasks = plan_from_decision(decision)
    if verbose:
        for t in tasks:
            print(f"  {t.get('step','?')}. {t.get('task','?')}  →  {t.get('tool','?')}")

    # ── Step 4: Execute ───────────────────────────────────────────────────────
    if verbose:
        print("\n[4/5] Executing plan...")
    executor = Executor(dry_run=dry_run, verbose=verbose)
    results  = executor.run_plan(tasks)

    # ── Step 5: Reflect and learn ─────────────────────────────────────────────
    if verbose:
        print("\n[5/5] Reflecting and updating memory...")
    reflection = reflect(decision, results)
    if verbose:
        print(f"\n  Reflection: {reflection}")

    # Build cycle summary
    duration = (datetime.now() - cycle_start).total_seconds()
    summary  = {
        "timestamp":  cycle_start.isoformat(),
        "action":     decision["action"],
        "priority":   decision["priority"],
        "reason":     decision["reason"],
        "tasks_run":  len(results),
        "successes":  len([r for r in results if r.get("success")]),
        "failures":   len([r for r in results if not r.get("success")]),
        "reflection": reflection,
        "duration_s": round(duration, 1),
        "dry_run":    dry_run,
    }

    _append_loop_log(summary)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Cycle complete in {duration:.1f}s")
        print(f"  {summary['successes']}/{summary['tasks_run']} tasks succeeded")
        print(f"{'='*60}\n")

    return summary


# ─── Continuous loop ──────────────────────────────────────────────────────────

def start_loop(interval_minutes: int = 15, dry_run: bool = False):
    """
    Run the autonomous loop indefinitely.
    Respects quiet hours (10 PM – 7 AM) to avoid inbox noise.
    """
    print(f"\n[Apex Brain] Starting autonomous loop (every {interval_minutes} min)")
    print("[Apex Brain] Press Ctrl+C to stop.\n")

    while True:
        try:
            hour = datetime.now().hour
            if hour >= 22 or hour < 7:
                print(f"[Apex Brain] Quiet hours ({hour}:00) — skipping cycle. Sleeping 30 min.")
                time.sleep(30 * 60)
                continue

            run_cycle(dry_run=dry_run)
            time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n[Apex Brain] Loop stopped by user.")
            break
        except Exception as e:
            print(f"\n[Apex Brain] Cycle error: {e}")
            print("[Apex Brain] Sleeping 5 min then retrying...")
            time.sleep(5 * 60)


# ─── Logging helpers ──────────────────────────────────────────────────────────

def _log_state_summary(state: dict, verbose: bool):
    if not verbose:
        return
    inv   = state.get("lead_inventory", {})
    sends = state.get("send_metrics", {})
    rep   = state.get("reply_metrics", {})
    print(f"  Leads queued:    {inv.get('queued', 'n/a')}")
    print(f"  Total sent:      {sends.get('total_sent', 0)}")
    print(f"  Sent today:      {sends.get('today', 0)}")
    print(f"  Total replies:   {rep.get('total', 0)}")
    print(f"  Interested:      {rep.get('interested', 0)}")
    print(f"  Urgent followup: {len(rep.get('urgent_followup', []))}")


def _append_loop_log(summary: dict):
    """Keep the last 200 cycle summaries in loop_log.json."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    log = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                log = json.load(f)
        except Exception:
            log = []
    log.append(summary)
    if len(log) > 200:
        log = log[-200:]
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def get_loop_history(n: int = 10) -> list[dict]:
    """Return the last n cycle summaries."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE) as f:
        try:
            return json.load(f)[-n:]
        except Exception:
            return []


# ─── Entry point (called by cron) ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Apex Brain — one autonomous cycle")
    parser.add_argument("--dry-run", action="store_true", help="Plan and log but don't execute sends")
    parser.add_argument("--quiet",   action="store_true", help="Suppress verbose output")
    args = parser.parse_args()
    run_cycle(dry_run=args.dry_run, verbose=not args.quiet)

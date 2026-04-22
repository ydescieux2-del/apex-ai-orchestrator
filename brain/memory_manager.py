"""
memory_manager.py — Persistent Brain Memory

Stores and retrieves system learnings across sessions.
This is what separates an autonomous system from a script that starts fresh every run.

Two files:
  memory/system_memory.json  — Current state: segment performance, sender health, copy performance
  memory/learning_log.json   — Append-only: every decision made + its outcome

Usage:
    from brain.memory_manager import load_memory, update_memory, record_learning, reflect
"""

import json
import os
from datetime import datetime
from typing import Any

ORCHESTRATOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR       = os.path.join(ORCHESTRATOR_DIR, "memory")
MEMORY_FILE      = os.path.join(MEMORY_DIR, "system_memory.json")
LEARNING_FILE    = os.path.join(MEMORY_DIR, "learning_log.json")


# ─── Bootstrap ────────────────────────────────────────────────────────────────

def _ensure_memory_dir():
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _init_memory() -> dict:
    return {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "segments": {
            "SEG-1": {
                "name":          "IT Procurement",
                "company":       "datatech",
                "sends":         0,
                "replies":       0,
                "reply_rate":    0.0,
                "best_subject":  None,
                "best_body_idx": None,
                "notes":         [],
            },
            "SEG-6": {
                "name":          "CEOs of Nonprofits",
                "company":       "zs_recycling",
                "sends":         0,
                "replies":       0,
                "reply_rate":    0.0,
                "best_subject":  None,
                "best_body_idx": None,
                "notes":         [],
            },
        },
        "senders": {
            "SENDER_01": {
                "email":       "James@DataTechDisposition.com",
                "daily_cap":   50,
                "warmup_day":  0,
                "health":      "warming",
                "bounces":     0,
                "bounce_rate": 0.0,
            }
        },
        "copy_performance": {},
        "global_stats": {
            "total_sends":    0,
            "total_replies":  0,
            "total_meetings": 0,
            "total_revenue":  0,
        },
        "strategy_notes": [],
        "last_action":    None,
        "last_decision":  None,
    }


# ─── Core read/write ──────────────────────────────────────────────────────────

def load_memory() -> dict:
    _ensure_memory_dir()
    if not os.path.exists(MEMORY_FILE):
        mem = _init_memory()
        _save_memory(mem)
        return mem
    with open(MEMORY_FILE) as f:
        return json.load(f)


def _save_memory(mem: dict):
    _ensure_memory_dir()
    mem["last_updated"] = datetime.now().isoformat()
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)


def update_memory(updates: dict):
    """
    Merge updates dict into system_memory.json.

    Supports nested updates via dot notation key or direct key.
    Examples:
        update_memory({"global_stats.total_sends": 50})
        update_memory({"last_action": "run_campaign"})
        update_memory({"segments.SEG-1.reply_rate": 0.06})
    """
    mem = load_memory()
    for key, value in updates.items():
        _deep_set(mem, key, value)
    _save_memory(mem)


def _deep_set(d: dict, key: str, value: Any):
    """Set a value using dot notation path."""
    parts = key.split(".")
    for part in parts[:-1]:
        d = d.setdefault(part, {})
    d[parts[-1]] = value


# ─── Learning log ─────────────────────────────────────────────────────────────

def record_learning(entry: dict):
    """
    Append a learning entry to the log.

    entry should include:
        action, decision, results, reflection, timestamp
    """
    _ensure_memory_dir()
    log = []
    if os.path.exists(LEARNING_FILE):
        with open(LEARNING_FILE) as f:
            try:
                log = json.load(f)
            except json.JSONDecodeError:
                log = []

    entry["timestamp"] = entry.get("timestamp", datetime.now().isoformat())
    log.append(entry)

    # Keep log bounded (last 500 entries)
    if len(log) > 500:
        log = log[-500:]

    with open(LEARNING_FILE, "w") as f:
        json.dump(log, f, indent=2)


def get_recent_learnings(n: int = 10) -> list[dict]:
    """Return the n most recent learning entries."""
    if not os.path.exists(LEARNING_FILE):
        return []
    with open(LEARNING_FILE) as f:
        try:
            log = json.load(f)
        except json.JSONDecodeError:
            return []
    return log[-n:]


# ─── Reflection (LLM-powered) ─────────────────────────────────────────────────

def reflect(decision: dict, results: list[dict]) -> str:
    """
    Call Claude to generate a reflection on what happened this cycle.
    Reflection is stored in learning_log.json and used to improve future decisions.
    """
    import anthropic

    successes = [r for r in results if r.get("success")]
    failures  = [r for r in results if not r.get("success")]
    recent    = get_recent_learnings(5)

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    prompt = f"""You are the reflection layer of an autonomous B2B outreach system.

DECISION MADE:
{json.dumps(decision, indent=2)}

EXECUTION RESULTS:
Successes ({len(successes)}): {[r['tool'] for r in successes]}
Failures  ({len(failures)}):  {[r['tool'] for r in failures]}

RECENT HISTORY:
{json.dumps(recent, indent=2)[:1000]}

In 2-4 sentences, answer:
1. Did the decision make sense given the results?
2. What should the system do differently next cycle?
3. Any pattern emerging from the recent history?

Return as plain text. Be direct and specific."""

    try:
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        reflection_text = msg.content[0].text.strip()
    except Exception as e:
        reflection_text = f"Reflection failed: {e}"

    # Record in learning log
    record_learning({
        "action":     decision.get("action"),
        "reason":     decision.get("reason"),
        "successes":  len(successes),
        "failures":   len(failures),
        "tools_run":  [r["tool"] for r in results],
        "reflection": reflection_text,
    })

    # Store last reflection in memory
    update_memory({
        "last_action":   decision.get("action"),
        "last_decision": decision,
    })

    return reflection_text


# ─── Metrics updater ──────────────────────────────────────────────────────────

def update_segment_metrics(segment: str, sends_delta: int = 0, replies_delta: int = 0):
    """Increment per-segment counters after a campaign run."""
    mem = load_memory()
    seg = mem.setdefault("segments", {}).setdefault(segment, {
        "sends": 0, "replies": 0, "reply_rate": 0.0
    })
    seg["sends"]  = seg.get("sends", 0) + sends_delta
    seg["replies"] = seg.get("replies", 0) + replies_delta
    if seg["sends"] > 0:
        seg["reply_rate"] = round(seg["replies"] / seg["sends"], 4)

    mem["global_stats"]["total_sends"]   = mem["global_stats"].get("total_sends", 0) + sends_delta
    mem["global_stats"]["total_replies"] = mem["global_stats"].get("total_replies", 0) + replies_delta

    _save_memory(mem)


def add_strategy_note(note: str):
    """Append a strategic note to memory (e.g., from Von or reflection)."""
    mem = load_memory()
    mem.setdefault("strategy_notes", []).append({
        "note":      note,
        "timestamp": datetime.now().isoformat(),
    })
    # Cap at 50 notes
    mem["strategy_notes"] = mem["strategy_notes"][-50:]
    _save_memory(mem)

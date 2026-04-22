"""
decision_engine.py — Apex Autonomous Brain

Reads full system state and returns a prioritized action recommendation.
This is the "nervous system" that turns metrics into decisions.

No LLM calls here — this is deterministic logic that runs fast and cheap.
The LLM (planner.py) only gets invoked when the decision engine
calls for a plan (e.g., "optimize_copy" or "run_campaign").
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

ORCHESTRATOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS_DIR = os.path.expanduser("~/james-outreach-harness")
MEMORY_FILE = os.path.join(ORCHESTRATOR_DIR, "memory", "system_memory.json")


# ─── Thresholds (tune these as you learn) ─────────────────────────────────────

THRESHOLDS = {
    "min_reply_rate":       0.01,   # Below 1% → pause and optimize copy
    "target_reply_rate":    0.05,   # Above 5% → scale up
    "max_bounce_rate":      0.08,   # Above 8% → pause sender, review list quality
    "min_leads_remaining":  50,     # Below 50 → trigger lead sourcing
    "max_daily_sends":      50,     # Hard cap per sender per day
    "followup_lag_hours":   72,     # If interested reply unhandled > 3h → urgent
    "sender_warmup_days":   14,     # Days before sender at full capacity
    "cooldown_hours":       120,    # 5-day deconflict window
}


# ─── State reader ──────────────────────────────────────────────────────────────

def load_state() -> dict:
    """Merge all available data sources into one system snapshot."""
    state = {
        "timestamp": datetime.now().isoformat(),
        "companies": {},
        "segments": {},
        "senders": {},
        "replies": {},
        "memory": {},
        "alerts": [],
    }

    # Company config
    config_path = os.path.join(ORCHESTRATOR_DIR, "company_config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            cfg = json.load(f)
        state["companies"] = cfg.get("companies", {})
        state["segments"] = cfg.get("segment_registry", {})
        state["global_rules"] = cfg.get("global_rules", {})

    # Campaign state
    campaign_path = os.path.join(ORCHESTRATOR_DIR, "campaign_state.json")
    if os.path.exists(campaign_path):
        with open(campaign_path) as f:
            state["campaign_state"] = json.load(f)

    # Master send log → compute per-segment metrics
    send_log_path = os.path.join(ORCHESTRATOR_DIR, "master_send_log.json")
    if os.path.exists(send_log_path):
        with open(send_log_path) as f:
            send_log = json.load(f)
        state["send_log"] = send_log
        state["send_metrics"] = _compute_send_metrics(send_log)

    # Inbox/reply ledger
    inbox_path = os.path.join(ORCHESTRATOR_DIR, "inbox_ledger.json")
    if os.path.exists(inbox_path):
        with open(inbox_path) as f:
            inbox = json.load(f)
        state["replies"] = inbox if isinstance(inbox, dict) else {}
        state["reply_metrics"] = _compute_reply_metrics(inbox)

    # DataTech-specific: email_log, leads, sender health
    dt_email_log = os.path.join(HARNESS_DIR, "email_log.json")
    if os.path.exists(dt_email_log):
        with open(dt_email_log) as f:
            dt_log = json.load(f)
        state["datatech_log"] = dt_log
        state["datatech_metrics"] = _compute_datatech_metrics(dt_log)

    dt_leads = os.path.join(HARNESS_DIR, "leads.json")
    if os.path.exists(dt_leads):
        with open(dt_leads) as f:
            leads = json.load(f)
        state["lead_inventory"] = _summarize_leads(leads)

    dt_senders = os.path.join(HARNESS_DIR, "senders.json")
    if os.path.exists(dt_senders):
        with open(dt_senders) as f:
            state["senders"] = json.load(f)

    # Persistent memory
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            state["memory"] = json.load(f)

    return state


# ─── Metrics helpers ───────────────────────────────────────────────────────────

def _compute_send_metrics(send_log: list | dict) -> dict:
    metrics = {"total_sent": 0, "by_segment": {}, "by_company": {}, "today": 0}
    entries = send_log if isinstance(send_log, list) else send_log.get("entries", [])
    today = datetime.now().date().isoformat()
    for entry in entries:
        seg = entry.get("segment", "unknown")
        co  = entry.get("company", "unknown")
        metrics["total_sent"] += 1
        metrics["by_segment"][seg] = metrics["by_segment"].get(seg, 0) + 1
        metrics["by_company"][co]  = metrics["by_company"].get(co, 0) + 1
        if entry.get("sent_at", "")[:10] == today:
            metrics["today"] += 1
    return metrics


def _compute_reply_metrics(inbox: list | dict) -> dict:
    entries = inbox if isinstance(inbox, list) else inbox.get("replies", [])
    metrics = {
        "total": len(entries),
        "interested": 0,
        "not_interested": 0,
        "ooo":  0,
        "unsubscribe": 0,
        "urgent_followup": [],
    }
    now = datetime.now()
    for r in entries:
        classification = r.get("classification", r.get("type", "unknown"))
        metrics[classification] = metrics.get(classification, 0) + 1
        # Flag interested replies that haven't been followed up
        if classification == "interested" and not r.get("followed_up"):
            replied_at = r.get("replied_at", r.get("timestamp", ""))
            if replied_at:
                try:
                    age_hours = (now - datetime.fromisoformat(replied_at)).total_seconds() / 3600
                    if age_hours > THRESHOLDS["followup_lag_hours"]:
                        metrics["urgent_followup"].append(r)
                except Exception:
                    pass
    return metrics


def _compute_datatech_metrics(email_log: list | dict) -> dict:
    entries = email_log if isinstance(email_log, list) else []
    if isinstance(email_log, dict):
        entries = email_log.get("sent", []) + email_log.get("log", [])
    sent    = [e for e in entries if e.get("status") not in ("dry_run", "draft")]
    bounced = [e for e in sent if e.get("bounced") or e.get("status") == "bounced"]
    return {
        "total_sent": len(sent),
        "bounces": len(bounced),
        "bounce_rate": len(bounced) / len(sent) if sent else 0,
        "dry_runs": len([e for e in entries if e.get("status") == "dry_run"]),
    }


def _summarize_leads(leads: list | dict) -> dict:
    if isinstance(leads, dict):
        leads = leads.get("leads", [])
    summary = {"total": len(leads), "by_status": {}, "by_segment": {}}
    for lead in leads:
        s = lead.get("status", "unknown")
        seg = lead.get("segment", "unknown")
        summary["by_status"][s] = summary["by_status"].get(s, 0) + 1
        summary["by_segment"][seg] = summary["by_segment"].get(seg, 0) + 1
    summary["queued"] = summary["by_status"].get("queued", 0)
    summary["sent"]   = summary["by_status"].get("sent", 0)
    return summary


# ─── Decision engine ───────────────────────────────────────────────────────────

def decide(state: dict) -> dict:
    """
    Returns:
        {
            "action":   str,           # what to do
            "priority": int,           # 1 (urgent) → 5 (routine)
            "company":  str | None,
            "segment":  str | None,
            "reason":   str,
            "context":  dict,          # extra data for the executor
        }
    """
    alerts = []

    # ── Priority 1: Urgent follow-up on warm leads ──────────────────────────
    reply_metrics = state.get("reply_metrics", {})
    urgent = reply_metrics.get("urgent_followup", [])
    if urgent:
        return {
            "action":   "followup_warm_leads",
            "priority": 1,
            "company":  "datatech",
            "segment":  None,
            "reason":   f"{len(urgent)} interested reply(ies) unhandled for >{THRESHOLDS['followup_lag_hours']}h",
            "context":  {"leads": urgent},
        }

    # ── Priority 1: Bounce spike — pause sender ──────────────────────────────
    dt_metrics = state.get("datatech_metrics", {})
    if dt_metrics.get("bounce_rate", 0) > THRESHOLDS["max_bounce_rate"]:
        return {
            "action":   "pause_sender",
            "priority": 1,
            "company":  "datatech",
            "segment":  None,
            "reason":   f"Bounce rate {dt_metrics['bounce_rate']:.1%} exceeds {THRESHOLDS['max_bounce_rate']:.0%} threshold",
            "context":  {"bounce_rate": dt_metrics["bounce_rate"]},
        }

    # ── Priority 2: Low reply rate — optimize copy ───────────────────────────
    send_metrics = state.get("send_metrics", {})
    total_sent   = send_metrics.get("total_sent", 0)
    total_replies = reply_metrics.get("total", 0)
    if total_sent >= 20:
        reply_rate = total_replies / total_sent
        if reply_rate < THRESHOLDS["min_reply_rate"]:
            return {
                "action":   "optimize_copy",
                "priority": 2,
                "company":  "datatech",
                "segment":  "SEG-1",
                "reason":   f"Reply rate {reply_rate:.2%} below {THRESHOLDS['min_reply_rate']:.0%} floor — copy needs work",
                "context":  {"reply_rate": reply_rate, "total_sent": total_sent},
            }

    # ── Priority 2: Lead inventory low — source new leads ───────────────────
    inventory = state.get("lead_inventory", {})
    queued = inventory.get("queued", 999)  # assume plenty if file not found
    if queued < THRESHOLDS["min_leads_remaining"]:
        return {
            "action":   "source_leads",
            "priority": 2,
            "company":  "datatech",
            "segment":  "SEG-1",
            "reason":   f"Only {queued} leads queued — below minimum {THRESHOLDS['min_leads_remaining']}",
            "context":  {"queued": queued},
        }

    # ── Priority 3: Daily send quota not yet hit — run campaign ─────────────
    today_sent = send_metrics.get("today", 0)
    active_companies = [k for k, v in state.get("companies", {}).items()
                        if v.get("status") == "active"]
    for company in active_companies:
        if today_sent < THRESHOLDS["max_daily_sends"]:
            return {
                "action":   "run_campaign",
                "priority": 3,
                "company":  company,
                "segment":  "SEG-1",
                "reason":   f"Only {today_sent}/{THRESHOLDS['max_daily_sends']} daily sends used — capacity available",
                "context":  {"today_sent": today_sent, "capacity": THRESHOLDS["max_daily_sends"]},
            }

    # ── Priority 4: Check inbox for new replies ──────────────────────────────
    return {
        "action":   "monitor_inbox",
        "priority": 4,
        "company":  "datatech",
        "segment":  None,
        "reason":   "Routine inbox scan — daily quota met, no urgent actions",
        "context":  {},
    }


def decide_next_action(state: Optional[dict] = None) -> dict:
    """Public API: load state if not provided, then decide."""
    if state is None:
        state = load_state()
    return decide(state)

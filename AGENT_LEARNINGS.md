# AGENT_LEARNINGS.md — Apex AI Orchestrator
**Last updated:** 2026-04-09

---

## What This Is

Cross-company outreach orchestration layer for Apex AI Consulting. Manages segment ownership, deduplication, and audit logging across multiple client outreach harnesses (DataTech, EZ Recycling, pending others).

## Architecture

```
orchestrate.py          — CLI entry: --status, --audit, --company, --segment, --dry-run
deconflict.py           — Cross-company deconfliction (5-day cooldown, no same-day overlap, opt-out propagation)
inbox_monitor.py        — Gmail scanning, reply classification (interested/unsubscribe/OOO/not interested), auto-draft
follow_up_engine.py     — Day 3/7/14 cadence with cross-company blocking
lead_scorer.py          — Lead scoring engine
lead_segmenter.py       — Segment assignment logic
lead_sourcer.py         — Multi-provider sourcing (CSV, Hunter, Apollo, web discovery)
lead_verifier.py        — ZeroBounce email verification (env var: ZEROBOUNCE_API_KEY)
calendly_links.py       — Single-use Calendly link generation + booking tracking
providers/              — Pluggable lead source providers (csv, hunter, apollo, web)
data/raw/               — 9 WIZA CSVs covering all segments
```

## Company Registry (as of April 2026)

| Company | Segments | Status |
|---------|----------|--------|
| DataTech Disposition | SEG-1, SEG-3, SEG-7 | Active |
| EZ Recycling | SEG-5, SEG-6 | Setup (needs creds) |
| EHS California | SEG-2 | Pending |
| Financial/Banks | SEG-4 | Pending |

## Billing Model

$500 setup + $300/mo retainer per company.

## Data Stores

- `scheduling_tracker.json` — send schedule
- `inbox_ledger.json` — classified replies
- `pending_drafts.json` — auto-drafted responses
- `send_ledger.json` — cross-company send log
- `sourcing_log.json` — lead acquisition audit
- `discovered_companies.json` — web-discovered prospects

## What Has Never Been Done

- No live campaign has ever run through the full autonomous pipeline end-to-end.
- Scheduled task automation not live (inbox monitor every 15 min, follow-ups daily 9 AM).
- Calendly API token not configured (links default to public Calendly URL).
- Text layout engine branch exists but npm package not built/published.

## Critical Rules

1. **Segment ownership is sacred.** Each segment belongs to exactly one company. Violations are blocked.
2. **Deconfliction is mandatory.** 5-day cooldown between sends to same lead across companies. No same-day overlap.
3. **All secrets via env vars.** `.env` is gitignored. Never hardcode API keys.
4. **Opt-out propagation is global.** An unsubscribe from any company blocks ALL companies.
5. **Each harness is standalone.** The orchestrator coordinates but doesn't replace per-company harnesses.

## Known Issues

- EZ Recycling needs Gmail credentials confirmed before moving to "active"
- 2 pending companies (EHS California, Financial/Banks) have no harnesses built yet
- Raw WIZA CSVs in `data/raw/` need periodic refresh

## Next Steps (Priority Order)

1. Configure Calendly API token
2. Run first live campaign through full pipeline (DataTech SEG-1 recommended)
3. Activate scheduled inbox monitoring
4. Move EZ Recycling from "setup" to "active" once creds confirmed
5. Build harnesses for companies 3 and 4 when ready

---

## BRAIN LAYER — Added 2026-04-09

The autonomous brain was added as a separate package. Before this, the system was execution-only — everything required manual commands. The brain adds: decision logic, LLM planning, execution routing, persistent memory, and a self-running loop.

### New File Structure

```
brain/
  __init__.py          — Package init
  decision_engine.py   — Reads system state, returns prioritized action (no LLM — pure logic)
  planner.py           — Claude API: intent → JSON task graph
  executor.py          — Routes tool names to actual subprocess calls
  memory_manager.py    — read/write system_memory.json + learning_log.json
  run_loop.py          — Autonomous heartbeat (single cycle or continuous loop)
  install_cron.sh      — Wires 15-min loop to macOS cron

memory/
  system_memory.json   — Segment metrics, sender health, strategy notes (persists across sessions)
  learning_log.json    — Append-only: every decision + reflection (last 500 entries)
  loop_log.json        — Cycle summary history (auto-created)
  cron.log             — Cron output (auto-created)

apex_brain.py          — CLI entry point (replaces manual orchestrate.py for most tasks)
```

### How to Use

```bash
# Natural language → full autonomous execution:
python apex_brain.py "Run DataTech SEG-1 campaign and optimize for replies"

# One decision cycle (what cron calls):
python apex_brain.py --cycle

# Show current brain state:
python apex_brain.py --status

# Start continuous loop (15 min intervals):
python apex_brain.py --loop

# Safe test run — plans without sending:
python apex_brain.py --cycle --dry-run

# Show recent cycle history:
python apex_brain.py --history

# Add a strategy note the brain will remember:
python apex_brain.py --note "SEG-1 subject line with question outperforms statement"
```

### How to Activate Cron

```bash
cd ~/apex-ai-orchestrator
./brain/install_cron.sh
```

This wires the brain to run every 15 minutes, 7AM–10PM, respecting quiet hours.

### Decision Priority Order

1. Urgent: interested reply unhandled > 3 hours → `followup_warm_leads`
2. Urgent: bounce rate > 8% → `pause_sender`
3. High:   reply rate < 1% (after 20+ sends) → `optimize_copy`
4. High:   lead inventory < 50 queued → `source_leads`
5. Normal: daily send quota not met → `run_campaign`
6. Low:    default → `monitor_inbox`

### Thresholds (tune in decision_engine.py)

```python
THRESHOLDS = {
    "min_reply_rate":      0.01,   # Below 1% → pause and optimize copy
    "target_reply_rate":   0.05,   # Above 5% → scale up
    "max_bounce_rate":     0.08,   # Above 8% → pause sender
    "min_leads_remaining": 50,     # Below 50 → source leads
    "max_daily_sends":     50,     # Hard cap per sender per day
    "followup_lag_hours":  72,     # Hours before interested reply becomes urgent
    "sender_warmup_days":  14,     # Days before sender at full capacity
}
```

### Current Status (Apr 9)

- Brain installed, not yet activated for cron
- Memory initialized with current DataTech state (9 real sends, 4,745 qualified leads)
- SENDER_01 (James@DataTechDisposition.com) on warmup Day 3 — stay at 10/day
- First recommended action: `run_campaign` (SEG-1, 10 leads, warmup-safe)
- Test with `python apex_brain.py --cycle --dry-run` before activating

### What's Not Wired Yet (Future)

- Gmail MCP → inbox_monitor and response_handler should call Gmail MCP directly (currently IMAP stub)
- Calendly MCP → calendly_links.py has TODO for actual API calls
- Ollama/Mistral local routing → cheap tasks could use local models instead of Claude API
- Multi-company expansion → brain currently prioritizes DataTech only; needs EZ Recycling and company_3 config


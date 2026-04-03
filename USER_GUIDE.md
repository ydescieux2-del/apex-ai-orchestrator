# APEX AI Orchestrator — Complete User Guide
**Version 1.0** | Last Updated: March 31, 2026

---

## Table of Contents
1. [System Overview](#system-overview)
2. [The Autonomous Pipeline](#the-autonomous-pipeline)
3. [Module Reference](#module-reference)
4. [Running Your First Campaign](#running-your-first-campaign)
5. [Monitoring & Dashboards](#monitoring--dashboards)
6. [Scheduling Automation](#scheduling-automation)
7. [Troubleshooting](#troubleshooting)
8. [Data Flow & Ledgers](#data-flow--ledgers)

---

## System Overview

You now have a **fully autonomous multi-company outreach orchestrator** that:
- ✅ Sends personalized emails from multiple ITAD companies
- ✅ Monitors inboxes for replies automatically
- ✅ Generates Calendly scheduling links for "interested" prospects
- ✅ Auto-drafts follow-up responses
- ✅ Enforces 5-day cooldown + no same-day overlap across all companies
- ✅ Tracks every email, reply, and meeting across a unified dashboard

**Two companies active:**
1. **DataTech Disposition** (DTD) — 4 segments, ~5,700 leads
2. **EZ Recycling** — 4 segments, 252 leads

---

## The Autonomous Pipeline

### Phase 1: Send (You Do This)
```
python ~/james-outreach-harness/send_emails.py --dry-run 10
python ~/ez-recycling-harness/send_emails.py --run 50
```
✅ Emails go out → `email_log.json` populates → deconfliction ledger updates

### Phase 2: Monitor (Scheduled Every 15 Min)
```
cd ~/apex-ai-orchestrator && python3 inbox_monitor.py --scan
```
🔄 Scans Gmail for replies → classifies them → saves to `inbox_ledger.json`

### Phase 3: Draft & Respond (Automated)
```
Interested? → Auto-generates warm reply with Calendly link → `pending_drafts.json`
Unsubscribe? → Opts out across ALL companies → `send_ledger.json` updated
Out of office? → Logged, no action
```

### Phase 4: Follow-Ups (Scheduled Every 24h)
```
cd ~/james-outreach-harness && python3 follow_up_sequences.py --run-due
```
📧 Day 3, 7, 14 follow-ups sent automatically (if no reply detected)

### Phase 5: Meetings (Real-time)
```
Prospect clicks Calendly link → books meeting → `scheduling_tracker.json` updates
Dashboard shows BOOKED status
```

---

## Module Reference

### 1. Inbox Monitor (`inbox_monitor.py`)

**What it does:**
- Searches Gmail for replies to your outreach emails
- Classifies each reply: `interested`, `unsubscribe`, `out_of_office`, `not_interested`
- For interested replies: auto-drafts a follow-up
- For unsubscribes: opts lead out across ALL companies

**Commands:**
```bash
# Scan inbox (reads from Gmail, logs to inbox_ledger.json)
python3 inbox_monitor.py --scan

# Preview without writing
python3 inbox_monitor.py --scan --dry-run

# Simulate a reply (for testing)
python3 inbox_monitor.py --simulate "john@example.com" --type interested

# Show status
python3 inbox_monitor.py --status
```

**Output Files:**
- `inbox_ledger.json` — All reply classifications and actions taken
- `pending_drafts.json` — Auto-generated replies waiting for human review

---

### 2. Calendly Links (`calendly_links.py`)

**What it does:**
- Generates single-use Calendly scheduling links per prospect
- Tracks which links have been booked
- Injects links into email replies automatically

**Commands:**
```bash
# Create a link for someone
python3 calendly_links.py --create "ted.ross@lacity.gov" "Ted Ross" --company ez_recycling

# Mark someone as booked (when they click the link)
python3 calendly_links.py --booked "ted.ross@lacity.gov"

# Show tracker status
python3 calendly_links.py --status
```

**Output Files:**
- `scheduling_tracker.json` — All generated links and booking status

---

### 3. Follow-Up Sequences (`follow_up_sequences.py`)

**What it does:**
- Sends Day 3, 7, 14 follow-ups automatically
- Each day has a different angle/reason to stay in touch
- Respects reply detection (no follow-ups if they've already replied)
- Enforces 5-day cooldown across all companies

**Commands:**
```bash
# Send all due follow-ups today
cd ~/james-outreach-harness
python3 follow_up_sequences.py --run-due

# Preview without sending
python3 follow_up_sequences.py --run-due --dry-run

# Show status
python3 follow_up_sequences.py --status
```

**Output Files:**
- `follow_up_log.json` — Every follow-up sent (which day, which lead, success/failure)

---

### 4. Dashboards (HTML + JSON)

**DTD Dashboard:**
```
http://localhost:8080/demo/dashboard.html
```
Shows: 5,721 leads, 4 segments, email pipeline status

**EZ Recycling Dashboard:**
```
http://localhost:8081/demo/dashboard.html
```
Shows: 252 leads, 4 segments, plus **NEW**: Replies & Meetings panel

**New Replies & Meetings Panel:**
- 4 stat cards: Total Replies, Interested, Unsubscribes, Booked Meetings
- Inbox log: searchable table of all replies with classification
- Pending drafts: auto-generated replies for review
- Scheduling tracker: links and booking status

---

## Running Your First Campaign

### Step 1: Dry-Run (Test the System)
```bash
cd ~/james-outreach-harness

# Preview 10 emails without sending
python3 send_emails.py --dry-run 10

# You'll see:
#   📧 Subject line
#   👤 To: email@domain.com
#   ✅ Queued (dry-run mode)
```

### Step 2: Send a Small Batch (5-10 leads)
```bash
# Go live with a small batch
python3 send_emails.py --run 5

# Watch for:
#   ✅ Email sent
#   ⏳ Waiting Xs before next send (randomized 90-240s)
#   📝 Logged to email_log.json
```

### Step 3: Check the Dashboard
```
http://localhost:8080/demo/dashboard.html
```
You should see:
- Total Leads count
- "Sent" count increases
- "Pipeline Funnel" shows: New → Sent → (waiting for replies)

### Step 4: Enable Inbox Monitoring
```bash
# Optional: test with a simulated reply first
cd ~/apex-ai-orchestrator
python3 inbox_monitor.py --simulate "john@example.com" --type interested

# Then schedule live monitoring (see "Scheduling Automation" below)
```

### Step 5: Watch Replies Come In
```
http://localhost:8080/demo/dashboard.html
Navigate to: Replies & Meetings panel
```
You'll see replies appear in real-time (or every 30s poll).

---

## Monitoring & Dashboards

### Dashboard 1: Home (Pipeline Overview)
**Shows:**
- Total Leads in system
- Segments active
- Emails created
- Sent count
- Pipeline funnel: New → Sent → Replied
- Industry breakdown pie chart

### Dashboard 2: By Segment
Click a segment sidebar icon (GOV / EDU / HED / CORP)
**Shows:**
- Leads in that segment (searchable, sortable)
- Status: New / Sent / Dry-run / Replied
- All contact info: Name, Title, Company, Email, Phone

### Dashboard 3: Lead Detail
Click any lead in segment table
**Shows:**
- Full contact information
- Email preview: subject + body
- Status badge
- Date added
- Notes / source

### Dashboard 4: Replies & Meetings (NEW)
Click the message icon in sidebar
**Shows:**
- **Stat cards**: Total Replies, Interested, Unsubscribes, Meetings Booked
- **Inbox log table**: From, Company, Date, Classification, Subject
  - Interested replies show green badge with draft reply link
  - Unsubscribe replies show red badge
  - Searchable + filterable by classification
- **Pending drafts section**: Auto-generated replies waiting for your review
  - Shows: who it's for, subject, body preview
  - "Open in Email Client" button to send via Gmail
- **Scheduling tracker**: All Calendly links and booking status
  - Shows: Name, Email, Link, Status (BOOKED / Pending), Created date

---

## Scheduling Automation

### Option A: Schedule Everything Now (Recommended)

**Inbox Monitor** (every 15 minutes):
```bash
python3 create_scheduled_task.py \
  --task inbox-monitor \
  --cron "*/15 * * * *" \
  --prompt "Run inbox monitor: cd ~/apex-ai-orchestrator && python3 inbox_monitor.py --scan"
```

**Follow-Ups** (once daily at 9 AM):
```bash
python3 create_scheduled_task.py \
  --task follow-ups-daily \
  --cron "0 9 * * *" \
  --prompt "Run follow-ups: cd ~/james-outreach-harness && python3 follow_up_sequences.py --run-due"
```

### Option B: Schedule Later (After First Send)
```bash
# After you've done your first send batch, run:
cd ~/apex-ai-orchestrator
python3 inbox_monitor.py --status

# If you see "Monitoring N recipients", then:
# Schedule the tasks (commands above)
```

### What Gets Scheduled

| Task | Frequency | What It Does |
|------|-----------|---|
| **Inbox Monitor** | Every 15 min | Scans Gmail, classifies replies, auto-drafts responses |
| **Follow-Ups** | Daily 9 AM | Sends any Day 3/7/14 follow-ups that are due |

You still do this manually:
- Initial send batches (you control size, timing, company)
- Review pending drafts (before they're sent)
- Check dashboard (monitor progress)

---

## Troubleshooting

### Problem: "No sent email history found"
**Cause:** Inbox monitor has nothing to watch yet.
**Fix:** Do your first send batch, then run monitor.
```bash
cd ~/james-outreach-harness && python3 send_emails.py --run 10
cd ~/apex-ai-orchestrator && python3 inbox_monitor.py --scan
```

### Problem: "GMAIL_USER and GMAIL_APP_PASSWORD must be set in .env"
**Cause:** Missing email credentials.
**Fix:** Add to `.env` file:
```
GMAIL_USER=james@datatechdisposition.com
GMAIL_APP_PASSWORD=your_app_password
SENDER_NAME=James Ignacio
```

### Problem: Follow-ups showing as "0 due"
**Cause:** No emails have been sent yet, OR not enough days have passed.
**Fix:**
1. Send some emails today
2. Check again in 3+ days for Day 3 follow-ups to appear
```bash
python3 follow_up_sequences.py --status
```

### Problem: Dashboard shows 0 replies
**Cause:** Inbox monitor hasn't run yet, OR no replies have come in.
**Fix:**
```bash
# Test with a simulated reply
python3 inbox_monitor.py --simulate "test@example.com" --type interested

# Check dashboard again
http://localhost:8081/demo/dashboard.html → Replies & Meetings
```

### Problem: Calendly links not working
**Cause:** Calendly API token not configured.
**Fix:** Add to `.env`:
```
CALENDLY_API_TOKEN=your_token_here
```
(Until MCP fully configured, links default to public Calendly URL)

---

## Data Flow & Ledgers

### The Big Picture
```
SEND
├─ email_log.json (DTD harness)
└─ email_log.json (EZ harness)
  │
  ├─→ DECONFLICTION LAYER (orchestrator)
  │   └─ send_ledger.json (5-day cooldown, opt-outs, cross-company enforcement)
  │
  ├─→ INBOX MONITOR (every 15 min)
  │   ├─ Gmail API scan
  │   └─ inbox_ledger.json (reply classifications)
  │       ├─ interested → draft reply with Calendly link
  │       └─ unsubscribe → opt-out all companies
  │
  ├─→ CALENDLY LINKS
  │   └─ scheduling_tracker.json (links and booking status)
  │
  ├─→ FOLLOW-UP SEQUENCES (daily)
  │   ├─ email_log.json (new follow-up sends)
  │   └─ follow_up_log.json (Day 3/7/14 tracking)
  │
  └─→ DASHBOARDS (real-time)
      ├─ DTD: http://localhost:8080
      └─ EZ: http://localhost:8081
```

### Key Files Explained

| File | Location | Purpose | Updated By |
|------|----------|---------|-----------|
| `email_log.json` | Each harness | Every email sent, draft, approval | `send_emails.py` |
| `send_ledger.json` | Orchestrator | Cross-company deconfliction, opt-outs | `deconflict.py` |
| `inbox_ledger.json` | Orchestrator | All reply classifications | `inbox_monitor.py` |
| `pending_drafts.json` | Orchestrator | Auto-generated replies for review | `inbox_monitor.py` |
| `scheduling_tracker.json` | Orchestrator | Calendly links and booking status | `calendly_links.py` |
| `follow_up_log.json` | Each harness | Follow-up send history | `follow_up_sequences.py` |

### How Deconfliction Works

**Scenario:** Lead appears in both DTD and EZ Recycling databases

**Rule 1: Cross-Company Dedup**
- Lead is assigned to ONE company only (first-owner wins)
- Other company's copy is marked as "deconflicted"

**Rule 2: 5-Day Cooldown**
- If DTD sends on Day 1 → EZ can't send until Day 6
- Checked across `send_ledger.json`

**Rule 3: No Same-Day Overlap**
- If DTD sends on Day 3 → EZ can't send on Day 3
- Even if different segments, same lead

**Rule 4: Opt-Out Enforcement**
- Lead replies "unsubscribe" to DTD
- `send_ledger.json` marks as `opted_out: true`
- EZ automatically skips this lead forever

---

## Quick Commands Reference

```bash
# ═══════════════════════════════════════════
# SENDING
# ═══════════════════════════════════════════
cd ~/james-outreach-harness

# DTD: preview 10 emails
python3 send_emails.py --dry-run 10

# DTD: send 50 emails (randomized, with delays)
python3 send_emails.py --run 50

# EZ: send 25 emails
cd ~/ez-recycling-harness && python3 send_emails.py --run 25

# ═══════════════════════════════════════════
# MONITORING
# ═══════════════════════════════════════════
cd ~/apex-ai-orchestrator

# Scan for replies
python3 inbox_monitor.py --scan

# Dry-run (preview without writing)
python3 inbox_monitor.py --scan --dry-run

# Show status
python3 inbox_monitor.py --status

# Test with simulated reply
python3 inbox_monitor.py --simulate "john@example.com" --type interested

# ═══════════════════════════════════════════
# CALENDLY
# ═══════════════════════════════════════════

# Generate a link
python3 calendly_links.py --create "email@example.com" "Full Name" --company ez_recycling

# Mark as booked
python3 calendly_links.py --booked "email@example.com"

# Show tracker
python3 calendly_links.py --status

# ═══════════════════════════════════════════
# FOLLOW-UPS
# ═══════════════════════════════════════════
cd ~/james-outreach-harness

# Send due follow-ups
python3 follow_up_sequences.py --run-due

# Dry-run (preview)
python3 follow_up_sequences.py --run-due --dry-run

# Show status
python3 follow_up_sequences.py --status

# ═══════════════════════════════════════════
# DASHBOARDS
# ═══════════════════════════════════════════

# DTD (starts on port 8080)
python3 -m http.server 8080 -d ~/james-outreach-harness
# Then visit: http://localhost:8080/demo/dashboard.html

# EZ (starts on port 8081)
python3 -m http.server 8081 -d ~/ez-recycling-harness
# Then visit: http://localhost:8081/demo/dashboard.html
```

---

## Next Steps

1. **Do a dry-run send** (see "Running Your First Campaign")
2. **Check the dashboard** — verify emails logged correctly
3. **Simulate a reply** — test the full classification pipeline
4. **Schedule the recurring tasks** — set inbox monitor and follow-ups
5. **Do a real send** — launch your first actual campaign
6. **Monitor replies** — watch them come in on the dashboard

---

**Questions or issues?** All commands have `--help` flags:
```bash
python3 inbox_monitor.py --help
python3 follow_up_sequences.py --help
python3 calendly_links.py --help
```

Good luck! 🚀

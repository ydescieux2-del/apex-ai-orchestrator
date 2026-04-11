# Apex AI Autonomous Pipeline

**Status**: Ready to activate  
**Built**: 2026-04-05  
**Interval**: Daily (cron) + continuous monitoring

---

## What This Does

Fully automated lead-to-response pipeline for Apex AI Consulting:

```
Lead Discovery (Apollo.io)
    ↓
ICP Scoring & Segmentation (Claude)
    ↓
Personalized Email Generation (Claude)
    ↓
Email Delivery (Gmail SMTP)
    ↓
Response Monitoring (Gmail IMAP)
    ↓
Intelligent Follow-ups (Claude)
    ↓
Pipeline Metrics & Reports
```

**Zero daily inputs required.** Set it up, let it run.

---

## Quick Start

### 1. Set Environment Variables

```bash
# Edit ~/.env (or create it)
GMAIL_USER=ydescieux2@gmail.com
GMAIL_APP_PASSWORD=your_gmail_app_password
APOLLO_API_KEY=your_apollo_key  # Optional (free at apollo.io)
```

### 2. Verify Setup

```bash
cd ~/apex-ai-orchestrator

# Check Python dependencies
pip install anthropic requests python-dotenv

# Test authentication
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✓ .env loaded')"
```

### 3. Run Full Pipeline

```bash
# One command, everything flows
python3 apex_pipeline_orchestrator.py run

# This:
# 1. Sources 50 leads via Apollo.io
# 2. Qualifies them (ICP fit scoring)
# 3. Generates personalized emails
# 4. Sends up to 50 emails
# 5. Starts response monitoring
```

### 4. Monitor Status Anytime

```bash
python3 apex_pipeline_orchestrator.py status

# Shows:
# - Total leads sourced
# - Emails sent
# - Replies received
# - Conversion rate
# - By tier breakdown
```

---

## Components

### Lead Sourcer (`lead_sourcer_apollo.py`)
- Finds companies via Apollo.io API
- Filters by ICP: company size, industry, hiring signals
- Extracts decision makers (VP Sales, VP Growth, CRO)
- Outputs: `apex_leads.json`

### Lead Qualifier (`lead_qualifier.py`)
- Scores leads 0-100 based on ICP fit
- Segments by industry + company stage
- Generates personalized subject + body for each lead
- Uses Claude to write compelling, contextual emails
- Outputs: `apex_qualified_leads.json`, `apex_outreach_queue.json`

### Email Delivery (`apex_send_emails.py`)
- Sends from your Gmail account
- Rate-limited (default 50/day)
- Tracks sent, opened, replied status
- Logs all sends
- Outputs: `apex_send_log.json`, `apex_pipeline.json`

### Response Handler (`apex_response_handler.py`)
- Continuously monitors inbox
- Detects fraud/spam flags (manual review required)
- Matches replies to original outreach
- Generates intelligent follow-ups
- Sends follow-ups automatically
- Logs all interactions

### Orchestrator (`apex_pipeline_orchestrator.py`)
- Coordinates all steps
- Can run full pipeline in one command
- Generates reports
- Schedule-ready

---

## Scheduling (Cron)

### Daily Pipeline Run (9 AM)

```bash
# Edit crontab
crontab -e

# Add this line:
0 9 * * * cd /Users/pandorasbox/apex-ai-orchestrator && python3 apex_pipeline_orchestrator.py run >> apex_pipeline.log 2>&1
```

### Continuous Response Monitoring

```bash
# Run response handler in background
# Either manually:
nohup python3 apex_response_handler.py > response_handler.log 2>&1 &

# Or in cron every 5 minutes:
*/5 * * * * cd /Users/pandorasbox/apex-ai-orchestrator && python3 apex_response_handler.py >> response_monitor.log 2>&1
```

---

## Files Generated

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `apex_leads.json` | All sourced leads | Daily |
| `apex_qualified_leads.json` | Qualified leads with scores | Daily |
| `apex_outreach_queue.json` | Emails ready/sent | Daily |
| `apex_pipeline.json` | Pipeline metrics & stats | After each step |
| `apex_send_log.json` | Send history | Each email |
| `apex_responses.json` | Inbound replies & actions | Continuous |
| `icp_config.json` | ICP definition & pricing | Manual |

---

## Pipeline Metrics

After first run, check `apex_pipeline.json`:

```json
{
  "stats": {
    "total_outreach": 50,
    "sent": 50,
    "opened": 12,
    "replied": 3,
    "conversion_rate": 6.0
  },
  "by_tier": {
    "hot": {"sent": 20, "opened": 8, "replied": 2},
    "warm": {"sent": 20, "opened": 3, "replied": 1},
    "cool": {"sent": 10, "opened": 1, "replied": 0}
  }
}
```

---

## Customization

### Change ICP
Edit `icp_config.json`:
- Target industries
- Company size ranges
- Buyer personas
- Pain points
- Buying signals

### Change Email Tone
Edit prompts in `lead_qualifier.py` `generate_outreach_email()` function

### Change Send Limits
```bash
# Send only "hot" leads
python3 apex_send_emails.py --hot --limit 25

# Send all tiers
python3 apex_send_emails.py --limit 100
```

### Change Response Handler Interval
Edit `apex_response_handler.py`:
```python
monitor_responses(check_interval=300)  # 5 minutes (default)
monitor_responses(check_interval=600)  # 10 minutes
```

---

## Troubleshooting

**No leads found:**
- Check `APOLLO_API_KEY` is set and valid
- Run: `python3 lead_sourcer_apollo.py` to see errors

**Emails not sending:**
- Verify `GMAIL_USER` and `GMAIL_APP_PASSWORD` in .env
- Test: `python3 apex_send_emails.py` to see SMTP errors

**No replies detected:**
- Check that emails are actually being sent first
- Verify response handler is running
- Check `apex_responses.json` for logged interactions

---

## What's Next

1. **Tomorrow**: Run `python3 apex_pipeline_orchestrator.py status` to see results
2. **This week**: Refine messaging based on reply rate
3. **This month**: Adjust ICP based on what converts
4. **Scale**: Increase send limits as conversion rate improves

---

## Support

All logs available:
- Pipeline metrics: `apex_pipeline.json`
- Send errors: `apex_send_log.json`
- Replies: `apex_responses.json`
- Orchestrator logs: Run with `--verbose` flag


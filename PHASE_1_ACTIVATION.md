# DESCIEUX DIGITAL — PHASE 1 ACTIVATION GUIDE

**Date**: 2026-04-05
**System**: Autonomous Content Creator Outreach & Deal Tracking
**Target**: Descieux Digital (Von's company) - Content creation tools + consulting

---

## WHAT IS PHASE 1?

A complete, autonomous end-to-end sales pipeline that:
1. **Finds** content creators, agencies, and production companies (via Apollo.io)
2. **Reaches out** with personalized emails about the platform (Claude AI + hybrid templates)
3. **Schedules demos** with interested prospects (Calendly booking link in emails)
4. **Converts to customers** via subscription tiers or custom projects
5. **Tracks revenue** and reports on conversions and pipeline health

**Success definition**: Leads flow through autonomous system from outreach → meeting → closed subscription or project sale.

---

## SYSTEM ARCHITECTURE

### Components

**1. Lead Sourcing** (`lead_sourcer_apollo.py`)
- Searches Apollo.io for content creators, video editors, production companies, marketing agencies
- Targets job postings for: Producer, Content Creator, Creative Director, Video Editor, Motion Graphics, etc.
- Scores companies by ICP fit (50-2000 employees, content/creative/production industries)
- Outputs: `apex_leads.json`

**2. Lead Qualification** (`lead_qualifier.py`)
- Classifies leads into segments: Creator_Influencer, Production_Studio, Brand_Marketing, Agency_Content
- Scores each on 0-100 scale (hot 85+, warm 70-84, cool 55-69)
- Generates personalized emails using Claude AI + segment-specific pain points
- Outputs: `apex_outreach_queue.json`

**3. Email Delivery** (`apex_send_emails.py`)
- Sends from ydescieux2@gmail.com via Gmail SMTP
- Rate-limited: 50 emails/day (adjustable)
- Includes Calendly booking link: https://calendly.com/descieuxdigital
- Logs sends: `apex_send_log.json`

**4. Response Monitoring** (`apex_response_handler.py`)
- Monitors ydescieux2@gmail.com inbox via IMAP
- Detects fraud/spam emails
- Matches replies to original outreach
- Generates contextual follow-ups with Claude
- Logs responses: `apex_responses.json`

**5. Deal Tracking** (`deal_tracker.py`)
- Creates deal record for each outreach sent
- Tracks progression: outreach → demo scheduled → demo completed → subscribed/project
- Records subscription tier (Creator Essentials $249, Creator Pro $699, Studio Custom custom)
- Tracks custom projects (one-time revenue)
- Outputs: `deals.json`, `revenue_summary.json`

**6. Reporting & Orchestration** (`apex_pipeline_orchestrator.py`)
- Runs full pipeline: source → qualify → send → monitor
- Generates deal funnel report (outreach → demos → conversions)
- Calculates MRR/ARR, conversion rates, average deal value
- Provides actionable next steps

---

## CONFIGURATION

### `.env` File (Required)

```
APOLLO_API_KEY=sU1EQkHTcix236QmmHX1gA
GMAIL_USER=ydescieux2@gmail.com
GMAIL_APP_PASSWORD=sbze lzhx gyvk quum
SENDER_NAME=Von Descieux
```

**Status**: ✓ Already configured in apex-ai-orchestrator/.env

### ICP Configuration (`icp_config.json`)

- **Target industries**: Content Creation, Production, Creative Agencies, Marketing Agencies, Brands, Entertainment
- **Buyer personas**: Content Creator, Production Director, Creative Director, Marketing Manager
- **Company size**: 1-500 employees (solopreneurs to mid-size agencies)
- **Pricing tiers**:
  - Creator Essentials: $249/mo (20 shorts/month, TTS voiceover)
  - Creator Pro: $699/mo (unlimited shorts, premium effects, batch processing)
  - Studio Custom: $2K-$10K/mo (custom work with Von, white-label, API access)

**Status**: ✓ Updated for content creation targeting

### Calendly Integration

- Link: https://calendly.com/descieuxdigital
- Automatically included in all outreach emails
- Prospects can book demo slots directly
- Demo notes → deal tracker → conversion tracking

**Status**: ✓ Ready (configure Calendly availability separately)

---

## RUNNING THE SYSTEM

### Full Pipeline (Recommended)

```bash
cd ~/apex-ai-orchestrator
python3 apex_pipeline_orchestrator.py run
```

**What happens**:
1. Sources 50 new leads from Apollo.io
2. Qualifies and generates personalized emails
3. Sends up to 50 emails
4. Monitors inbox for replies (continuous background)
5. Prints deal funnel and revenue report

**Output**: Deal status → revenue report with MRR, ARR, conversions, avg deal value

### Individual Commands

```bash
# 1. Source leads only
python3 lead_sourcer_apollo.py

# 2. Qualify & generate emails
python3 lead_qualifier.py

# 3. Send emails
python3 apex_send_emails.py --limit 50

# 4. Monitor inbox (continuous)
python3 apex_response_handler.py

# 5. Track deals & revenue
python3 deal_tracker.py

# 6. Check pipeline status
python3 apex_pipeline_orchestrator.py status
```

### Scheduling with Cron

```bash
# Daily at 9am (source → qualify → send)
0 9 * * * cd ~/apex-ai-orchestrator && python3 apex_pipeline_orchestrator.py run >> /tmp/descieux_pipeline.log 2>&1

# Every 5 minutes (monitor inbox for replies)
*/5 * * * * cd ~/apex-ai-orchestrator && python3 apex_response_handler.py >> /tmp/descieux_monitor.log 2>&1

# Every hour (update deal tracking & revenue)
0 * * * * cd ~/apex-ai-orchestrator && python3 deal_tracker.py >> /tmp/descieux_deals.log 2>&1
```

---

## EXPECTED RESULTS (First 30 Days)

| Metric | Target | Notes |
|--------|--------|-------|
| Leads sourced | 1,500-2,000 | Apollo.io searches + manual additions |
| Emails sent | 1,200-1,500 | 50/day × 25 business days, limit-adjusted |
| Reply rate | 3-5% | Industry standard for cold outreach |
| Replies | 36-75 | From replied-to leads |
| Demos scheduled | 15-30 | Via Calendly, from replies |
| Demo conversion | 40-60% | To subscription or project |
| Conversions | 6-18 | Subscriptions or custom projects |
| MRR | $1,500-$12,000 | Depends on tier mix (Essentials, Pro, Custom) |
| ARR | $18,000-$144,000 | MRR × 12 |

---

## DEAL TRACKING WORKFLOW

### Stage 1: Outreach Sent
- Lead sourced, qualified, email generated
- Deal record created with `status: "outreach_sent"`
- Email sent with Calendly link

### Stage 2: Demo Scheduled
- Prospect clicks Calendly link and books slot
- **Manual step**: Update deal with `schedule_demo(deal_id, demo_date, calendly_link)`
- Status: `"demo_scheduled"`

### Stage 3: Demo Completed
- After demo call, record outcome
- **Manual step**: `complete_demo(deal_id, outcome, notes)`
- Outcomes: "interested", "not_interested", "need_more_info"

### Stage 4: Conversion
- If interested, move to subscription or project
- **Manual step**: Either:
  - `convert_to_subscription(deal_id, tier)` → tracks MRR
  - `start_custom_project(deal_id, project_name, value)` → tracks one-time revenue
- Status: `"subscribed"` or `"project_in_progress"`

### Stage 5: Closed Deal
- Subscription active or project completed
- **Manual step**: `close_deal(deal_id)`
- Status: `"closed"`

---

## MANUAL INTEGRATION POINTS

The autonomous system handles: sourcing → outreach → replies → follow-ups

**You need to manually handle**:
1. **Demo scheduling** - Prospect books via Calendly → you confirm in deal_tracker
2. **Demo completion** - After call → record outcome in deal tracker
3. **Subscription onboarding** - Convert interested leads to paying subscribers
4. **Custom project scoping** - For "Studio Custom" tier leads

**Semi-automated**:
- Demo reminders (set Calendly reminders)
- Follow-up sequences (handled by response_handler.py)
- Invoice/payment processing (integrate Stripe/payment processor separately)

---

## KEY FILES

| File | Purpose | Status |
|------|---------|--------|
| `.env` | Credentials & API keys | ✓ Configured |
| `icp_config.json` | ICP, personas, pricing, messaging | ✓ Updated for content creators |
| `lead_sourcer_apollo.py` | Apollo.io integration | ✓ Ready (test with live key) |
| `lead_qualifier.py` | Qualification & email generation | ✓ Updated for content messaging |
| `apex_send_emails.py` | Gmail SMTP delivery | ✓ Ready |
| `apex_response_handler.py` | IMAP monitoring & follow-ups | ✓ Ready |
| `deal_tracker.py` | Deal/revenue tracking | ✓ New |
| `apex_pipeline_orchestrator.py` | Orchestration & reporting | ✓ Updated with deal/revenue reporting |
| `apex_leads.json` | Sourced leads | ⊘ Generated on first run |
| `apex_outreach_queue.json` | Qualified leads ready to send | ⊘ Generated on first run |
| `apex_send_log.json` | Send history | ⊘ Generated on first send |
| `apex_responses.json` | Reply tracking | ⊘ Generated on first reply |
| `deals.json` | Deal funnel tracking | ⊘ Generated on first send |
| `revenue_summary.json` | MRR/ARR/conversion metrics | ⊘ Generated on first conversion |

---

## BLOCKERS & NEXT STEPS

### Current Status: ✓ Ready for Testing

**Before going live**:
1. ✓ Apollo.io API key configured (verify it's not 403)
2. ✓ Gmail credentials working (IMAP/SMTP)
3. ✓ Calendly account linked in emails
4. ⊘ Test with sample data (run `python3 lead_qualifier.py` with apex_leads.json)
5. ⊘ Send test email batch
6. ⊘ Verify Calendly integration in responses
7. ⊘ Schedule cron jobs

### Going Live (Phase 1 Deployment)

```bash
# 1. Test Apollo sourcing
python3 lead_sourcer_apollo.py

# 2. Qualify test leads
python3 lead_qualifier.py

# 3. Test email sending (small batch)
python3 apex_send_emails.py --limit 5

# 4. Check dashboard
python3 apex_pipeline_orchestrator.py status

# 5. Enable cron scheduler
# Add cron jobs (see section above)

# 6. Monitor first run
tail -f /tmp/descieux_pipeline.log
```

---

## PHASE 1 SUCCESS METRICS

**Go-live criteria**:
- [ ] Apollo API working (sourced ≥50 leads)
- [ ] Emails sending (≥5 test sends successful)
- [ ] Responses being monitored (inbox check working)
- [ ] Calendly links clickable in emails
- [ ] Deal tracker recording conversions
- [ ] Revenue summary calculating correctly
- [ ] Cron jobs scheduled

**Phase 1 complete when**:
- [ ] First subscription signed (Creator Essentials or Pro)
- [ ] First custom project deal started
- [ ] MRR ≥ $500 (indicates product-market fit)
- [ ] Conversion rate ≥ 2% (sourceable and scalable)

---

## REVENUE CALCULATION

Once deals start converting, the system calculates:

```
MRR = Monthly recurring revenue from active subscriptions
ARR = MRR × 12 (annual projection)

Conversion rate = (Subscriptions + Projects) / Total Leads

Avg deal value = Total Revenue / Total Conversions

Expansion revenue = Upgrades from Essentials → Pro → Custom
Churn rate = Cancellations / Active subscriptions
```

---

## NOTES FOR VON

- **Descieux Digital is your test bed**: If this works for your own company, you'll have proven proof of concept for DataTech and ZS Recycling
- **Focus on demos first**: Don't worry about 100% automation yet; schedule demos, see what works
- **Iterate on messaging**: If reply rate is low, update icp_config.json email templates
- **Track what converts**: Which segments (Creator vs. Agency) convert best? Which value props work?
- **Phase 2 opportunity**: Once Phase 1 works, apply same system to James/DataTech and ZS Recycling with their leads


# APEX AI Orchestrator — Quick Start (5 Minutes)

## 1. Do a Test Send

```bash
cd ~/james-outreach-harness

# Preview 5 emails (no actual send)
python3 send_emails.py --dry-run 5
```

✅ You should see 5 emails logged to screen. Hit Enter, then go to next step.

## 2. Send Them

```bash
# Actually send (randomized, 90-240s delay between)
python3 send_emails.py --run 5

# Watch it work...
```

✅ You'll see "✅ Email sent to john@example.com" for each one.

## 3. Check the Dashboard

```bash
# In a new terminal tab, start the DTD server (if not already running)
cd ~/james-outreach-harness
python3 -m http.server 8080 &

# Open in browser
# http://localhost:8080/demo/dashboard.html
```

✅ You should see "Sent: 5" in the stat cards.

## 4. Test the Inbox Monitor

```bash
cd ~/apex-ai-orchestrator

# Simulate someone interested
python3 inbox_monitor.py --simulate "john@test.com" --type interested
```

✅ You should see:
- "Draft reply generated"
- "Logged to inbox_ledger.json"

Go back to dashboard → **Replies & Meetings** tab
✅ You should see the simulated reply in the inbox log.

## 5. Schedule Automation (Optional)

To run inbox monitor automatically every 15 minutes:

```bash
cd ~/apex-ai-orchestrator && python3 inbox_monitor.py --scan
```

For now, this runs manually. To schedule it later, see USER_GUIDE.md.

---

## Dashboards

| Dashboard | Port | URL |
|-----------|------|-----|
| DataTech Disposition | 8080 | http://localhost:8080/demo/dashboard.html |
| EZ Recycling | 8081 | http://localhost:8081/demo/dashboard.html |

## Key Commands (Copy/Paste)

```bash
# Send emails
cd ~/james-outreach-harness && python3 send_emails.py --run 10

# Check for replies
cd ~/apex-ai-orchestrator && python3 inbox_monitor.py --scan

# See what follow-ups are due
cd ~/james-outreach-harness && python3 follow_up_sequences.py --status

# Show all pending drafts
cd ~/apex-ai-orchestrator && python3 inbox_monitor.py --status

# Create a Calendly link
cd ~/apex-ai-orchestrator && python3 calendly_links.py --create "email@example.com" "Name" --company ez_recycling
```

## What Happens Next

1. **Replies come in** → Inbox monitor classifies them
2. **"Interested" replies** → Auto-draft response with Calendly link
3. **"Unsubscribe" replies** → Opt-out across all companies
4. **Day 3, 7, 14** → Follow-up emails sent automatically
5. **Prospect books** → Calendly link clicked → Meetings Booked count updates

---

## Still Here?

Read the full **USER_GUIDE.md** for:
- How deconfliction works (5-day cooldown, same-day blocking)
- All data flow and ledger files
- Troubleshooting
- Scheduling setup

Now go send some emails! 🚀

#!/usr/bin/env python3
"""
Apex AI Email Delivery System
Sends personalized outreach emails from Apex AI account.
Tracks sends, opens, clicks, replies in pipeline database.

Uses Gmail IMAP/SMTP with app password.
"""

import os
import json
import time
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")  # ydescieux2@gmail.com
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
OUTREACH_QUEUE = "apex_outreach_queue.json"
PIPELINE_DB = "apex_pipeline.json"
SEND_LOG = "apex_send_log.json"

# Configuration
DAILY_SEND_LIMIT = 50
FROM_NAME = "Von Descieux"
FROM_EMAIL = "Von@DescieuxDigital.com"  # Or use GMAIL_USER


def load_json(filename: str, default=None):
    """Load JSON."""
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            return default if default is not None else {}
    return default if default is not None else {}


def save_json(filename: str, data):
    """Save JSON."""
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def log_send(outreach_id: str, recipient: str, status: str, details: str = ""):
    """Log email send."""
    log = load_json(SEND_LOG, [])
    log.append({
        "timestamp": datetime.now().isoformat(),
        "outreach_id": outreach_id,
        "recipient": recipient,
        "status": status,
        "details": details
    })
    save_json(SEND_LOG, log)


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send email via Gmail SMTP."""
    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        message = MIMEText(body)
        message["to"] = to_address
        message["from"] = f"{FROM_NAME} <{GMAIL_USER}>"
        message["subject"] = subject
        
        smtp.send_message(message)
        smtp.quit()
        
        return True
    except Exception as e:
        print(f"❌ SMTP Error: {str(e)}")
        return False


def send_outreach_batch(limit: int = DAILY_SEND_LIMIT, tier_filter: str = None) -> int:
    """
    Send outreach emails from queue.
    
    Args:
        limit: Max emails to send today
        tier_filter: Send only "hot", "warm", or "cool" (None = all)
    """
    print("\n" + "="*70)
    print("📧 APEX AI EMAIL DELIVERY")
    print("="*70 + "\n")
    
    if not GMAIL_APP_PASSWORD:
        print("❌ Gmail app password not set in .env")
        print("   Add: GMAIL_APP_PASSWORD=your_app_password\n")
        return 0
    
    # Load queue
    queue = load_json(OUTREACH_QUEUE, [])
    if not queue:
        print("❌ No outreach items in queue. Run lead_qualifier.py first.\n")
        return 0
    
    # Filter unsent items
    to_send = [item for item in queue if not item.get("sent")]
    
    # Filter by tier if specified
    if tier_filter:
        to_send = [item for item in to_send if item.get("tier") == tier_filter]
    
    # Apply limit
    to_send = to_send[:limit]
    
    print(f"Sending {len(to_send)} emails ({tier_filter or 'all'} tier)\n")
    
    sent_count = 0
    
    for item in to_send:
        email = item.get("lead_email")
        name = item.get("lead_name")
        company = item.get("company")
        subject = item.get("subject")
        body = item.get("body")
        outreach_id = item.get("id")
        
        print(f"→ {name} @ {company}")
        
        # Send email
        if send_email(email, subject, body):
            # Update queue item
            item["sent"] = True
            item["sent_at"] = datetime.now().isoformat()
            sent_count += 1
            
            log_send(outreach_id, email, "sent", subject)
            print(f"  ✓ Sent\n")
        else:
            log_send(outreach_id, email, "failed", "SMTP error")
            print(f"  ❌ Failed\n")
        
        # Rate limiting (don't spam)
        time.sleep(1)
    
    # Save updated queue
    save_json(OUTREACH_QUEUE, queue)
    
    # Update pipeline database
    update_pipeline_db(queue)
    
    print(f"{'='*70}")
    print(f"✅ SEND COMPLETE: {sent_count} emails sent")
    print(f"{'='*70}\n")
    
    return sent_count


def update_pipeline_db(outreach_items: list):
    """Update central pipeline database."""
    pipeline = load_json(PIPELINE_DB, {
        "business": "Apex AI",
        "updated_at": None,
        "stats": {
            "total_outreach": 0,
            "sent": 0,
            "opened": 0,
            "replied": 0,
            "conversion_rate": 0
        },
        "by_segment": {},
        "by_tier": {
            "hot": {"sent": 0, "opened": 0, "replied": 0},
            "warm": {"sent": 0, "opened": 0, "replied": 0},
            "cool": {"sent": 0, "opened": 0, "replied": 0}
        }
    })
    
    # Update stats
    sent = sum(1 for item in outreach_items if item.get("sent"))
    opened = sum(1 for item in outreach_items if item.get("opened"))
    replied = sum(1 for item in outreach_items if item.get("replied"))
    
    pipeline["stats"]["total_outreach"] = len(outreach_items)
    pipeline["stats"]["sent"] = sent
    pipeline["stats"]["opened"] = opened
    pipeline["stats"]["replied"] = replied
    
    if sent > 0:
        pipeline["stats"]["conversion_rate"] = round((replied / sent) * 100, 1)
    
    # By tier
    for tier in ["hot", "warm", "cool"]:
        tier_items = [item for item in outreach_items if item.get("tier") == tier]
        pipeline["by_tier"][tier]["sent"] = sum(1 for item in tier_items if item.get("sent"))
        pipeline["by_tier"][tier]["opened"] = sum(1 for item in tier_items if item.get("opened"))
        pipeline["by_tier"][tier]["replied"] = sum(1 for item in tier_items if item.get("replied"))
    
    pipeline["updated_at"] = datetime.now().isoformat()
    
    save_json(PIPELINE_DB, pipeline)


if __name__ == "__main__":
    import sys
    
    # Command line options
    tier = None
    limit = DAILY_SEND_LIMIT
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--hot", "--warm", "--cool"]:
            tier = sys.argv[1].replace("--", "")
        if "--limit" in sys.argv:
            idx = sys.argv.index("--limit")
            limit = int(sys.argv[idx + 1])
    
    send_outreach_batch(limit=limit, tier_filter=tier)

#!/usr/bin/env python3
"""
Apex AI Response Handler
Monitors inbox for replies to outreach emails.
Logs interactions, generates follow-ups, tracks pipeline progression.

Uses IMAP to monitor ydescieux2@gmail.com for inbound replies.
"""

import os
import json
import time
import imaplib
from datetime import datetime
from email.header import decode_header
from email.mime.text import MIMEText
import smtplib
from dotenv import load_dotenv
import anthropic

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "")
OUTREACH_QUEUE = "apex_outreach_queue.json"
PIPELINE_DB = "apex_pipeline.json"
RESPONSES_LOG = "apex_responses.json"

# Fraud detection
FRAUD_KEYWORDS = [
    "wire", "transfer money", "urgent", "verify account", "click immediately",
    "limited time", "claim prize", "upfront fee", "payment", "confirm password"
]


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


def authenticate_imap():
    """Connect to Gmail IMAP."""
    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com")
        imap.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        return imap
    except Exception as e:
        print(f"❌ IMAP Auth failed: {e}")
        return None


def check_for_fraud(sender: str, subject: str, body: str) -> list:
    """Detect fraud indicators."""
    flags = []
    text = f"{sender} {subject} {body}".lower()
    
    for keyword in FRAUD_KEYWORDS:
        if keyword in text:
            flags.append(keyword)
    
    return flags


def generate_followup(prospect_name: str, original_subject: str, response_body: str) -> str:
    """Generate intelligent follow-up using Claude."""
    client = anthropic.Anthropic()
    
    prompt = f"""You are Von Descieux, Founder of Apex AI Consulting.

A prospect replied to your outreach email:
- Name: {prospect_name}
- Original: {original_subject}
- Their response: {response_body}

Generate a brief, intelligent follow-up that:
1. Acknowledges their specific response
2. Answers their implicit questions
3. Offers the next step (call, demo, etc.)
4. 2-3 sentences max
5. End with: "Best, Von"

Respond with ONLY the email body text."""

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=200,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    return message.content[0].text


def send_email(to_address: str, subject: str, body: str) -> bool:
    """Send follow-up email."""
    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        
        message = MIMEText(body)
        message["to"] = to_address
        message["from"] = GMAIL_USER
        message["subject"] = subject
        
        smtp.send_message(message)
        smtp.quit()
        return True
    except Exception as e:
        print(f"❌ Send failed: {e}")
        return False


def log_response(lead_email: str, sender: str, subject: str, body: str, action: str, fraud_flags: list = None):
    """Log inbound response."""
    responses = load_json(RESPONSES_LOG, [])
    responses.append({
        "timestamp": datetime.now().isoformat(),
        "from": sender,
        "to": lead_email,
        "subject": subject,
        "body_preview": body[:100],
        "action": action,
        "fraud_flags": fraud_flags or [],
        "requires_review": len(fraud_flags or []) > 0
    })
    save_json(RESPONSES_LOG, responses)


def get_unread_replies(imap) -> list:
    """Get unread emails from outreach recipients."""
    try:
        imap.select("INBOX")
        status, messages = imap.search(None, "UNSEEN")
        
        if status == "OK":
            return messages[0].split()
        return []
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return []


def extract_message(imap, msg_id: bytes) -> dict:
    """Extract message details."""
    try:
        status, msg_data = imap.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return None
        
        import email
        message = email.message_from_bytes(msg_data[0][1])
        
        sender = message.get("From", "Unknown")
        subject = message.get("Subject", "No Subject")
        
        # Decode subject
        if isinstance(subject, str):
            decoded = decode_header(subject)
            subject = "".join(word.decode(encoding or "utf-8") if isinstance(word, bytes) else word for word, encoding in decoded)
        
        # Extract body
        body = ""
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
        else:
            body = message.get_payload(decode=True).decode("utf-8", errors="ignore")
        
        return {"id": msg_id.decode(), "sender": sender, "subject": subject, "body": body}
    except Exception as e:
        print(f"Error parsing message: {e}")
        return None


def find_matching_outreach(sender_email: str) -> dict:
    """Find matching outreach item by sender email."""
    queue = load_json(OUTREACH_QUEUE, [])
    
    for item in queue:
        if sender_email.lower() in item.get("lead_email", "").lower():
            return item
    
    return None


def monitor_responses(check_interval: int = 300):
    """
    Main monitoring loop.
    Checks every 5 minutes by default.
    """
    print("\n" + "="*70)
    print("📬 APEX AI RESPONSE HANDLER")
    print("="*70)
    print(f"Monitoring: {GMAIL_USER}")
    print(f"Check interval: {check_interval}s\n")
    
    while True:
        try:
            imap = authenticate_imap()
            if not imap:
                print(f"⏳ Retrying in {check_interval}s...")
                time.sleep(check_interval)
                continue
            
            # Get unread messages
            unread = get_unread_replies(imap)
            
            if unread:
                print(f"📧 Found {len(unread)} unread message(s)\n")
                
                for msg_id in unread:
                    msg = extract_message(imap, msg_id)
                    if not msg:
                        continue
                    
                    sender = msg["sender"]
                    subject = msg["subject"]
                    body = msg["body"]
                    
                    print(f"→ From: {sender}")
                    print(f"  Subject: {subject}")
                    
                    # Check for fraud
                    fraud_flags = check_for_fraud(sender, subject, body)
                    
                    if fraud_flags:
                        print(f"  ⚠️  FLAGGED: {fraud_flags}")
                        log_response(GMAIL_USER, sender, subject, body, "flagged", fraud_flags)
                    else:
                        # Find matching outreach
                        outreach = find_matching_outreach(sender)
                        
                        if outreach:
                            print(f"  ✓ Matched to outreach for {outreach.get('lead_name')}")
                            
                            # Generate follow-up
                            followup = generate_followup(
                                outreach.get('lead_name'),
                                outreach.get('subject'),
                                body
                            )
                            
                            # Send follow-up
                            if send_email(sender, f"Re: {subject}", followup):
                                print(f"  ✓ Follow-up sent\n")
                                log_response(GMAIL_USER, sender, subject, body, "replied", [])
                                
                                # Update outreach status
                                outreach["replied"] = True
                                outreach["replied_at"] = datetime.now().isoformat()
                                save_json(OUTREACH_QUEUE, [o for o in load_json(OUTREACH_QUEUE, []) if o.get('id') != outreach.get('id')] + [outreach])
                            else:
                                print(f"  ❌ Failed to send follow-up\n")
                        else:
                            print(f"  ❓ No matching outreach found\n")
                            log_response(GMAIL_USER, sender, subject, body, "unmatched", [])
            
            imap.close()
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print(f"⏳ Next check at {datetime.now().isoformat()}")
        time.sleep(check_interval)


if __name__ == "__main__":
    monitor_responses(check_interval=300)

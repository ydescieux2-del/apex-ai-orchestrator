#!/usr/bin/env python3
"""
Apex AI Lead Qualifier & Outreach Generator
Qualifies leads by ICP fit and generates personalized outreach sequences.

Pipeline:
1. Load leads from lead_sourcer_apollo.py
2. Qualify by ICP match + engagement readiness
3. Segment by industry + company stage
4. Generate personalized subject + body for each
5. Output to outreach queue
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict
import anthropic

# File I/O
LEADS_FILE = "apex_leads.json"
OUTREACH_QUEUE = "apex_outreach_queue.json"
QUALIFIED_LEADS = "apex_qualified_leads.json"
LOG_FILE = "qualifier_log.json"

# Load ICP config
with open("icp_config.json", "r") as f:
    CONFIG = json.load(f)
    ICP = CONFIG["icp"]
    VALUE_PROPS = CONFIG["pricing"]


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


def log_action(action: str, details: str, status: str = "info"):
    """Log action."""
    log = load_json(LOG_FILE, [])
    log.append({
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
        "status": status
    })
    save_json(LOG_FILE, log)
    print(f"[{status.upper()}] {action}: {details}")


def qualify_lead(lead: dict) -> dict:
    """
    Score lead by readiness for outreach.
    Factors: ICP fit, decision maker title, company growth signals
    """
    score = lead.get("icp_score", 0)
    
    # Boost score if hiring signals present
    if lead.get("hiring_signals"):
        score += 15
    
    # Boost score for growth-stage funding
    funding = lead.get("funding_stage", "").lower()
    if any(stage in funding for stage in ["series b", "growth", "late stage"]):
        score += 10
    
    # Decision maker bonus
    title = lead.get("title", "").lower()
    if any(keyword in title for keyword in ["vp", "cro", "chief", "director"]):
        score += 5
    
    # Determine qualification tier
    if score >= 85:
        tier = "hot"
    elif score >= 70:
        tier = "warm"
    elif score >= 55:
        tier = "cool"
    else:
        tier = "unqualified"
    
    return {
        **lead,
        "qualification_score": min(round(score, 1), 100),
        "qualification_tier": tier,
        "qualified": tier in ["hot", "warm"],
        "qualified_at": datetime.now().isoformat() if tier in ["hot", "warm"] else None
    }


def segment_lead(lead: dict) -> str:
    """Determine outreach segment based on industry + role."""
    industry = lead.get("industry", "").lower()
    title = lead.get("title", "").lower()
    company_size = lead.get("company_size", 0)

    # Segment by role/title first (most reliable indicator)
    if any(word in title for word in ["creator", "influencer", "streamer", "youtuber", "tiktok"]):
        return "Creator_Influencer"

    if any(word in title for word in ["production", "director", "studio", "creative director", "head of"]):
        if "production" in title or "studio" in title or "creative" in title:
            return "Production_Studio"
        return "Agency_Content"

    if any(word in title for word in ["brand manager", "marketing director", "content manager", "social media"]):
        if company_size >= 200:
            return "Brand_Marketing"
        else:
            return "Creator_Influencer"

    # Segment by industry second
    if "production" in industry or "film" in industry or "entertainment" in industry:
        return "Production_Studio"

    if "agency" in industry or "creative" in industry or "marketing" in industry:
        return "Agency_Content"

    if "content" in industry or "media" in industry or "streaming" in industry:
        if company_size >= 100:
            return "Production_Studio"
        else:
            return "Creator_Influencer"

    if "brand" in industry or "cpg" in industry or "retail" in industry or "ecommerce" in industry:
        return "Brand_Marketing"

    # Default fallback based on size
    if company_size >= 200:
        return "Agency_Content"
    elif company_size >= 50:
        return "Brand_Marketing"
    else:
        return "Creator_Influencer"


def generate_outreach_email(lead: dict, segment: str) -> dict:
    """Generate personalized outreach email using Claude."""
    client = anthropic.Anthropic()

    # Map segment to key messaging
    segment_messaging = {
        "Creator_Influencer": "content creation takes too much time, and you're barely keeping up",
        "Production_Studio": "projects take weeks to complete due to editing and effects work bottlenecks",
        "Brand_Marketing": "producing enough video content for campaigns stretches your budget and timelines",
        "Agency_Content": "managing multiple clients' content demands without scaling your team is unsustainable"
    }

    pain_point = segment_messaging.get(segment, "content production is your biggest bottleneck")

    prompt = f"""You are Von Descieux, Founder of Descieux Digital - a platform for professional content creation.

Prospect profile:
- Name: {lead.get('first_name')} {lead.get('last_name')}
- Title: {lead.get('title')}
- Company: {lead.get('company_name')}
- Industry: {lead.get('industry')}
- Company size: {lead.get('company_size')} employees
- Segment: {segment}

Their likely pain point: {pain_point}

Your task: Write a SHORT, personalized outreach email that:

1. Opens with ONE specific observation about their content creation challenges (be precise to their role)
2. Briefly mention how Descieux Digital solves it (professional quality, 10x faster, one integrated platform)
3. Offer a specific demo/walkthrough for their use case
4. Keep it to 4-5 sentences max
5. Conversational but professional tone
6. End with "Quick demo this week?" and your name

IMPORTANT: Focus on their specific pain point, not generic benefits. Show you know what content creators/studios actually struggle with.

Respond with ONLY the email body text."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=300,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Generate subject
    subject_prompt = f"""Generate a short, compelling email subject line for {lead.get('first_name')} at {lead.get('company_name')}.

Context: {lead.get('title')} in {lead.get('industry')}. Main pain: {pain_point}

The email is inviting them to see how Descieux Digital speeds up content creation.

Respond with ONLY the subject line. Max 8 words. Make it relevant to their specific role/pain."""

    subject_message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=20,
        messages=[
            {"role": "user", "content": subject_prompt}
        ]
    )

    return {
        "subject": subject_message.content[0].text.strip(),
        "body": message.content[0].text.strip(),
        "personalized": True
    }


def create_outreach_item(lead: dict, email: dict) -> dict:
    """Create outreach queue item."""
    segment = segment_lead(lead)
    
    return {
        "id": lead.get("id"),
        "lead_email": lead.get("email"),
        "lead_name": f"{lead.get('first_name')} {lead.get('last_name')}",
        "company": lead.get("company_name"),
        "title": lead.get("title"),
        "segment": segment,
        "qualification_score": lead.get("qualification_score"),
        "tier": lead.get("qualification_tier"),
        "subject": email.get("subject"),
        "body": email.get("body"),
        "created_at": datetime.now().isoformat(),
        "scheduled_send": None,
        "sent": False,
        "opened": False,
        "replied": False
    }


def qualify_and_segment_batch(min_score: float = 60.0) -> int:
    """
    Qualify all leads and generate outreach emails.
    Returns count of outreach items created.
    """
    print("\n" + "="*70)
    print("🎯 APEX AI LEAD QUALIFIER")
    print("="*70 + "\n")
    
    # Load leads
    all_leads = load_json(LEADS_FILE, [])
    if not all_leads:
        print("❌ No leads found. Run lead_sourcer_apollo.py first.\n")
        return 0
    
    print(f"📊 Qualifying {len(all_leads)} leads...\n")
    
    # Qualify leads
    qualified = []
    for lead in all_leads:
        if lead.get("outreach_status") == "sent":
            continue  # Skip already sent
        
        q_lead = qualify_lead(lead)
        if q_lead.get("qualified"):
            qualified.append(q_lead)
    
    print(f"✓ {len(qualified)} leads qualified\n")
    
    # Generate outreach for qualified leads
    outreach_queue = []
    for i, lead in enumerate(qualified, 1):
        segment = segment_lead(lead)
        print(f"  {i}. {lead.get('first_name')} {lead.get('last_name')} @ {lead.get('company_name')}")
        print(f"     Score: {lead.get('qualification_score')}/100 | Tier: {lead.get('qualification_tier')} | Segment: {segment}")
        
        try:
            email = generate_outreach_email(lead, segment)
            outreach_item = create_outreach_item(lead, email)
            outreach_queue.append(outreach_item)
            print(f"     ✓ Email generated\n")
            
            # Rate limit Claude calls
            time.sleep(0.5)
        except Exception as e:
            log_action("generate_email", f"{lead.get('email')}: {str(e)}", "error")
            print(f"     ❌ Error: {str(e)}\n")
    
    # Save outputs
    save_json(QUALIFIED_LEADS, qualified)
    save_json(OUTREACH_QUEUE, outreach_queue)
    
    log_action("qualifier_complete", f"Qualified {len(qualified)} leads, generated {len(outreach_queue)} emails", "success")
    
    print(f"{'='*70}")
    print(f"✅ QUALIFICATION COMPLETE")
    print(f"   Qualified leads: {len(qualified)}")
    print(f"   Outreach emails: {len(outreach_queue)}")
    print(f"   Outputs: {QUALIFIED_LEADS}, {OUTREACH_QUEUE}")
    print(f"{'='*70}\n")
    
    return len(outreach_queue)


if __name__ == "__main__":
    qualify_and_segment_batch(min_score=60.0)

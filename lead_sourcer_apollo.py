#!/usr/bin/env python3
"""
Descieux Digital Lead Sourcer - Apollo.io Integration
Finds content creators, agencies, and production companies matching ICP.

Uses Apollo.io API to search for:
- Content creation / production / creative agencies
- Companies hiring video editors, motion graphics, content creators
- Decision makers (Creative Directors, Production Heads, Content Managers, Influencers)

Outputs verified leads to apex_leads.json
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
import requests
import anthropic

load_dotenv()

# Apollo.io API key (sign up free at apollo.io)
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY", "")

# File outputs
LEADS_FILE = "apex_leads.json"
DEDUP_FILE = "apex_leads_dedup.json"
LOG_FILE = "sourcer_log.json"

# Load ICP config
with open("icp_config.json", "r") as f:
    ICP = json.load(f)["icp"]

# Search queries targeting buying signals
SEARCH_QUERIES = [
    "video editor hiring",
    "content creator hiring",
    "motion graphics hiring",
    "production company",
    "creative agency",
    "social media content",
    "digital marketing agency",
    "influencer hiring",
    "animation studio",
    "freelance video editor wanted"
]

# Job title keywords that indicate buying signals
HIRING_KEYWORDS = [
    "Content Creator", "Production Director", "Creative Director",
    "Video Editor", "Motion Graphics Designer", "Studio Head",
    "Creative Manager", "Head of Production", "Content Manager",
    "Director of Marketing", "Brand Manager", "Social Media Manager",
    "VP Creative", "VP Production", "Producer", "Animator",
    "Filmmaker", "Director of Content"
]


def log_action(action: str, details: str, status: str = "info"):
    """Log sourcing activity."""
    log = load_json(LOG_FILE, [])
    log.append({
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "details": details,
        "status": status
    })
    save_json(LOG_FILE, log)
    print(f"[{status.upper()}] {action}: {details}")


def load_json(filename: str, default=None):
    """Load JSON file."""
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except:
            return default if default is not None else {}
    return default if default is not None else {}


def save_json(filename: str, data):
    """Save JSON file."""
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)


def search_apollo_companies(query: str, limit: int = 20) -> List[dict]:
    """
    Search Apollo.io for companies matching criteria.
    Requires APOLLO_API_KEY env variable.
    """
    if not APOLLO_API_KEY:
        log_action("apollo_search", f"No API key set. Get free key at apollo.io", "warning")
        return []
    
    try:
        # Apollo.io v1 endpoint
        url = "https://api.apollo.io/v1/mixed_companies/search"
        
        params = {
            "q": query,
            "per_page": limit,
            "page": 1
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": APOLLO_API_KEY
        }
        
        response = requests.post(url, json=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        companies = data.get("companies", [])
        
        log_action("apollo_search", f"Found {len(companies)} companies for '{query}'", "success")
        return companies
        
    except Exception as e:
        log_action("apollo_search", f"Error: {str(e)}", "error")
        return []


def search_apollo_contacts(company_id: str, limit: int = 10) -> List[dict]:
    """Search Apollo.io for decision makers at a company."""
    if not APOLLO_API_KEY:
        return []
    
    try:
        url = "https://api.apollo.io/v1/contacts/search"
        
        params = {
            "organization_id": company_id,
            "per_page": limit,
            "page": 1
        }
        
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": APOLLO_API_KEY
        }
        
        response = requests.post(url, json=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        contacts = data.get("contacts", [])
        
        return contacts
        
    except Exception as e:
        log_action("apollo_contacts", f"Error for company {company_id}: {str(e)}", "error")
        return []


def score_company_icp_fit(company: dict) -> float:
    """
    Score company 0-100 on ICP fit.
    Factors: size, industry, hiring signals, growth indicators
    """
    score = 0
    
    # Company size scoring
    employee_count = company.get("estimated_num_employees", 0)
    if ICP["company_size"]["min_employees"] <= employee_count <= ICP["company_size"]["max_employees"]:
        score += 25
    
    # Industry scoring
    industry = company.get("industry", "").lower()
    if any(ind.lower() in industry for ind in ICP["target_industries"]):
        score += 20
    
    # Hiring signal scoring
    company_name = company.get("name", "").lower()
    recent_hiring = company.get("recent_hiring_activity", False)
    if recent_hiring:
        score += 30
    
    # Growth signal scoring
    funding_status = company.get("funding_stage", "").lower()
    if any(stage in funding_status for stage in ["series a", "series b", "growth", "late stage"]):
        score += 15
    
    # Website activity
    if company.get("website_updated_recently", False):
        score += 10
    
    return min(score, 100)


def enrich_contact_for_outreach(contact: dict, company: dict) -> dict:
    """Enrich contact with outreach-ready data."""
    return {
        "first_name": contact.get("first_name", ""),
        "last_name": contact.get("last_name", ""),
        "title": contact.get("title", ""),
        "email": contact.get("email", ""),
        "phone": contact.get("phone_number", ""),
        "company_name": company.get("name", ""),
        "industry": company.get("industry", ""),
        "company_size": company.get("estimated_num_employees", 0),
        "company_website": company.get("website_url", ""),
        "linkedin_url": contact.get("linkedin_url", "")
    }


def is_decision_maker(contact: dict) -> bool:
    """Check if contact matches buyer personas."""
    title = contact.get("title", "").lower()
    return any(keyword.lower() in title for keyword in HIRING_KEYWORDS)


def is_duplicate(email: str, existing_leads: List[dict]) -> bool:
    """Check if email already in leads."""
    dedup = load_json(DEDUP_FILE, [])
    all_leads = existing_leads + dedup
    
    return any(lead.get("email") == email for lead in all_leads)


def create_lead_record(contact: dict, company: dict, icp_score: float) -> dict:
    """Create standardized lead record."""
    return {
        "id": f"APEX-{int(time.time())}-{contact.get('email', '')[:5]}",
        "first_name": contact.get("first_name", ""),
        "last_name": contact.get("last_name", ""),
        "email": contact.get("email", ""),
        "title": contact.get("title", ""),
        "company_name": company.get("name", ""),
        "industry": company.get("industry", ""),
        "company_size": company.get("estimated_num_employees", 0),
        "company_website": company.get("website_url", ""),
        "icp_score": round(icp_score, 1),
        "hiring_signals": company.get("recent_hiring_activity", False),
        "funding_stage": company.get("funding_stage", ""),
        "source": "apollo-io",
        "discovered_at": datetime.now().isoformat(),
        "status": "new",
        "outreach_status": "pending"
    }


def source_apex_leads(batch_size: int = 50, min_icp_score: float = 60.0) -> int:
    """
    Run full Apex lead sourcing pipeline.
    Returns count of new leads added.
    """
    print("\n" + "="*70)
    print("🚀 APEX AI LEAD SOURCER — Apollo.io Integration")
    print("="*70 + "\n")
    
    if not APOLLO_API_KEY:
        print("\n⚠️  SETUP REQUIRED:")
        print("   1. Sign up free at apollo.io")
        print("   2. Get API key from settings")
        print("   3. Add to .env: APOLLO_API_KEY=your_key")
        print("   4. Run sourcer again\n")
        return 0
    
    log_action("sourcer_start", f"Target: {batch_size} qualified leads (min ICP score: {min_icp_score})", "info")
    
    existing_leads = load_json(LEADS_FILE, [])
    new_leads = []
    
    # Search for companies by hiring signals
    for query in SEARCH_QUERIES:
        print(f"\n🔍 Searching: {query}")
        companies = search_apollo_companies(query, limit=10)
        
        for company in companies:
            # Score company by ICP fit
            icp_score = score_company_icp_fit(company)
            
            if icp_score < min_icp_score:
                continue
            
            print(f"  ✓ {company.get('name')} (Score: {icp_score}/100)")
            
            # Get decision makers
            contacts = search_apollo_contacts(company.get("id", ""), limit=5)
            
            for contact in contacts:
                if not is_decision_maker(contact):
                    continue
                
                email = contact.get("email", "")
                
                # Skip duplicates
                if is_duplicate(email, existing_leads):
                    continue
                
                # Create lead
                lead = create_lead_record(contact, company, icp_score)
                new_leads.append(lead)
                
                print(f"    → {contact.get('first_name')} {contact.get('last_name')} ({email})")
            
            # Rate limiting
            time.sleep(0.5)
    
    # Save leads
    all_leads = existing_leads + new_leads
    save_json(LEADS_FILE, all_leads)
    save_json(DEDUP_FILE, all_leads)
    
    log_action("sourcer_complete", f"Added {len(new_leads)} new leads (Total: {len(all_leads)})", "success")
    
    print(f"\n{'='*70}")
    print(f"✅ SOURCING COMPLETE")
    print(f"   New leads: {len(new_leads)}")
    print(f"   Total leads: {len(all_leads)}")
    print(f"   Min ICP score: {min_icp_score}")
    print(f"   Output: {LEADS_FILE}")
    print(f"{'='*70}\n")
    
    return len(new_leads)


if __name__ == "__main__":
    source_apex_leads(batch_size=50, min_icp_score=60.0)

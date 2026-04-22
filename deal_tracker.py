#!/usr/bin/env python3
"""
Deal Tracker for Descieux Digital Phase 1
Tracks leads through the full pipeline: outreach → demo → subscription/project → closed deal.

Manages:
- Demo scheduling (via Calendly links in emails)
- Subscription conversions (Creator Essentials, Creator Pro, Studio Custom)
- Custom project tracking
- Revenue reporting and metrics
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional

DEALS_FILE = "deals.json"
SUBSCRIPTIONS_FILE = "subscriptions.json"
REVENUE_FILE = "revenue_summary.json"

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

def create_deal_from_lead(lead_email: str, lead_name: str, company: str, segment: str) -> dict:
    """Create a new deal tracking record from a qualified lead."""
    return {
        "id": f"DEAL-{int(datetime.now().timestamp())}-{lead_email[:8]}",
        "lead_email": lead_email,
        "lead_name": lead_name,
        "company": company,
        "segment": segment,
        "status": "outreach_sent",  # outreach_sent → demo_scheduled → demo_completed → subscribed/project_in_progress → closed
        "stages": {
            "outreach_sent_at": datetime.now().isoformat(),
            "demo_scheduled_at": None,
            "demo_completed_at": None,
            "subscription_selected_at": None,
            "project_started_at": None,
            "closed_at": None
        },
        "conversion": {
            "subscription_tier": None,  # Creator Essentials, Creator Pro, Studio Custom
            "subscription_start": None,
            "project_name": None,
            "project_value": None,
            "notes": ""
        },
        "revenue": {
            "mrr": 0,  # Monthly recurring revenue from subscription
            "one_time_revenue": 0,  # From custom projects
            "total_value": 0
        }
    }

def schedule_demo(deal_id: str, demo_date: str, calendly_link: str) -> dict:
    """Record that a demo was scheduled for this deal."""
    deals = load_json(DEALS_FILE, [])

    for deal in deals:
        if deal.get("id") == deal_id:
            deal["status"] = "demo_scheduled"
            deal["stages"]["demo_scheduled_at"] = datetime.now().isoformat()
            deal["conversion"]["demo_scheduled_date"] = demo_date
            deal["conversion"]["calendly_link"] = calendly_link
            break

    save_json(DEALS_FILE, deals)
    return deal

def complete_demo(deal_id: str, outcome: str, notes: str = "") -> dict:
    """Mark demo as completed with outcome (interested/not_interested/need_more_info)."""
    deals = load_json(DEALS_FILE, [])

    for deal in deals:
        if deal.get("id") == deal_id:
            deal["status"] = "demo_completed"
            deal["stages"]["demo_completed_at"] = datetime.now().isoformat()
            deal["conversion"]["demo_outcome"] = outcome
            deal["conversion"]["notes"] = notes
            break

    save_json(DEALS_FILE, deals)
    return deal

def convert_to_subscription(deal_id: str, tier: str, monthly_price: float) -> dict:
    """Convert a deal to a subscription."""
    deals = load_json(DEALS_FILE, [])

    # Pricing reference
    PRICING = {
        "Creator Essentials": 249,
        "Creator Pro": 699,
        "Studio Custom": 3000  # Average of custom range
    }

    price = PRICING.get(tier, monthly_price)

    for deal in deals:
        if deal.get("id") == deal_id:
            deal["status"] = "subscribed"
            deal["stages"]["subscription_selected_at"] = datetime.now().isoformat()
            deal["conversion"]["subscription_tier"] = tier
            deal["conversion"]["subscription_start"] = datetime.now().isoformat()
            deal["revenue"]["mrr"] = price
            deal["revenue"]["total_value"] = price  # First month
            break

    save_json(DEALS_FILE, deals)
    update_revenue_summary()
    return deal

def start_custom_project(deal_id: str, project_name: str, project_value: float) -> dict:
    """Convert a deal to a custom project."""
    deals = load_json(DEALS_FILE, [])

    for deal in deals:
        if deal.get("id") == deal_id:
            deal["status"] = "project_in_progress"
            deal["stages"]["project_started_at"] = datetime.now().isoformat()
            deal["conversion"]["project_name"] = project_name
            deal["conversion"]["project_value"] = project_value
            deal["revenue"]["one_time_revenue"] = project_value
            deal["revenue"]["total_value"] = project_value
            break

    save_json(DEALS_FILE, deals)
    update_revenue_summary()
    return deal

def close_deal(deal_id: str) -> dict:
    """Mark deal as closed (subscription ongoing or project completed)."""
    deals = load_json(DEALS_FILE, [])

    for deal in deals:
        if deal.get("id") == deal_id:
            deal["status"] = "closed"
            deal["stages"]["closed_at"] = datetime.now().isoformat()
            break

    save_json(DEALS_FILE, deals)
    update_revenue_summary()
    return deal

def update_revenue_summary() -> dict:
    """Calculate and update revenue summary across all deals."""
    deals = load_json(DEALS_FILE, [])

    summary = {
        "calculated_at": datetime.now().isoformat(),
        "total_deals": len(deals),
        "deals_by_status": {},
        "mrr_total": 0,
        "arr_total": 0,
        "one_time_revenue_total": 0,
        "total_revenue": 0,
        "subscriptions": {
            "Creator Essentials": 0,
            "Creator Pro": 0,
            "Studio Custom": 0
        },
        "active_projects": 0,
        "conversion_metrics": {}
    }

    for deal in deals:
        status = deal.get("status")
        summary["deals_by_status"][status] = summary["deals_by_status"].get(status, 0) + 1

        if status == "closed" or status == "subscribed":
            mrr = deal.get("revenue", {}).get("mrr", 0)
            summary["mrr_total"] += mrr

            tier = deal.get("conversion", {}).get("subscription_tier")
            if tier and tier in summary["subscriptions"]:
                summary["subscriptions"][tier] += 1

        if status == "project_in_progress":
            summary["active_projects"] += 1

        summary["one_time_revenue_total"] += deal.get("revenue", {}).get("one_time_revenue", 0)

    # Calculate ARR (monthly recurring × 12)
    summary["arr_total"] = summary["mrr_total"] * 12
    summary["total_revenue"] = summary["mrr_total"] + summary["one_time_revenue_total"]

    # Conversion metrics
    total = summary["total_deals"]
    if total > 0:
        subscribed = summary["deals_by_status"].get("subscribed", 0)
        projects = summary["deals_by_status"].get("project_in_progress", 0)

        summary["conversion_metrics"] = {
            "total_leads": total,
            "demos_scheduled": summary["deals_by_status"].get("demo_scheduled", 0) + subscribed + projects,
            "demos_completed": summary["deals_by_status"].get("demo_completed", 0) + subscribed + projects,
            "conversions": subscribed + projects,
            "conversion_rate": round(((subscribed + projects) / total * 100), 2),
            "avg_deal_value": round(summary["total_revenue"] / max(subscribed + projects, 1), 2)
        }

    save_json(REVENUE_FILE, summary)
    return summary

def get_revenue_summary() -> dict:
    """Get current revenue summary."""
    return load_json(REVENUE_FILE, {
        "mrr_total": 0,
        "arr_total": 0,
        "total_revenue": 0,
        "subscriptions": {},
        "conversion_rate": 0
    })

def print_deal_dashboard() -> None:
    """Print dashboard of all deals and revenue."""
    deals = load_json(DEALS_FILE, [])
    summary = load_json(REVENUE_FILE, {})

    print("\n" + "="*70)
    print("📊 DESCIEUX DIGITAL — DEAL TRACKER DASHBOARD")
    print("="*70)

    print(f"\n💰 REVENUE:")
    print(f"  Monthly Recurring (MRR):     ${summary.get('mrr_total', 0):,.2f}")
    print(f"  Annual Recurring (ARR):      ${summary.get('arr_total', 0):,.2f}")
    print(f"  One-time Revenue:            ${summary.get('one_time_revenue_total', 0):,.2f}")
    print(f"  Total Revenue:               ${summary.get('total_revenue', 0):,.2f}")

    print(f"\n📈 DEALS:")
    deals_by_status = summary.get("deals_by_status", {})
    for status, count in sorted(deals_by_status.items()):
        print(f"  {status}:                 {count}")

    print(f"\n🎯 CONVERSIONS:")
    metrics = summary.get("conversion_metrics", {})
    print(f"  Total Leads:                 {metrics.get('total_leads', 0)}")
    print(f"  Demos Scheduled:             {metrics.get('demos_scheduled', 0)}")
    print(f"  Demos Completed:             {metrics.get('demos_completed', 0)}")
    print(f"  Conversions (Sub + Project): {metrics.get('conversions', 0)}")
    print(f"  Conversion Rate:             {metrics.get('conversion_rate', 0)}%")
    print(f"  Avg Deal Value:              ${metrics.get('avg_deal_value', 0):,.2f}")

    print(f"\n🎁 SUBSCRIPTIONS:")
    subs = summary.get("subscriptions", {})
    print(f"  Creator Essentials ($249):   {subs.get('Creator Essentials', 0)}")
    print(f"  Creator Pro ($699):          {subs.get('Creator Pro', 0)}")
    print(f"  Studio Custom (avg $3K):     {subs.get('Studio Custom', 0)}")

    print(f"\n{'='*70}\n")

if __name__ == "__main__":
    print_deal_dashboard()

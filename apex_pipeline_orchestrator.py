#!/usr/bin/env python3
"""
Descieux Digital Phase 1 Pipeline Orchestrator
Coordinates complete end-to-end pipeline for Descieux Digital content creation platform:
1. Source leads via Apollo.io (content creators, agencies, production companies)
2. Qualify and segment by buyer persona
3. Generate personalized outreach (platform benefits for each segment)
4. Send emails (rate limited, includes Calendly booking link)
5. Monitor responses and schedule demos
6. Track deals through conversions (subscriptions or custom projects)
7. Generate revenue and conversion reports

Run on schedule (daily) to keep pipeline flowing.
"""

import os
import json
import subprocess
import sys
from datetime import datetime
from typing import Dict

CONFIG_FILE = "icp_config.json"
PIPELINE_DB = "apex_pipeline.json"


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


def run_step(step_name: str, script: str, args: list = None) -> bool:
    """Run a pipeline step."""
    print(f"\n{'─'*70}")
    print(f"▶️  {step_name}")
    print(f"{'─'*70}\n")
    
    try:
        cmd = ["python3", script]
        if args:
            cmd.extend(args)
        
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"\n✅ {step_name} complete\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {step_name} failed: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ {step_name} error: {e}\n")
        return False


def generate_pipeline_report() -> Dict:
    """Generate current pipeline report with deals and revenue."""
    pipeline = load_json(PIPELINE_DB, {})
    revenue = load_json("revenue_summary.json", {})
    deals = load_json("deals.json", [])

    report = {
        "timestamp": datetime.now().isoformat(),
        "business": "Descieux Digital - Content Creation Platform",
        "phase": "Phase 1 - Platform Validation",
        "pipeline_health": {
            "total_leads_sourced": len(deals),
            "emails_sent": pipeline.get("stats", {}).get("sent", 0),
            "replies": pipeline.get("stats", {}).get("replied", 0),
            "reply_rate": round((pipeline.get("stats", {}).get("replied", 0) / max(pipeline.get("stats", {}).get("sent", 1), 1) * 100), 2)
        },
        "deal_funnel": {
            "outreach_sent": len([d for d in deals if d.get("status") == "outreach_sent"]),
            "demo_scheduled": len([d for d in deals if d.get("status") == "demo_scheduled"]),
            "demo_completed": len([d for d in deals if d.get("status") == "demo_completed"]),
            "subscribed": len([d for d in deals if d.get("status") == "subscribed"]),
            "projects": len([d for d in deals if d.get("status") == "project_in_progress"]),
            "closed": len([d for d in deals if d.get("status") == "closed"])
        },
        "revenue": {
            "mrr": revenue.get("mrr_total", 0),
            "arr": revenue.get("arr_total", 0),
            "one_time": revenue.get("one_time_revenue_total", 0),
            "total": revenue.get("total_revenue", 0)
        },
        "subscriptions": revenue.get("subscriptions", {}),
        "by_tier": pipeline.get("by_tier", {}),
        "next_actions": []
    }

    # Generate recommendations
    sent = pipeline.get("stats", {}).get("sent", 0)
    replied = pipeline.get("stats", {}).get("replied", 0)
    conversions = report["deal_funnel"]["subscribed"] + report["deal_funnel"]["projects"]

    if sent == 0:
        report["next_actions"].append("▶️  Run lead sourcer to find content creators/agencies")
    elif replied == 0:
        report["next_actions"].append(f"▶️  Waiting for replies ({sent} conversations started)")
    else:
        if conversions == 0:
            report["next_actions"].append("⚠️  No conversions yet, schedule demos with interested prospects")
        else:
            conversion_rate = (conversions / max(sent, 1)) * 100
            if conversion_rate < 3:
                report["next_actions"].append(f"⚠️  Conversion rate {conversion_rate:.1f}%, refine demo/pitch")
            else:
                report["next_actions"].append(f"✓ Conversion rate {conversion_rate:.1f}%, on track to hit targets")

    if report["revenue"]["mrr"] > 0:
        report["next_actions"].append(f"💰 Monthly recurring: ${report['revenue']['mrr']:,.0f}")

    return report


def print_pipeline_status():
    """Print current pipeline status with deals and revenue."""
    pipeline = load_json(PIPELINE_DB, {})
    config = load_json(CONFIG_FILE, {})
    revenue = load_json("revenue_summary.json", {})
    deals = load_json("deals.json", [])

    print("\n" + "="*70)
    print("📊 DESCIEUX DIGITAL — PHASE 1 PIPELINE STATUS")
    print("="*70 + "\n")

    print(f"Business: {config.get('business', 'Descieux Digital')}")
    print(f"Updated: {pipeline.get('updated_at', 'Never')}\n")

    # Outreach metrics
    stats = pipeline.get("stats", {})
    print("📧 OUTREACH:")
    print(f"  Total sourced: {len(deals)}")
    print(f"  Sent: {stats.get('sent', 0)}")
    print(f"  Replied: {stats.get('replied', 0)}")
    if stats.get('sent', 0) > 0:
        reply_rate = (stats.get('replied', 0) / stats.get('sent', 0)) * 100
        print(f"  Reply rate: {reply_rate:.1f}%\n")
    else:
        print()

    # Deal funnel
    print("🎯 DEAL FUNNEL:")
    print(f"  Outreach sent: {len([d for d in deals if d.get('status') == 'outreach_sent'])}")
    print(f"  Demos scheduled: {len([d for d in deals if d.get('status') == 'demo_scheduled'])}")
    print(f"  Demos completed: {len([d for d in deals if d.get('status') == 'demo_completed'])}")
    print(f"  Subscribed: {len([d for d in deals if d.get('status') == 'subscribed'])}")
    print(f"  Projects: {len([d for d in deals if d.get('status') == 'project_in_progress'])}\n")

    # Revenue
    print("💰 REVENUE:")
    print(f"  Monthly recurring (MRR): ${revenue.get('mrr_total', 0):,.2f}")
    print(f"  Annual recurring (ARR): ${revenue.get('arr_total', 0):,.2f}")
    print(f"  One-time revenue: ${revenue.get('one_time_revenue_total', 0):,.2f}")
    print(f"  Total revenue: ${revenue.get('total_revenue', 0):,.2f}\n")

    # Subscriptions
    print("🎁 SUBSCRIPTIONS:")
    subs = revenue.get("subscriptions", {})
    print(f"  Creator Essentials ($249): {subs.get('Creator Essentials', 0)}")
    print(f"  Creator Pro ($699): {subs.get('Creator Pro', 0)}")
    print(f"  Studio Custom: {subs.get('Studio Custom', 0)}\n")

    print("BY QUALIFICATION TIER:")
    for tier, data in pipeline.get("by_tier", {}).items():
        print(f"  {tier.upper()}: {data.get('sent', 0)} sent | {data.get('replied', 0)} replied")

    print("\n" + "="*70 + "\n")


def run_full_pipeline(source_limit: int = 50, send_limit: int = 50, skip_source: bool = False) -> bool:
    """
    Run complete pipeline from lead sourcing to follow-ups.
    
    Args:
        source_limit: Max leads to source
        send_limit: Max emails to send today
        skip_source: Skip sourcing (use existing queue)
    """
    print("\n" + "╔" + "═"*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  🚀 APEX AI AUTONOMOUS PIPELINE".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "═"*68 + "╝\n")
    
    print(f"Start time: {datetime.now().isoformat()}\n")
    
    steps_completed = 0
    steps_failed = 0
    
    # STEP 1: Source leads (optional skip)
    if not skip_source:
        if run_step("1️⃣  Lead Sourcing (Apollo.io)", "lead_sourcer_apollo.py"):
            steps_completed += 1
        else:
            steps_failed += 1
            print("⚠️  Continuing with existing leads...")
    else:
        print("\n⊘ Skipping lead sourcing (using existing queue)\n")
    
    # STEP 2: Qualify & segment
    if run_step("2️⃣  Lead Qualification & Segmentation", "lead_qualifier.py"):
        steps_completed += 1
    else:
        steps_failed += 1
        print("⚠️  Check if leads exist...")
    
    # STEP 3: Send outreach
    if run_step("3️⃣  Email Delivery", "apex_send_emails.py", ["--limit", str(send_limit)]):
        steps_completed += 1
    else:
        steps_failed += 1
    
    # STEP 4: Monitor responses (background)
    print(f"\n{'─'*70}")
    print("4️⃣  Response Monitoring")
    print(f"{'─'*70}\n")
    print("💡 Response handler runs continuously in background:")
    print("   python3 apex_response_handler.py\n")
    print("✓ Configured to run as daemon\n")
    
    # Generate report
    report = generate_pipeline_report()
    
    print(f"\n{'='*70}")
    print("📋 PIPELINE REPORT")
    print(f"{'='*70}\n")
    print(f"Timestamp: {report['timestamp']}")
    print(f"Total sourced: {report['pipeline_health']['total_leads_sourced']}")
    print(f"Emails sent: {report['pipeline_health']['emails_sent']}")
    print(f"Conversion rate: {report['pipeline_health']['open_rate']}%")
    print(f"Replies: {report['pipeline_health']['replies']}")
    print("\nNext actions:")
    for action in report["next_actions"]:
        print(f"  {action}")
    
    print(f"\n{'='*70}")
    print(f"✅ Pipeline run complete | {steps_completed} steps completed, {steps_failed} failed")
    print(f"{'='*70}\n")
    
    return steps_failed == 0


def show_commands():
    """Show available commands."""
    print("""
╔────────────────────────────────────────────────────────────────╗
║            APEX AI PIPELINE — Available Commands               ║
╚────────────────────────────────────────────────────────────────╝

FULL PIPELINE (Recommended):
  python3 apex_pipeline_orchestrator.py run
    → Sources leads → Qualifies → Sends emails → Monitors responses

INDIVIDUAL STEPS:
  python3 lead_sourcer_apollo.py
    → Find companies via Apollo.io API

  python3 lead_qualifier.py
    → Qualify leads & generate personalized emails

  python3 apex_send_emails.py [--hot|--warm|--cool] [--limit N]
    → Send outreach emails
    → Filter by tier or set daily limit

  python3 apex_response_handler.py
    → Monitor inbox for replies (run continuously)

STATUS:
  python3 apex_pipeline_orchestrator.py status
    → Show current pipeline health

REPORTS:
  cat apex_pipeline.json          → Pipeline metrics
  cat apex_outreach_queue.json    → Emails ready/sent
  cat apex_responses.json         → Inbound replies
  cat apex_send_log.json          → Send history

SETUP REQUIRED:
  1. .env file needs:
     - GMAIL_USER=ydescieux2@gmail.com
     - GMAIL_APP_PASSWORD=your_app_password
     - APOLLO_API_KEY=your_apollo_key (optional, free at apollo.io)

  2. Scheduling (cron):
     # Daily at 9am
     0 9 * * * cd ~/apex-ai-orchestrator && python3 apex_pipeline_orchestrator.py run

     # Monitor responses continuously
     * * * * * cd ~/apex-ai-orchestrator && python3 apex_response_handler.py > /dev/null 2>&1
    """)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "run":
            run_full_pipeline(source_limit=50, send_limit=50)
        
        elif cmd == "status":
            print_pipeline_status()
        
        elif cmd == "help" or cmd == "--help" or cmd == "-h":
            show_commands()
        
        else:
            print(f"Unknown command: {cmd}")
            show_commands()
    
    else:
        show_commands()

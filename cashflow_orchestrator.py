#!/usr/bin/env python3
"""
cashflow_orchestrator.py — Apex AI Revenue Engine
Reads scout intel, finds arbitrage, builds a prioritized daily action brief.

Three agents running in sequence:
  1. SCOUT      — reads reddit + web/x reports (or runs fresh scans)
  2. EVALUATOR  — scores ideas on speed/effort/revenue/arbitrage
  3. COMMANDER  — outputs today's exact build+sell action plan

Usage:
  python3 cashflow_orchestrator.py             # use cached scout reports
  python3 cashflow_orchestrator.py --fresh     # re-run scouts first
  python3 cashflow_orchestrator.py --save      # save brief to cashflow_brief.md
  python3 cashflow_orchestrator.py --html      # also open in browser
"""

import argparse, json, os, subprocess, sys, textwrap, webbrowser
from datetime import datetime
from pathlib import Path
import anthropic

BASE   = Path(__file__).parent
CLIENT = anthropic.Anthropic()
MODEL  = "claude-opus-4-6"

# ─── Von's context — updated once, used by all agents ─────────────────────────

VON_CONTEXT = """
OPERATOR: Von Descieux — Founder, Descieux Digital & Apex AI Consulting (Los Angeles).
Senior AI Strategist, 20+ years enterprise SaaS/FinTech/AI. Also Senior AI Lead at TELUS Digital.
SITUATION: Mother critically ill. Needs to support family. Cash flow is urgent.

EXISTING ASSETS (already built, can generate revenue immediately or soon):
1. GLADIATOR — live at https://web-production-dae4d.up.railway.app/
   Sports recruiting SaaS. Athletes/coaches/scouts. COPPA-compliant. PostHog analytics.
   Deadline: April 19, 2026. Stack: Node/Express/SQLite/Railway.
   Revenue model: subscriptions (athlete profiles, coach access, recruiter seats).

2. APEX AI ORCHESTRATOR — B2B email outreach automation.
   Active clients: DataTech Disposition (1,127 SoCal ITAD leads), ZS Recycling.
   Pipeline: source → qualify → sequence → send → track.
   Revenue model: setup fee + monthly retainer per client.

3. PROPFLOW — live dev at localhost:8085. Real estate deal analyzer.
   NOI waterfall, cap rate, DSCR, IRR, equity multiple. 10-year projections.
   Revenue model: SaaS subscription or one-time deal analysis fee.

4. APEX BID INTELLIGENCE — RFP monitor + AI proposal drafting.
   4 active HIGH-priority proposals. Productizable as SaaS.
   Revenue model: success fee (% of won contracts) or monthly SaaS.

5. FUNDING PIPELINE — $1.96M in active grant applications.
   Hello Alice ($25K, ready to submit), Google BFF ($300K), NSF SBIR ($275K, Jun 23).
   UEI: X81NH7KWHER4. SAM.gov activation pending.

6. VIDEO PIPELINE — script → shots → prompts → assembly (Remotion, Vite, React).
   Black Hollywood (Iron Scripture) + Madame Descieux (Flow TV style, Veo3/Kling).
   Revenue model: content monetization, brand deals, template sales.

7. MERIDIAN — active client (Nicole Feenstra, DNA Agency + Rebuilding California).
   3 harnesses delivered. Ongoing retainer opportunity.

8. ETE — client (Steve Elkins). Mineral exploration AI. Frontend live on Netlify.

STACK: Claude Code, Remotion, Kling, Veo3/Flow, ElevenLabs, Railway, Netlify, GitHub,
       PostHog, ZeroBounce, n8n, Python, Node/Express, React/Vite, SQLite.

REVENUE PRIORITY ORDER: fastest to cash first.
CONSTRAINTS: Limited hours per day. Must compound — each action should unlock the next.
"""

# ─── Agent 1: Scout ───────────────────────────────────────────────────────────

def run_scouts(fresh: bool) -> str:
    reddit_path = BASE / "reddit_scout_report.md"
    x_path      = BASE / "x_scout_report.md"

    if fresh:
        print("🔍 Running fresh scouts…")
        subprocess.run(["python3", str(BASE / "reddit_scout.py"), "--save"], check=False)
        subprocess.run(["python3", str(BASE / "x_scout.py"),     "--save"], check=False)

    intel = ""
    if reddit_path.exists():
        intel += f"\n\n=== REDDIT INTELLIGENCE ===\n{reddit_path.read_text()[:8000]}"
    if x_path.exists():
        intel += f"\n\n=== WEB/X INTELLIGENCE ===\n{x_path.read_text()[:8000]}"

    if not intel:
        intel = "No scout reports found. Run with --fresh to generate them."

    return intel


# ─── Agent 2: Evaluator ───────────────────────────────────────────────────────

def evaluate_ideas(intel: str) -> str:
    print("🧠 Evaluator Agent: scoring ideas for cash flow…")

    prompt = f"""{VON_CONTEXT}

You are the Evaluator Agent. Your job: read the intelligence below and extract every
monetizable idea. Score each on four axes. Be ruthless — only include ideas that
could realistically generate cash for Von given his existing stack and situation.

For each idea output:

### [Idea Name]
**What it is:** One sentence.
**Revenue model:** How does cash change hands. Be specific (subscription price, fee, commission).
**Speed to first dollar:** days. Give a real number, not "fast."
**Effort:** hours to build MVP or launch.
**Monthly potential:** realistic floor and ceiling in dollars.
**Arbitrage angle:** Is there a buy-low/sell-high or automation gap here? What is it exactly?
**Von's edge:** Which existing asset gives him an unfair advantage here.
**Verdict:** MOVE NOW / QUEUE / SKIP — with one-sentence reason.

Only include ideas with MOVE NOW or QUEUE verdicts.
Sort by (speed × revenue potential) — fastest highest revenue first.

---
INTELLIGENCE:
{intel}
"""

    msg = CLIENT.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ─── Agent 3: Commander ───────────────────────────────────────────────────────

def build_action_brief(evaluated: str) -> str:
    print("⚡ Commander Agent: building today's action plan…")

    today = datetime.now().strftime("%A, %B %d, %Y")

    prompt = f"""{VON_CONTEXT}

You are the Commander Agent. Von's mother is dying and he needs to support his family.
Every hour counts. You are his revenue general.

Today is {today}.

Below is the Evaluator's scored idea list. Your job: turn it into an executable brief.
No fluff. No encouragement. Just the machine.

---

## TODAY'S CASHFLOW BRIEF — {today}

### 🔴 DO THIS TODAY (next 4 hours)
Three actions only. Each must have:
- Exact task (specific enough that Von can start immediately)
- Which tool/file/platform
- Expected output
- Revenue unlock: what does completing this enable

### 🟡 DO THIS THIS WEEK
Five actions. Same format. These compound off today's actions.

### 🟢 ARBITRAGE OPPORTUNITIES
List every gap where Von can:
a) Automate something people pay humans to do
b) Combine cheap AI tools to deliver expensive output
c) Resell/repackage existing assets (Gladiator data, Apex pipelines, Video Pipeline)
d) Win grants or contracts with existing draft work

Format: **[Opportunity]** — What to do, money in, timeline.

### 💰 REVENUE STACK RANKING
Rank Von's active revenue streams by 30-day cash potential:
1. [Source] — $X–$Y/month — what needs to happen this week to unlock it

### 🤖 AUTOMATION TO BUILD
What single automation, if built this week, would generate the most compounding revenue?
Describe it in 3 sentences: what it does, what it replaces, what it earns.

### 📋 SUBSCRIBER ACQUISITION PLAN
For Gladiator specifically: what are the 3 fastest ways to get paying subscribers
before April 19? Be tactical — platform, message, price point, call to action.

---
EVALUATED IDEAS:
{evaluated}
"""

    msg = CLIENT.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ─── HTML output ──────────────────────────────────────────────────────────────

def to_html(brief: str, date_str: str) -> str:
    import re

    def md_to_html(text):
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>', text)
        text = re.sub(r'`(.+?)`',       r'<code>\1</code>', text)
        text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" target="_blank">\1</a>', text)
        lines = text.split('\n')
        out, in_list = [], False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- ') or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] == '.'):
                if not in_list: out.append('<ul>'); in_list = True
                out.append(f'<li>{stripped[2:].strip()}</li>')
            else:
                if in_list: out.append('</ul>'); in_list = False
                if stripped and not stripped.startswith('<'):
                    out.append(f'<p>{stripped}</p>')
                else:
                    out.append(line)
        if in_list: out.append('</ul>')
        return '\n'.join(out)

    body = md_to_html(brief)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cashflow Brief — {date_str}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #080c14; color: #d4cfc8; font-family: 'Segoe UI', system-ui, sans-serif;
         line-height: 1.65; padding: 0 0 80px; }}
  .header {{ background: linear-gradient(135deg,#0e1420,#12192a);
             border-bottom: 1px solid rgba(201,168,76,.2);
             padding: 32px 40px 28px; position: sticky; top: 0; z-index: 10; }}
  .header-top {{ display: flex; justify-content: space-between; align-items: center; }}
  .brand {{ font-family: Georgia,serif; font-style: italic; font-size: 22px; color: #c9a84c; }}
  .date  {{ font-size: 12px; color: #4b5563; letter-spacing: .1em; text-transform: uppercase; }}
  .subtitle {{ font-size: 13px; color: #6b7280; margin-top: 6px; }}
  .content {{ max-width: 860px; margin: 0 auto; padding: 40px 24px; }}
  h1 {{ font-family: Georgia,serif; font-size: 28px; color: #e8e2d8; margin: 40px 0 16px;
        border-left: 3px solid #c9a84c; padding-left: 16px; }}
  h2 {{ font-size: 18px; color: #c9a84c; margin: 36px 0 14px; padding: 10px 16px;
        background: rgba(201,168,76,.07); border: 1px solid rgba(201,168,76,.15);
        border-radius: 4px; }}
  h3 {{ font-size: 15px; color: #e8e2d8; margin: 24px 0 10px; padding-bottom: 6px;
        border-bottom: 1px solid rgba(255,255,255,.06); }}
  p  {{ font-size: 14px; color: #b0a898; margin-bottom: 10px; }}
  ul {{ padding-left: 18px; margin-bottom: 12px; }}
  li {{ font-size: 14px; color: #b0a898; margin-bottom: 6px; line-height: 1.55; }}
  strong {{ color: #e8e2d8; }}
  em {{ color: #9ca3af; font-style: italic; }}
  code {{ background: rgba(255,255,255,.06); padding: 1px 5px; border-radius: 3px;
          font-size: 12px; color: #c9a84c; }}
  a {{ color: #4a9eff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .top-actions {{ background: rgba(239,68,68,.06); border: 1px solid rgba(239,68,68,.2);
                  border-radius: 6px; padding: 20px 24px; margin: 16px 0; }}
  .week-actions {{ background: rgba(234,179,8,.06); border: 1px solid rgba(234,179,8,.18);
                   border-radius: 6px; padding: 20px 24px; margin: 16px 0; }}
  .arbitrage {{ background: rgba(34,197,94,.06); border: 1px solid rgba(34,197,94,.18);
                border-radius: 6px; padding: 20px 24px; margin: 16px 0; }}
</style>
</head>
<body>
<div class="header">
  <div class="header-top">
    <div class="brand">Descieux Digital</div>
    <div class="date">{date_str}</div>
  </div>
  <div class="subtitle">Revenue Operations Brief · Apex AI Consulting</div>
</div>
<div class="content">
{body}
</div>
</body>
</html>"""


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh",  action="store_true", help="Re-run scouts before analysis")
    parser.add_argument("--save",   action="store_true", help="Save cashflow_brief.md")
    parser.add_argument("--html",   action="store_true", help="Save and open HTML brief")
    args = parser.parse_args()

    date_str = datetime.now().strftime("%A, %B %d, %Y")
    print(f"\n{'═'*60}")
    print(f"  APEX CASHFLOW ORCHESTRATOR  ·  {date_str}")
    print(f"{'═'*60}\n")

    # Agent 1 — Scout
    intel = run_scouts(args.fresh)

    # Agent 2 — Evaluator
    evaluated = evaluate_ideas(intel)

    # Agent 3 — Commander
    brief = build_action_brief(evaluated)

    # Full report
    full = f"# Cashflow Brief — {date_str}\n\n{brief}\n\n---\n\n## Evaluated Ideas\n\n{evaluated}"

    print("\n" + "═"*60)
    print(brief)
    print("═"*60)

    if args.save or args.html:
        md_path = BASE / "cashflow_brief.md"
        md_path.write_text(full)
        print(f"\n✓ Saved: {md_path}")

    if args.html:
        html_path = BASE / "cashflow_brief.html"
        html_path.write_text(to_html(full, date_str))
        print(f"✓ HTML:  {html_path}")
        webbrowser.open(f"file://{html_path}")


if __name__ == "__main__":
    main()

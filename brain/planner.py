"""
planner.py — LLM-Powered Intent → Task Graph

Takes a natural language command (or a decision engine recommendation)
and returns a structured, ordered list of tasks with tool assignments.

This is where Claude does the thinking.

Usage:
    from brain.planner import plan
    tasks = plan("Run DataTech SEG-1 campaign and optimize for replies")
    # → [{"step": 1, "task": "check_status", "tool": "orchestrate_status", ...}, ...]
"""

import json
import os
import anthropic

ORCHESTRATOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─── Available tools manifest (maps to executor.py) ───────────────────────────
TOOL_MANIFEST = """
Available tools and their purpose:

CAMPAIGN CONTROL
- orchestrate_status      → Show current campaign state across all companies
- orchestrate_audit       → Cross-company dedup check, segment ownership review
- orchestrate_run         → Execute send for a company/segment (requires --company, --segment)
- orchestrate_dry_run     → Preview send without executing (use before orchestrate_run)
- campaign_metrics        → Pull reply rates, open rates, bounce rates

LEAD PIPELINE
- score_leads             → Score and rank leads by ICP fit (requires --segment)
- verify_leads            → ZeroBounce email verification (requires --segment)
- source_leads            → Pull new leads from CSV, Hunter.io, Apollo (requires --segment)
- segment_leads           → Re-run segmentation logic on raw leads
- deconflict_check        → Check for cross-company lead overlap (run before any send)
- preview_send            → Preview exactly who gets emailed and what they receive

INBOX & RESPONSE
- monitor_inbox           → Scan Gmail for replies, classify intent (interested/OOO/etc)
- schedule_followups      → Queue Day 3/7/14 follow-up messages for replied leads
- handle_responses        → Generate intelligent replies to interested prospects

REVENUE & BOOKING
- calendly_links          → Generate single-use booking links for hot prospects
- deal_tracker            → Log and track deals from outreach → demo → close

COPY & OPTIMIZATION
- rewrite_copy            → Generate improved email variants using Claude
- ab_test                 → Run A/B variant comparison on existing templates
- sentiment_check         → Analyze reply sentiment, identify patterns

MEMORY
- read_memory             → Load current system memory / learnings
- write_memory            → Store new learnings, update segment performance
"""

PLAN_PROMPT = """You are the planning layer of an autonomous B2B email outreach system called Apex.
You translate a command into a precise, ordered list of tasks using ONLY the available tools listed below.

{tool_manifest}

RULES:
1. Return ONLY a JSON array — no prose, no markdown.
2. Each task is an object with: step (int), task (str), tool (str), args (dict), rationale (str).
3. Always start with orchestrate_status or deconflict_check before any send.
4. Never include orchestrate_run without a preceding orchestrate_dry_run.
5. Always end with monitor_inbox and write_memory.
6. Keep it to 8 tasks max — be surgical, not exhaustive.
7. Use the exact tool names from the manifest.

COMMAND: {command}

CURRENT CONTEXT: {context}

Return the JSON array only:
"""


# ─── Planner ──────────────────────────────────────────────────────────────────

def plan(command: str, context: dict | None = None) -> list[dict]:
    """
    Translate a natural language command into a structured task list.

    Args:
        command: What you want the system to do.
        context: Optional dict with current state metrics to help the planner.

    Returns:
        List of task objects: [{step, task, tool, args, rationale}, ...]
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    context_str = json.dumps(context or {}, indent=2) if context else "No context provided."

    prompt = PLAN_PROMPT.format(
        tool_manifest=TOOL_MANIFEST,
        command=command,
        context=context_str,
    )

    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        tasks = json.loads(raw)

        # Validate structure
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError(f"Expected dict, got: {type(task)}")
            if "tool" not in task:
                raise ValueError(f"Task missing 'tool' key: {task}")

        return tasks

    except json.JSONDecodeError as e:
        print(f"[Planner] Failed to parse Claude response as JSON: {e}")
        print(f"[Planner] Raw response: {raw[:500]}")
        return _fallback_plan(command)

    except Exception as e:
        print(f"[Planner] API error: {e}")
        return _fallback_plan(command)


def plan_from_decision(decision: dict) -> list[dict]:
    """
    Convert a decision engine output into a task plan.
    Bridges the gap between the deterministic engine and the LLM planner.
    """
    action = decision.get("action")
    company = decision.get("company", "datatech")
    segment = decision.get("segment", "SEG-1")
    context = {
        "decision": decision,
        "company":  company,
        "segment":  segment,
    }

    # Map known actions to optimized commands
    action_commands = {
        "run_campaign":       f"Run {company} {segment} campaign — send to queued leads",
        "optimize_copy":      f"Analyze reply performance for {company} {segment} and generate improved email copy variants",
        "source_leads":       f"Source new leads for {company} {segment} — verify and segment them",
        "monitor_inbox":      f"Check inbox for new replies from {company} outreach and classify them",
        "followup_warm_leads": f"Handle interested replies for {company} — schedule demo calls and generate follow-ups",
        "pause_sender":       f"Audit sender health for {company} — check bounce rates and pause problematic senders",
    }

    command = action_commands.get(action, f"Execute action: {action} for {company}")
    return plan(command, context)


# ─── Fallback plan (used when LLM fails) ──────────────────────────────────────

def _fallback_plan(command: str) -> list[dict]:
    """Minimal safe plan used when the LLM call fails."""
    print("[Planner] Using fallback plan — check ANTHROPIC_API_KEY and connectivity.")
    return [
        {"step": 1, "task": "Check system status",  "tool": "orchestrate_status",
         "args": {}, "rationale": "Fallback: always start with status check"},
        {"step": 2, "task": "Scan inbox for replies", "tool": "monitor_inbox",
         "args": {"company": "datatech"}, "rationale": "Fallback: routine inbox scan"},
        {"step": 3, "task": "Save memory",            "tool": "write_memory",
         "args": {"note": f"Fallback plan executed for: {command}"},
         "rationale": "Fallback: persist state"},
    ]

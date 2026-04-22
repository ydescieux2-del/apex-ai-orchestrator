"""
executor.py — Task Router → Existing Scripts

Maps tool names (from the planner) to actual subprocess calls against
your existing harness scripts. This is the "hands" of the system.

Every tool in planner.py's TOOL_MANIFEST must have a handler here.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Optional

ORCHESTRATOR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS_DIR      = os.path.expanduser("~/james-outreach-harness")
APEX_PYTHON      = sys.executable  # use current venv/python


# ─── Tool → Command mapping ────────────────────────────────────────────────────

class Executor:

    def __init__(self, dry_run: bool = False, verbose: bool = True):
        self.dry_run = dry_run
        self.verbose = verbose
        self.results = []

    def run_task(self, task: dict) -> dict:
        """
        Execute a single task from the planner.

        Args:
            task: {step, task, tool, args, rationale}

        Returns:
            {tool, success, output, error, duration_s, timestamp}
        """
        tool    = task.get("tool", "")
        args    = task.get("args", {})
        label   = task.get("task", tool)
        start   = datetime.now()

        if self.verbose:
            print(f"\n  → [{task.get('step', '?')}] {label}")
            print(f"     Tool: {tool}  Args: {args}")

        handler = self._get_handler(tool)

        if handler is None:
            result = {
                "tool": tool, "success": False,
                "output": "", "error": f"No handler registered for tool: {tool}",
                "duration_s": 0, "timestamp": start.isoformat(),
            }
        else:
            try:
                output = handler(args)
                duration = (datetime.now() - start).total_seconds()
                result = {
                    "tool": tool, "success": True,
                    "output": output[:2000] if output else "",  # cap log size
                    "error": None,
                    "duration_s": round(duration, 2),
                    "timestamp": start.isoformat(),
                }
                if self.verbose:
                    print(f"     ✓ Done in {duration:.1f}s")
                    if output:
                        print(f"     {output[:200].strip()}")
            except Exception as e:
                duration = (datetime.now() - start).total_seconds()
                result = {
                    "tool": tool, "success": False,
                    "output": "", "error": str(e),
                    "duration_s": round(duration, 2),
                    "timestamp": start.isoformat(),
                }
                if self.verbose:
                    print(f"     ✗ Error: {e}")

        self.results.append(result)
        return result

    def run_plan(self, tasks: list[dict]) -> list[dict]:
        """Execute a full plan sequentially. Stop on critical failure."""
        if self.verbose:
            print(f"\n[Executor] Running {len(tasks)} tasks...")

        for task in tasks:
            result = self.run_task(task)
            # Halt on critical tool failures (senders, sends)
            if not result["success"] and task.get("tool") in ("orchestrate_run",):
                if self.verbose:
                    print(f"[Executor] Halting plan — critical tool '{task['tool']}' failed.")
                break

        return self.results

    # ─── Handler registry ──────────────────────────────────────────────────────

    def _get_handler(self, tool: str):
        handlers = {
            # Campaign control
            "orchestrate_status":    self._orchestrate_status,
            "orchestrate_audit":     self._orchestrate_audit,
            "orchestrate_run":       self._orchestrate_run,
            "orchestrate_dry_run":   self._orchestrate_dry_run,
            "campaign_metrics":      self._campaign_metrics,

            # Lead pipeline
            "score_leads":           self._score_leads,
            "verify_leads":          self._verify_leads,
            "source_leads":          self._source_leads,
            "segment_leads":         self._segment_leads,
            "deconflict_check":      self._deconflict_check,
            "preview_send":          self._preview_send,

            # Inbox & response
            "monitor_inbox":         self._monitor_inbox,
            "schedule_followups":    self._schedule_followups,
            "handle_responses":      self._handle_responses,

            # Revenue
            "calendly_links":        self._calendly_links,
            "deal_tracker":          self._deal_tracker,

            # Copy & optimization
            "rewrite_copy":          self._rewrite_copy,
            "ab_test":               self._ab_test,
            "sentiment_check":       self._sentiment_check,

            # Memory
            "read_memory":           self._read_memory,
            "write_memory":          self._write_memory,
        }
        return handlers.get(tool)

    # ─── Individual handlers ───────────────────────────────────────────────────

    def _run(self, cmd: list[str], cwd: str = None) -> str:
        """Execute a subprocess command and return stdout."""
        if self.dry_run:
            return f"[DRY RUN] Would execute: {' '.join(cmd)}"
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or ORCHESTRATOR_DIR,
            timeout=300,
        )
        out = result.stdout.strip()
        if result.returncode != 0 and result.stderr:
            out += f"\nSTDERR: {result.stderr.strip()[:500]}"
        return out

    # CAMPAIGN CONTROL

    def _orchestrate_status(self, args: dict) -> str:
        return self._run([APEX_PYTHON, "orchestrate.py", "--status"])

    def _orchestrate_audit(self, args: dict) -> str:
        return self._run([APEX_PYTHON, "orchestrate.py", "--audit"])

    def _orchestrate_run(self, args: dict) -> str:
        company = args.get("company", "datatech")
        segment = args.get("segment", "SEG-1")
        limit   = args.get("limit", "10")  # safe default — don't blast
        cmd = [APEX_PYTHON, "orchestrate.py",
               "--company", company, "--segment", segment, "--limit", str(limit)]
        return self._run(cmd)

    def _orchestrate_dry_run(self, args: dict) -> str:
        company = args.get("company", "datatech")
        segment = args.get("segment", "SEG-1")
        limit   = args.get("limit", "5")
        cmd = [APEX_PYTHON, "orchestrate.py",
               "--company", company, "--segment", segment,
               "--dry-run", "--limit", str(limit)]
        return self._run(cmd)

    def _campaign_metrics(self, args: dict) -> str:
        # Read from existing JSON files and summarize
        send_log = os.path.join(ORCHESTRATOR_DIR, "master_send_log.json")
        inbox    = os.path.join(ORCHESTRATOR_DIR, "inbox_ledger.json")
        metrics  = {}
        if os.path.exists(send_log):
            with open(send_log) as f:
                data = json.load(f)
            entries = data if isinstance(data, list) else data.get("entries", [])
            metrics["total_sent"] = len(entries)
        if os.path.exists(inbox):
            with open(inbox) as f:
                data = json.load(f)
            entries = data if isinstance(data, list) else data.get("replies", [])
            metrics["total_replies"] = len(entries)
            if metrics.get("total_sent"):
                metrics["reply_rate"] = f"{len(entries)/metrics['total_sent']:.2%}"
        return json.dumps(metrics, indent=2)

    # LEAD PIPELINE

    def _score_leads(self, args: dict) -> str:
        segment = args.get("segment", "SEG-1")
        return self._run(
            [APEX_PYTHON, "lead_scorer.py", "--segment", segment],
            cwd=HARNESS_DIR
        )

    def _verify_leads(self, args: dict) -> str:
        segment = args.get("segment", "SEG-1")
        return self._run(
            [APEX_PYTHON, "verify_leads.py", "--segment", segment],
            cwd=HARNESS_DIR
        )

    def _source_leads(self, args: dict) -> str:
        segment = args.get("segment", "SEG-1")
        return self._run(
            [APEX_PYTHON, "lead_sourcer.py", "--segment", segment],
            cwd=ORCHESTRATOR_DIR
        )

    def _segment_leads(self, args: dict) -> str:
        return self._run(
            [APEX_PYTHON, "lead_segmenter.py"],
            cwd=ORCHESTRATOR_DIR
        )

    def _deconflict_check(self, args: dict) -> str:
        company = args.get("company", "datatech")
        return self._run(
            [APEX_PYTHON, "deconflict.py", "--company", company],
            cwd=ORCHESTRATOR_DIR
        )

    def _preview_send(self, args: dict) -> str:
        company = args.get("company", "datatech")
        segment = args.get("segment", "SEG-1")
        return self._run(
            [APEX_PYTHON, "datatech_send_emails.py",
             "--segment", segment, "--dry-run", "--limit", "5"],
            cwd=HARNESS_DIR
        )

    # INBOX & RESPONSE

    def _monitor_inbox(self, args: dict) -> str:
        company = args.get("company", "datatech")
        return self._run(
            [APEX_PYTHON, "monitor_inbox.py", "--company", company],
            cwd=HARNESS_DIR
        )

    def _schedule_followups(self, args: dict) -> str:
        company = args.get("company", "datatech")
        return self._run(
            [APEX_PYTHON, "follow_up_engine.py", "--company", company],
            cwd=ORCHESTRATOR_DIR
        )

    def _handle_responses(self, args: dict) -> str:
        return self._run(
            [APEX_PYTHON, "apex_response_handler.py"],
            cwd=ORCHESTRATOR_DIR
        )

    # REVENUE

    def _calendly_links(self, args: dict) -> str:
        return self._run(
            [APEX_PYTHON, "calendly_links.py"],
            cwd=ORCHESTRATOR_DIR
        )

    def _deal_tracker(self, args: dict) -> str:
        return self._run(
            [APEX_PYTHON, "deal_tracker.py", "--status"],
            cwd=ORCHESTRATOR_DIR
        )

    # COPY & OPTIMIZATION

    def _rewrite_copy(self, args: dict) -> str:
        """Ask Claude to generate improved email copy based on performance data."""
        import anthropic
        segment    = args.get("segment", "SEG-1")
        reply_rate = args.get("reply_rate", "unknown")

        client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": f"""
You are an expert B2B cold email copywriter specializing in ITAD (IT Asset Disposition).

Current reply rate for {segment}: {reply_rate}

Write 3 improved subject lines and 3 improved email body variants.
Focus on:
- Pain points: IT equipment piling up, compliance risk, missed revenue
- Strong opener (no "I hope this finds you well")
- One clear CTA (15-min call or instant quote)
- Under 100 words per email
- Personalization placeholder: {{{{first_name}}}}, {{{{company_name}}}}

Format as JSON: [{{"subject": "...", "body": "..."}}]
"""}]
        )
        return msg.content[0].text

    def _ab_test(self, args: dict) -> str:
        # Read auto_campaign results if available
        ac_path = os.path.join(ORCHESTRATOR_DIR, "auto_campaign.json")
        if os.path.exists(ac_path):
            with open(ac_path) as f:
                data = json.load(f)
            return json.dumps(data, indent=2)[:1000]
        return "No A/B test data available yet."

    def _sentiment_check(self, args: dict) -> str:
        inbox_path = os.path.join(ORCHESTRATOR_DIR, "inbox_ledger.json")
        if not os.path.exists(inbox_path):
            return "No inbox data available."
        with open(inbox_path) as f:
            data = json.load(f)
        entries = data if isinstance(data, list) else data.get("replies", [])
        classified = {}
        for r in entries:
            c = r.get("classification", r.get("type", "unknown"))
            classified[c] = classified.get(c, 0) + 1
        return json.dumps({"reply_breakdown": classified, "total": len(entries)}, indent=2)

    # MEMORY

    def _read_memory(self, args: dict) -> str:
        from brain.memory_manager import load_memory
        mem = load_memory()
        return json.dumps(mem, indent=2)[:1000]

    def _write_memory(self, args: dict) -> str:
        from brain.memory_manager import update_memory
        update_memory(args)
        return f"Memory updated: {list(args.keys())}"

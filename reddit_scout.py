#!/usr/bin/env python3
"""
reddit_scout.py — Scans Reddit for new Claude / Claude Code / CoWork use cases.
Usage:
  python3 reddit_scout.py              # last 7 days, print report
  python3 reddit_scout.py --days 30    # last 30 days
  python3 reddit_scout.py --save       # also write reddit_scout_report.md
  python3 reddit_scout.py --json       # also write reddit_scout_report.json
"""

import argparse, json, os, sys, time, textwrap
from datetime import datetime, timezone
import requests
import anthropic

# ─── Config ──────────────────────────────────────────────────────────────────

SEARCHES = [
    # Query, subreddit (None = all of Reddit)
    ("claude use case",          None),
    ("claude code workflow",     None),
    ("claude code tips",         None),
    ("CoWork claude",            None),
    ("anthropic claude automati", None),
    ("claude code agent",        None),
    ("claude ai productivity",   None),
    ("claude code review",       None),
    ("claude mcp",               None),
    ("use claude to",            "ClaudeAI"),
    ("claude code",              "ClaudeAI"),
]

HEADERS = {"User-Agent": "reddit-scout/1.0 (apex-ai-consulting)"}
BASE_URL = "https://www.reddit.com"

# ─── Fetch ────────────────────────────────────────────────────────────────────

def search_reddit(query, subreddit=None, days=7, limit=15):
    if subreddit:
        url = f"{BASE_URL}/r/{subreddit}/search.json"
    else:
        url = f"{BASE_URL}/search.json"

    time_filter = "week" if days <= 7 else "month" if days <= 30 else "year"
    params = {
        "q": query,
        "sort": "relevance",
        "t": time_filter,
        "limit": limit,
        "restrict_sr": "true" if subreddit else "false",
    }
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=10)
        r.raise_for_status()
        posts = r.json().get("data", {}).get("children", [])
        return [p["data"] for p in posts]
    except Exception as e:
        print(f"  [warn] search '{query}' failed: {e}", file=sys.stderr)
        return []


def collect_posts(days=7):
    seen = set()
    all_posts = []
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

    for query, sub in SEARCHES:
        time.sleep(0.8)  # respect Reddit rate limit
        posts = search_reddit(query, sub, days)
        for p in posts:
            pid = p.get("id")
            if pid in seen:
                continue
            if p.get("created_utc", 0) < cutoff:
                continue
            seen.add(pid)
            all_posts.append({
                "id": pid,
                "title": p.get("title", ""),
                "subreddit": p.get("subreddit", ""),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "url": f"https://reddit.com{p.get('permalink','')}",
                "body": (p.get("selftext") or "")[:600],
                "created": datetime.fromtimestamp(
                    p.get("created_utc", 0), tz=timezone.utc
                ).strftime("%Y-%m-%d"),
            })

    # Sort by score descending
    all_posts.sort(key=lambda x: x["score"], reverse=True)
    return all_posts


# ─── Analyze ─────────────────────────────────────────────────────────────────

def analyze_posts(posts):
    if not posts:
        return "No relevant posts found."

    client = anthropic.Anthropic()

    # Build a compact digest for Claude to analyze
    digest = []
    for i, p in enumerate(posts[:40], 1):  # cap at 40 to keep tokens reasonable
        digest.append(
            f"[{i}] r/{p['subreddit']} | Score:{p['score']} | {p['created']}\n"
            f"Title: {p['title']}\n"
            f"Body: {p['body'][:200] or '(no body)'}\n"
            f"URL: {p['url']}"
        )

    prompt = f"""You are an AI product intelligence analyst for Apex AI Consulting.

Below are {len(digest)} recent Reddit posts about Claude, Claude Code, and CoWork.

Your job: extract REAL USE CASES — things people are actually doing with these tools.
Ignore hype, complaints, comparisons that don't show actual usage, and duplicate themes.

For each distinct use case you find, output:
## [Category]: [Short use case name]
**What they're doing:** One sentence.
**Relevance to us:** How Apex AI Consulting could use this or sell this to clients. One sentence.
**Signal strength:** Low / Medium / High (based on upvotes + discussion)
**Source:** [post title](url)

End with a ## PATTERNS section listing the top 3 emerging themes in 1-2 sentences each.

---
POSTS:
{chr(10).join(digest)}
"""

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ─── Report ───────────────────────────────────────────────────────────────────

def build_report(posts, analysis, days):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = textwrap.dedent(f"""\
        # Reddit Scout — Claude Use Case Report
        Generated: {now} | Window: last {days} days | Posts found: {len(posts)}

        ---
        """)

    raw_section = "\n## Raw Posts\n"
    for p in posts[:20]:
        raw_section += (
            f"- **[{p['title'][:80]}]({p['url']})** "
            f"— r/{p['subreddit']} | ↑{p['score']} | {p['created']}\n"
        )

    return header + analysis + raw_section


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scout Reddit for Claude use cases")
    parser.add_argument("--days", type=int, default=7, help="Look back N days (default 7)")
    parser.add_argument("--save", action="store_true", help="Save markdown report")
    parser.add_argument("--json", action="store_true", help="Save raw JSON of posts")
    args = parser.parse_args()

    print(f"🔍 Scanning Reddit for Claude use cases (last {args.days} days)…")
    posts = collect_posts(args.days)
    print(f"✓ Found {len(posts)} unique posts. Analyzing with Claude…")

    analysis = analyze_posts(posts)
    report = build_report(posts, analysis, args.days)

    print("\n" + "═" * 72)
    print(report)
    print("═" * 72)

    if args.save:
        out = f"/Users/pandorasbox/apex-ai-orchestrator/reddit_scout_report.md"
        with open(out, "w") as f:
            f.write(report)
        print(f"\n✓ Saved: {out}")

    if args.json:
        out = f"/Users/pandorasbox/apex-ai-orchestrator/reddit_scout_report.json"
        with open(out, "w") as f:
            json.dump(posts, f, indent=2)
        print(f"✓ Saved: {out}")


if __name__ == "__main__":
    main()

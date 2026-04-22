#!/usr/bin/env python3
"""
x_scout.py — Web intelligence scout for Claude / Claude Code animation use cases.
Searches across X threads (indexed), YouTube, Medium, dev.to, HN, Reddit — everywhere
the Claude animation & use-case conversation lives.

Usage:
  python3 x_scout.py              # last 7 days, print report
  python3 x_scout.py --days 14   # wider window
  python3 x_scout.py --save      # also write x_scout_report.md
  python3 x_scout.py --json      # also write raw JSON
"""

import argparse, json, sys, textwrap, time
from datetime import datetime
from pathlib import Path
from ddgs import DDGS
import anthropic

OUT_DIR = Path(__file__).parent

# ─── Search queries ───────────────────────────────────────────────────────────

ANIMATION_QUERIES = [
    # Kling / Veo3 / video generation
    "kling AI video workflow tips 2026",
    "veo3 prompt workflow cinematic 2026",
    "google flow veo3 animation tips",
    "AI video generation cinematic workflow",
    "kling AI motion prompt technique",
    # Remotion + AI
    "remotion AI animation claude code",
    "remotion react animation workflow 2026",
    "remotion generative animation",
    # Claude + animation
    "claude code animation react framer gsap",
    "claude code CSS animation workflow",
    "\"claude code\" motion design visual",
    "claude code react animation component built",
    # Broader AI animation
    "AI generative animation pipeline 2026",
    "HTML cinematic experience web audio api animation",
    "AI video storytelling prompt engineering 2026",
    "elevenlabs kling video production workflow",
    "AI motion graphics pipeline tools 2026",
    # X threads (indexed versions)
    "twitter claude animation workflow thread",
    "x.com kling veo3 video prompt tips",
]

GENERAL_QUERIES = [
    "\"claude code\" use case shipped built 2026",
    "\"claude code\" MCP agent automation workflow",
    "\"claude code\" productivity tip 2026",
    "claude code outreach automation SaaS",
    "\"claude code\" game changer developer",
    "anthropic claude code new feature 2026",
    "claude code cowork multi-agent",
    "\"claude code\" real world project example",
    "claude MCP server interesting use case",
    "claude code sports recruiting SaaS",
]

# ─── Fetch ────────────────────────────────────────────────────────────────────

ANIMATION_KEYWORDS = [
    "animat", "motion", "veo", "kling", "remotion", "gsap",
    "framer", "video", "render", "frame", "css anim",
    "transition", "cinematic", "visual effect", "elevenlabs",
    "web audio", "keyframe", "easing", "stagger", "lottie",
    "three.js", "webgl", "canvas", "svg anim",
]

def is_animation(text):
    t = text.lower()
    return any(kw in t for kw in ANIMATION_KEYWORDS)

def collect_posts(days: int):
    timelimit = "w" if days <= 7 else "m"
    seen, posts = set(), []

    with DDGS() as ddgs:
        for i, q in enumerate(ANIMATION_QUERIES + GENERAL_QUERIES):
            if i and i % 6 == 0:
                time.sleep(1.2)
            try:
                print(f"  → {q[:68]}…")
                results = list(ddgs.text(q, timelimit=timelimit, max_results=10))
                for r in results:
                    uid = r.get("href", "")
                    if uid in seen:
                        continue
                    seen.add(uid)
                    title = r.get("title", "")
                    body  = r.get("body", "")
                    combined = f"{title} {body}"
                    posts.append({
                        "title":  title,
                        "body":   body[:500],
                        "url":    uid,
                        "source": _source_label(uid),
                        "is_animation": is_animation(combined),
                        "is_social":    any(s in uid for s in ["x.com/", "twitter.com/", "reddit.com/"]),
                    })
            except Exception as e:
                print(f"  [warn] {e}", file=sys.stderr)

    # Prioritise: animation > social > general
    posts.sort(key=lambda p: (p["is_animation"] * 2 + p["is_social"]), reverse=True)
    return posts

def _source_label(url):
    for domain, label in [
        ("youtube.com",  "YouTube"),
        ("youtu.be",     "YouTube"),
        ("x.com",        "X"),
        ("twitter.com",  "X"),
        ("reddit.com",   "Reddit"),
        ("medium.com",   "Medium"),
        ("dev.to",       "dev.to"),
        ("news.ycombinator", "HN"),
        ("github.com",   "GitHub"),
    ]:
        if domain in url:
            return label
    return "Web"

# ─── Analyze ─────────────────────────────────────────────────────────────────

def analyze_posts(posts):
    if not posts:
        return "No results found."

    client = anthropic.Anthropic()

    anim_posts    = [p for p in posts if p["is_animation"]][:30]
    general_posts = [p for p in posts if not p["is_animation"]][:20]

    def fmt(p):
        return f"[{p['source']}] {p['title'][:90]}\n{p['body'][:350]}\n{p['url']}"

    digest  = "=== ANIMATION / VIDEO / MOTION ===\n\n"
    digest += "\n\n---\n\n".join(fmt(p) for p in anim_posts)
    digest += "\n\n=== GENERAL CLAUDE / CLAUDE CODE ===\n\n"
    digest += "\n\n---\n\n".join(fmt(p) for p in general_posts)

    prompt = f"""You are the chief AI product intelligence analyst for Descieux Digital & Apex AI Consulting.

The operator (Von Descieux) is a senior AI strategist building:
- **Gladiator** — sports recruiting SaaS (Node/Express, Railway, DEADLINE April 19 2026)
- **Apex AI Orchestrator** — B2B outreach automation (DataTech + ZS Recycling clients)
- **Black Hollywood** — dark biblical AI video series (Iron Scripture: high contrast black/white/silhouette, ElevenLabs + Kling)
- **Madame Descieux** — luxury Creole culinary brand films (Flow TV style only, Google Veo3)
- **Video Pipeline** — script → shots → prompts → assembly tool (Remotion, React, Vite)
- **PropFlow** — real estate deal analyzer

His animation/video stack: **Remotion, Kling, Google Veo3/Flow, ElevenLabs narration, CSS keyframe animations, Web Audio API, SVG animations, HTML cinematic experiences**.

His income levers: Gladiator (SaaS revenue), Apex (client automation fees), Black Hollywood & Madame Descieux (brand/content monetization), PropFlow (investor demo).

---

Below are recent web results about Claude, Claude Code, AI animation, and AI video workflows.
Extract real signal. Skip generic hype. Be concrete and opinionated.

---

## 🎬 ANIMATION & VIDEO INSIGHTS

For each distinct technique, tool, or workflow:

### [Name]
**What's happening:** What specifically are people doing or discovering.
**Von's angle:** Exactly which project this helps (Black Hollywood / Madame Descieux / Remotion / Kling prompts / HTML films). Name it. One sentence.
**This week's action:** The single most concrete thing Von could try in under 2 hours.
**Why it compounds:** How mastering this pays off across multiple projects.
**Signal:** Low / Medium / High
**Source:** [title](url)

---

## ⚡ TOP CLAUDE CODE IDEAS (Non-Animation)

Top 5 ideas for Apex AI Consulting or Gladiator. Same format.

---

## 🔥 WHAT TO DO FIRST — Priority Stack

Three bullets. The three highest-leverage actions for this week.
Prioritize things that:
1. Hit the April 19 Gladiator deadline
2. Compound across Black Hollywood + Madame Descieux
3. Generate near-term revenue for Apex

Be opinionated. Don't hedge.

---

POSTS:
{digest}
"""

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text

# ─── Report ───────────────────────────────────────────────────────────────────

def build_report(posts, analysis, days):
    now  = datetime.now().strftime("%Y-%m-%d %H:%M")
    anim = sum(1 for p in posts if p["is_animation"])
    by_source = {}
    for p in posts:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1
    src_summary = "  ".join(f"{s}:{n}" for s, n in sorted(by_source.items(), key=lambda x: -x[1]))

    header = textwrap.dedent(f"""\
        # Web Scout — Claude + Animation Use Cases
        Generated: {now} | Window: last {days} days
        Posts: {len(posts)} total · {anim} animation-related
        Sources: {src_summary}

        ---
        """)

    raw = "\n\n---\n\n## All Sources\n"
    for p in posts:
        tag = " 🎬" if p["is_animation"] else ""
        raw += f"- [{p['source']}]{tag} **{p['title'][:80]}**\n  {p['url']}\n"

    return header + analysis + raw

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print(f"🔍 Scanning web for Claude animation use cases (last {args.days} days)…")
    posts = collect_posts(args.days)
    anim  = sum(1 for p in posts if p["is_animation"])
    print(f"✓ {len(posts)} posts ({anim} animation-related). Analyzing with Claude Opus…")

    analysis = analyze_posts(posts)
    report   = build_report(posts, analysis, args.days)

    print("\n" + "═" * 72)
    print(report)
    print("═" * 72)

    if args.save:
        path = OUT_DIR / "x_scout_report.md"
        path.write_text(report)
        print(f"\n✓ Saved: {path}")

    if args.json:
        path = OUT_DIR / "x_scout_report.json"
        path.write_text(json.dumps(posts, indent=2))
        print(f"✓ Saved: {path}")

if __name__ == "__main__":
    main()

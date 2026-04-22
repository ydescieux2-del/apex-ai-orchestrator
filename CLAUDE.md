# APEX AI ORCHESTRATOR — CLAUDE.MD
# Shared orchestration layer for multi-company outreach
# Owner: Von Descieux / Apex AI Consulting

## PURPOSE
Cross-company outreach orchestration: segment ownership, dedup, master audit log, company status gating.

## COMPANIES
- datatech: DataTech Disposition (SEG-1, SEG-3, SEG-7) — Active
- zs_recycling: ZS Recycling (SEG-5, SEG-6) — Setup
- company_3: TBD — EHS California (SEG-2) — Pending
- company_4: TBD — Financial/Banks (SEG-4) — Pending

## SHARED TEXT LAYOUT ENGINE
Branch: claude/text-layout-engine-qyNLb

Exports:
- generateEmailLayout — email template composition
- computeVerticalLayout — vertical text block positioning
- computeHorizontalLayout — horizontal text block positioning
- measureTextBlock — text dimension calculation

Install in other repos:
```
npm install ~/apex-ai-orchestrator
```

Import:
```js
import { generateEmailLayout, computeVerticalLayout, computeHorizontalLayout, measureTextBlock } from '@apex-ai/text-layout-engine';
```

## KEY FILES
- orchestrate.py — Main orchestration CLI
- deconflict.py — Cross-company segment dedup
- lead_sourcer.py — Lead discovery
- lead_scorer.py / lead_segmenter.py — Scoring & segmentation
- lead_verifier.py — Email verification
- inbox_monitor.py — Reply tracking
- send_emails.py — Dispatch (in james-outreach-harness)
- calendly_links.py — Meeting link generation
- company_config.json — Company registry

## WORKING RULES
- Always run --dry-run before --live
- Never send to a segment owned by another company
- Check master_send_log.json before any send
- Respect company status gating (pending = no sends)

## DATA DIRECTORY (added 2026-03-31)
`data/raw/` — All raw WIZA lead CSVs (source data for ALL companies).
Moved here from james-outreach-harness because these contain leads across all segments,
including segments owned by ZS Recycling and pending companies.

Files:
- May_2024_Leads.csv (6.8MB — all segments)
- WIZA_MayJune2024.csv (13.3MB — all segments)
- WIZA_Leads_June_2024.csv (6.2MB — all segments)
- WIZA_EHS_IT_Export.csv (5.0MB — SEG-2 + SEG-1)
- WIZA_Financial_CFO_Banks.csv (353KB — SEG-4)
- WIZA_ProcurementGovAdmin.csv (1.4MB — SEG-3)
- WIZA_ProcurementITServices.csv (1.7MB — SEG-1)
- WIZA_ProcurementHospitality.csv (1.5MB — SEG-7)
- CEOs_NonProfits_LA.csv (407KB — SEG-6, owned by ZS Recycling)
- web_discovered.csv (5KB — new web leads)

## FOLLOW-UP ENGINE (added 2026-03-31)
`follow_up_engine.py` — Cross-company follow-up cadence logic.
Moved here from james-outreach-harness because follow-up rules (cooldown, cross-company blocking)
are orchestrator-level concerns that apply to all companies.

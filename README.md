# Apex AI Consulting — Outreach Orchestration Layer

**Orchestrator: Von Descieux | Apex AI Consulting**
**Industry: Electronics Recycling / IT Asset Disposition (ITAD)**

This layer sits above individual company harnesses and enforces:
- Segment ownership (each segment belongs to exactly one company)
- No cross-company sends
- Master audit log across all companies
- Company status gating (pending companies cannot send)

---

## Company Registry

| Key | Company | Segments | Status |
|---|---|---|---|
| `datatech` | DataTech Disposition | SEG-1, SEG-3, SEG-7 | Active |
| `ez_recycling` | EZ Recycling | SEG-5, SEG-6 | Setup |
| `company_3` | TBD — EHS California | SEG-2 | Pending |
| `company_4` | TBD — Financial/Banks | SEG-4 | Pending |

---

## Usage

```bash
cd ~/apex-ai-orchestrator

# Show all companies, segments, and status
python orchestrate.py --status

# Cross-company dedup audit
python orchestrate.py --audit

# Dry run for a specific company + segment
python orchestrate.py --company datatech --segment SEG-1 --dry-run
python orchestrate.py --company ez_recycling --segment SEG-6 --dry-run --limit 5

# Live send (only after dry run confirmed)
python orchestrate.py --company ez_recycling --segment SEG-6
```

---

## Ownership Enforcement

If you attempt to send a segment a company does not own, the orchestrator blocks it:

```
[BLOCKED] Segment ownership violation
  Company      : EZ Recycling
  Requested    : SEG-1
  Owns         : SEG-5, SEG-6
  Actual owner : DataTech Disposition

  This send has been blocked. Each segment is exclusive to one company.
```

---

## Files

```
apex-ai-orchestrator/
├── orchestrate.py          — main orchestration CLI
├── company_config.json     — all companies, segments, ownership, rules
├── master_send_log.json    — auto-created; all sends across all companies
└── README.md               — this file
```

---

## Adding a New Company

1. Add an entry to `company_config.json` under `"companies"` with status `"pending"`
2. Assign their segment(s) in `"segment_registry"` — update `"owner"` field
3. Scaffold their harness (mirror `~/ez-recycling-harness`)
4. Update status to `"setup"` once harness is ready, `"active"` once credentials confirmed
5. Run `python orchestrate.py --status` to verify

---

## Billing Model

- Setup fee: $500/company
- Monthly retainer: $300/company
- See `apex_billing` in `company_config.json` for current terms

# Synthetic data – Audit Evidence Pack Agent (CO-04)

All data is synthetic (fixed seed 42). Regenerate with `python generate_data.py`.
Lenders, agencies, people and phone numbers are fictitious; holiday dates are representative, not an official gazette.

## Files

| File | Source | Rows | Notes |
|---|---|---|---|
| `data/d1_account_master_thin.csv` | D1 (thin) | 2,000 | account → borrower, lender, **state** (needed for state holidays) |
| `data/d4_contact_history.csv` | D4 | ~62k | voice, WhatsApp, SMS attempts, Jan–Jun 2026 |
| `data/d5_call_transcripts.csv` | D5 | ~48k turns | one row per speaker turn, connected calls only |
| `data/d10_consent_registry.csv` | D10 | ~4.9k | per-borrower, per-channel consent and opt-outs |
| `data/d11_template_registry.csv` | D11 | 60 | WhatsApp and SMS templates with approval status |
| `data/d12_policy_rules.csv` | D12 | 18 | calling hours, caps, notice deadlines, business-day definition, precedence |
| `data/notice_dispatch_history.csv` | CO-04 | ~3k | demand / pre-legal notices, Dec 2025–Oct 2026 |
| `data/holiday_calendar.csv` | CO-04 | 64 | national + state holidays 2026–27 |
| `data/collector_roster.csv` | CO-04 | 120 | collectors by agency |
| `data/certification_register.csv` | CO-04 | ~234 | DRA certificates with validity |
| `data/audit_requests/` | CO-04 | 3 requests | REQ-01 (email), REQ-02 (PDF letter), REQ-03 (vague email) + Annexure A sample CSVs |
| `data/ground_truth/` | answer key | | per account×check status, and per gap item |

## Time zones (important)

| Source | Column | Time zone |
|---|---|---|
| D4 contact history | `contact_ts` | **IST**, stored without offset |
| D5 transcripts | `turn_start_ts` | **UTC**, stored without offset |
| D10 consent | `captured_at`, `opt_out_at` | **UTC**, stored without offset |
| Notices, certificates, holidays | dates | local dates |

All borrowers are in India, so borrower local time = IST.

## Key joins
- D4.account_id → D1.account_id → D1.borrower_id → D10.borrower_id (consent is per borrower)
- D4.contact_id = D5.call_id
- D4.collector_id → collector_roster.collector_id. **The format varies by agency dialer**: `COL-0042` (most), `col42` (AG04), `COL0042` (AG05). Normalize before joining.
- D4.template_id → D11.template_id
- notice.account_id → D1.state → holiday_calendar.state

## Audit requests

| Request | Lender | Period | Sample | Checks |
|---|---|---|---|---|
| REQ-01 (email) | L001 | Jan–Mar 2026 | 300 | C1 consent, C2 template approved, C3 hours, C4 frequency, C5 certification |
| REQ-02 (PDF) | L003 | Jan–Jun 2026 | 200 | C1 verification before disclosure, C2 call recording, C3 notice timeline |
| REQ-03 (vague email) | L002 | Apr–Jun 2026 | 250 | C1 consent, C2 hours, C3 frequency, C4 verification, C5 certification |

## Ground truth – rules used by the reference checker

The answer key is computed by running a reference checker over the generated data, so it always matches the CSVs.

- **Statuses** per account×check: `GAP` (any failing item) > `CANNOT_DETERMINE` (any undecidable item) > `EVIDENCED`. `NOT_APPLICABLE` means there was nothing to test in the period (e.g. no WhatsApp messages).
- **Consent:** every WhatsApp message in the period needs a WHATSAPP consent with `captured_at` < message time (UTC) and no opt-out at or before the message.
- **Template:** a registered WHATSAPP template with status APPROVED and `approved_date` ≤ the send date.
- **Hours:** every voice attempt, IST, inside the window (inclusive). L002 is stricter: 09:00–18:00 (POL-L002-004).
- **Frequency:** unique `contact_id`s only (D4 has exact duplicate rows). Daily cap 3 per IST date; L002 is 2 from 2026-05-01. Weekly cap 10 per Mon–Sun week, counting attempts inside the request period. POL-GEN-002A (cap 4) is superseded.
- **Certification:** every voice attempt; the collector's certificate must cover the IST call date. An unknown collector (`COL-0999`) gives `CANNOT_DETERMINE`.
- **Verification:** connected calls (CONNECTED_* and WRONG_NUMBER). Amount mentioned before successful ID verification, after a failed one, or to a third party gives `GAP`. Missing transcript gives `CANNOT_DETERMINE`. Mentioning "your loan account" without an amount before verification is compliant.
- **Recording:** a connected call with no D5 transcript gives `GAP`.
- **Notice:** trigger date in the period; deadline = trigger + N business days (POL-GEN-004/005/006, with state holidays and 2nd/4th Saturdays). Compares **service** date, not dispatch date. No service date gives `GAP` (`no_proof_of_service`).
- **Severity:** from each request's own scale. REQ-02 notices are HIGH if more than 5 business days late or no proof, otherwise MEDIUM.

## Seeded traps (do not share with the agent)
- Consent captured minutes after the first WhatsApp message. About half of these are only caught when D4 IST is converted to UTC.
- Opt-out followed by more messages, sometimes with a later re-consent.
- Rejected, pending and SMS templates used on WhatsApp; a template used before its approval date.
- Out-of-hours calls; calls that are fine generally but outside L002's stricter window; near misses at 08:00 / 18:59.
- Daily cap breaches; weekly breaches with no daily breach; 3-per-day accounts that only breach under L002's May change; duplicate rows that inflate naive counts.
- Expired certificates, gaps between renewals, certificates not yet valid; calls exactly on `valid_to` (compliant).
- Dues disclosed before verification, after failed verification, and to wrong-number third parties; one missing transcript among a series of calls.
- Notices dispatched on time but served late; late dispatch; no proof of service; notices served exactly on a deadline that is only met once state holidays (20 cases) and 2nd/4th Saturdays (168 cases) are counted.

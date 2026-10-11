---
target: frontend/src/pages/Overview.tsx
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 3
target_identity: "file:/Users/aayush_goyal/Documents/college/semester_5/CCD/CCD project/frontend/src/pages/Overview.tsx"
target_fingerprint: "sha256:2750282b4a2061b0058ef86314cfb565d732d55d71d89323eb8bbd0303b2a6b5"
target_path: /Users/aayush_goyal/Documents/college/semester_5/CCD/CCD project/frontend/src/pages/Overview.tsx
timestamp: 2026-10-06T03-10-54Z
slug: frontend-src-pages-overview-tsx
closed: true
---
Method: dual-agent (A: design review sub-agent · B: detector/browser sub-agent)

## Design Health Score: 26/40 (Acceptable)
| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Failed/null risk or exposure silently drops the chip and finding card (Overview.tsx:35, :248) |
| 2 | Match System / Real World | 3 | "news near-real-time" stamp on a page with no news |
| 3 | User Control and Freedom | 2 | Edit replaces the page with no route; toggle not in URL |
| 4 | Consistency and Standards | 3 | bandTone paints Moderate in the through-funds amber |
| 5 | Error Prevention | 3 | Constraints stated in editor dek |
| 6 | Recognition Rather Than Recall | 3 | Own view drops Cash; rows sum to ~87% |
| 7 | Flexibility and Efficiency | 2 | No sort, no deep links, pointer-only chart, no arrow keys in Segmented |
| 8 | Aesthetic and Minimalist Design | 3 | Repeated per-row "Weight", two hero footnotes |
| 9 | Error Recovery | 2 | Exposure failure leaves an empty own list |
| 10 | Help and Documentation | 2 | "Risk 34" has no scale; method only in 11px footnote |

## Design Specificity
On-brief Groww-grade shell, but category-interchangeable in the first viewport. Look-through (the hero idea) appears only as rail-card text; signature toggle below fold and styled like a range filter.
Detector: CLI clean (0). In-page: tiny-text x2 (Overview.tsx:33 11.7px, :83 11.25px); low-contrast x3 avatar monograms brand-ink on brand-soft 4.24:1 (ui.tsx:54); repeating-stripes (false positive: semantic hatching). No h1; Segmented radios lack roving tabindex; white on accent hover 4.42:1.

## Priority Issues
- [P0] Signature view has no payoff on default demo (fund unmapped, direct = effective everywhere). Fix: default to a portfolio with a real ingested disclosure; keep "can't see into" as secondary. Command: shape, clarify.
- [P1] Look-through invisible in first viewport at projector res. Fix: dumbbell figure in finding card, promote toggle, ?view=own in URL. Command: bolder, layout.
- [P1] Own view broken/missing states: no loading/error for exposure (:189), Cash missing, bar hidden below md (:134), no live announcement. Command: harden.
- [P1] Not legible from back of room / print: 10px delta arrows (ui.tsx:45), 11-12px captions, 4.24:1 monograms, no h1, Segmented keyboard. Command: typeset, audit.
- [P2] Risk chip borrows amber and lacks scale. Fix: neutral "Risk 34/100 · Moderate". Command: colorize, clarify.

## Persona Red Flags
Alex: no sort, no URL state, full-page edit takeover, no arrow keys, no ₹ per company in own view.
Sam: no h1, radio tab-stop per option, pointer-only chart, unannounced re-rank, silent failures.
Evaluator at back of room: reads red chart first; thesis in 340px rail; 10px arrows and 11px captions unreadable; toggle off-screen at 1024x768.

## Minor Observations
Mobile share-line wrap and Edit wrap; rail ends ~125px above hero at 1440; inconsistent link affordance (chip vs filled link); −18.6% range vs −14.7% total under-explained; "Insights" vs "Recommendations" naming drift.

## Questions to Consider
Why open on "What you hold" if look-through is the hero? Should a price chart be the biggest object of a not-a-price-predictor? Could loading a disclosure live be the demo peak?

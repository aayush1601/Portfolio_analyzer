---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Surface brief: Portfolio Intelligence dashboard

Scope: the React app in `frontend/`. Pages: Overview (default), Look-through, Risk, News, Insights. Mode: **Operate**.
Audience/job: evaluators watching a projected demo, and the researcher; screens also become report figures.
Constraints: light (lit classroom + projector); never colour-only (signs, arrows, hatching); disclaimer wherever insights appear; "near-real-time" wording; no fabricated results; recommendations research-framed, no trade buttons.
Replaces: the Chart Desk world (2026-10-04), redesigned at the user's request toward an established Indian investing app (PRODUCT.md, Brand Commitments).

## Direction contract
THESIS: A Groww-grade investing app that a retail investor would recognise instantly, whose one twist is honesty about what you really own; refuses both the bare report look of the previous build and trade-button excitement.
OWN-WORLD: white ground with a faint cool-grey canvas, rounded 16px cards with hairline borders and a whisper of shadow; confident green brand (#00B386 family) for brand, gains and primary actions; coral red (#EB5B3C family) for losses and alerts; indigo (#5367FF family) for interactive selection and directly-held exposure; amber hatch for exposure through funds; Manrope with tabular figures; generous spacing, pill tabs and chips.
STORY: the visitor sees what the portfolio is worth and how it has done, then flips to what it really owns, then follows risk, news impact and research insights with their reasons.
FIRST VIEWPORT: white top bar (wordmark, underline tabs with a green active rule as in the reference apps, portfolio switcher, new-portfolio button); hero card with Current value at display size, invested, total returns and 1D returns with sign + arrow, risk score chip; value chart (green line, soft area, 1M/6M/1Y/3Y/5Y pills, hover crosshair); right column with an exposure-gap insight card and allocation bar; holdings list below. Signature move: the "What you hold ↔ What you really own" segmented toggle that re-ranks the holdings list from direct to look-through exposure, rows sliding to their new place.
FORM: user-pinned canon (Groww reference; Kite/Console and Smallcase quality bar); no concept-seed roll (pinned direction beats the roll).
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

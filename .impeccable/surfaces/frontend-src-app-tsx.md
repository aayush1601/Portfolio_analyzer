---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Surface brief: Portfolio Intelligence dashboard (MVP pages)

Scope: the React app in `frontend/`, pages Look-through (default), Holdings, Risk, News, Actions. Mode: **Operate**.
Audience/job: evaluators watching a projected demo, and the researcher inspecting pipeline output; screens also become static report figures (print, possibly greyscale).
Constraints: light ground (lit classroom + projector); never colour-only (hatching, signs, glyphs); disclaimer wherever recommendations appear; "near-real-time" wording; no fabricated results; must not read as a trading app or a terminal.
Memorable moment: the look-through dumbbell with its sentence headline.
Unresolved: fund holdings disclosures are not ingested yet, so fund look-through renders its designed "not loaded" state.

## Direction contract
THESIS: Every screen leads with a chart whose title states its finding in a sentence, newspaper-graphics-desk style; refuses the KPI-card-and-donut admin dashboard.
OWN-WORLD: cool newsprint-white ground (#F3F4F0), white panels, ink #18222D, deep-navy top bar; navy = direct, ochre diagonal hatch = via funds; vermilion only for alerts and cap breaches; P&L carries sign and ▲▼, never colour alone; Atkinson Hyperlegible type with tabular figures; ruled sortable tables, dense but airy.
STORY: the evaluator sees within seconds that the portfolio owns more of some companies and sectors than its direct holdings say, then follows why: risk, news impact, and actions with reasons and the cap that constrained them.
FIRST VIEWPORT: navy bar (product name, portfolio select, tabs, near-real-time stamp); KPI strip (value, day P&L, total P&L, risk score); a sentence-headline dumbbell of top companies (direct dot → effective end, gap hatched ochre) beside sector direct-vs-effective bars; sortable company table below. Signature move: the look-through dumbbell; each company keeps one name plate (symbol · sector · effective %) everywhere.
FORM: Chart Desk (newspaper data-graphics desk), candidate 4 of 7; seed key abca6e7c. Raises: vermilion owns only alerts (from Metro); one name plate per company (from Roster); blocked actions stay visible, struck and stamped with the rule (from Ticket Wallet); news rows in fixed columns that never reflow (from Split-flap).
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

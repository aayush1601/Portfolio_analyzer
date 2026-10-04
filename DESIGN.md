---
name: Portfolio Intelligence
description: Look-through portfolio exposure, risk, news impact and capped recommendations, drawn as a newspaper chart desk.
colors:
  ground: "#f3f4f0"
  panel: "#ffffff"
  ink: "#18222d"
  ink-2: "#4a5663"
  ink-3: "#66707c"
  rule: "#d6dad3"
  rule-soft: "#e8eae5"
  bar: "#163a5f"
  bar-ink: "#e9eef4"
  bar-ink-2: "#b3c2d3"
  direct: "#1f4e79"
  direct-soft: "#dbe5ef"
  via: "#b8770c"
  via-soft: "#f6ead2"
  alert: "#b3261e"
  alert-soft: "#f8e3e1"
typography:
  headline:
    fontFamily: "Atkinson Hyperlegible Next Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.4rem"
    fontWeight: 700
    lineHeight: 1.375
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Atkinson Hyperlegible Next Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 700
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Atkinson Hyperlegible Next Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Atkinson Hyperlegible Next Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 400
    lineHeight: 1.5
  figure:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, monospace"
    fontSize: "1.05rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
  number:
    fontFamily: "Atkinson Hyperlegible Mono, ui-monospace, monospace"
    fontSize: "0.9rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
rounded:
  stamp: "2px"
  control: "3px"
spacing:
  gutter-mobile: "20px"
  gutter-desktop: "24px"
  page-desktop: "32px"
  figure-gap: "20px"
components:
  button-primary:
    backgroundColor: "{colors.bar}"
    textColor: "{colors.bar-ink}"
    rounded: "{rounded.control}"
    padding: "6px 12px"
  button-primary-hover:
    backgroundColor: "{colors.direct}"
  button-quiet:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "6px 12px"
  input-field:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "6px 8px"
  figure:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    padding: "16px 24px"
  top-bar:
    backgroundColor: "{colors.bar}"
    textColor: "{colors.bar-ink}"
  stamp-add:
    backgroundColor: "{colors.direct}"
    textColor: "{colors.panel}"
    rounded: "{rounded.stamp}"
    padding: "2px 8px"
  stamp-reduce:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.stamp}"
    padding: "2px 8px"
  stamp-hold:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.stamp}"
    padding: "2px 8px"
---

# Design System: Portfolio Intelligence

## Overview

**Creative North Star: "The Chart Desk"**

A newspaper data-graphics desk run as a working app. Every screen leads with a chart whose headline states its finding as a full sentence, followed by a one-paragraph dek, the graphic, and a small source line ruled off beneath. The ground is a cool newsprint white, panels are plain white, and a single deep-navy bar carries the product name, portfolio select, tabs and the data-as-of stamp. Light by design: the app is projected in lit rooms and printed into reports, often in greyscale.

Density is that of a well-set business page: ruled, sortable tables and compact horizontal-bar graphics, generous line height, no decoration that does not encode data. Colour is a legend, not a mood: navy means held directly, ochre hatching means held through funds, grey hatching means not yet visible, and vermilion appears only when something crosses a limit. Every encoding also survives without colour, through hatch, sign, glyph or position.

The system refuses the KPI-card-and-donut admin dashboard, the trading terminal, and the dark "fintech" look.

**Key Characteristics:**
- Sentence headlines that state the finding, balanced across lines, max 60ch.
- Figures open with a 2px ink rule on top; no cards, no shadows, no radius.
- Navy / ochre-hatch / grey-hatch / vermilion as a fixed data legend across every chart.
- Tabular monospace figures with true minus signs and Indian digit grouping.
- One company, one name plate (symbol · sector · effective %), identical everywhere.
- One authored motion: chart marks draw out from their zero line.

## Colors

A cool, near-neutral newsprint palette with two data hues and one alarm hue, each owning exactly one meaning.

### Primary
- **Direct Navy** (direct): solid fill for anything held directly: dumbbell direct bars and dots, sector direct segments, stock segments of the weight strip, ScoreBar fill, positive SignedBar halves, histogram body bars, the filled ADD stamp, focus outlines and text carets.
- **Masthead Navy** (bar): the top bar and the primary button at rest. Darker than Direct Navy so the masthead reads as furniture, not data. Primary buttons hover to Direct Navy.
- **Masthead Ink / Masthead Ink Muted** (bar-ink / bar-ink-2): active tab and product name on the bar; inactive tabs, the as-of stamp and secondary bar controls.

### Secondary
- **Fund Ochre** (via) over **Fund Ochre Wash** (via-soft): only ever as the 135° diagonal hatch (2px ochre, 3px wash) with a 1px ochre outline, marking exposure added through funds; also the small "+x pts via funds" annotation text. Fund Ochre Wash doubles as the text-selection colour.

### Tertiary
- **Vermilion** (alert) and **Vermilion Wash** (alert-soft): cap breaches, the negative-news alert banner, error states, cap-rule chips on blocked actions, and the hatched tail of the risk histogram. Always paired with the drawn alert triangle.

### Neutral
- **Newsprint** (ground): page background behind figures.
- **Panel White** (panel): every figure, table, the figures strip and form surfaces.
- **Ink** (ink): headlines, body, figure top rules, table header rules, the VaR cut line.
- **Ink 2** (ink-2): deks, secondary values, cap lines (dashed), negative SignedBar halves, struck-through blocked actions.
- **Ink 3** (ink-3): source lines, axis labels, zero lines, bullet dots, the grey "not yet visible" hatch, disabled fills.
- **Rule / Rule Soft** (rule / rule-soft): control borders and section dividers; row dividers, source-line separators, ScoreBar track.

### Named Rules
**The Legend Rule.** Navy = held directly. Ochre hatch = added through funds. Grey hatch (1px ink-3 over rule-soft, 135°) = held but not yet visible. These meanings are fixed across every chart; never reuse a data colour for chrome or emphasis.

**The Vermilion Owns Alerts Rule.** Vermilion appears only where a limit is crossed or something failed: cap breaches, the news alert, errors, the risk tail. A loss is not an alert; losses carry a minus sign and a down triangle in ink, never red.

**The Greyscale Rule.** Every encoding must survive greyscale print: fund exposure is hatched, not just ochre; unmapped exposure is a differently pitched grey hatch; gains and losses carry a sign and a drawn triangle; breaches carry the alert triangle.

## Typography

**Display Font:** none; headlines use the body family at bold weight.
**Body Font:** Atkinson Hyperlegible Next (variable, self-hosted), with ui-sans-serif, system-ui fallback.
**Label/Mono Font:** Atkinson Hyperlegible Mono 400/600 (self-hosted), with ui-monospace fallback.

**Character:** A legibility-first humanist sans set like a news desk's chart titles, paired with its own mono so every number lines up in columns and reads unambiguously from the back of a room.

### Hierarchy
- **Headline** (700, 1.25rem mobile / 1.4rem from 640px, snug leading, -0.01em, balanced wrap): the sentence headline of every Figure. States the finding, max 60ch.
- **Title** (700, 1.05rem, -0.01em): the product name in the masthead.
- **Body** (400, 15px root, 1.5): deks (ink-2), table cells at 0.9rem, explanatory paragraphs.
- **Label** (400, 0.75–0.8rem): figures-strip labels, axis ticks, source lines (ink-3), table headers (600, ink-2).
- **Figure** (mono 600, 1.05rem, tabular): headline numbers in the figures strip.
- **Number** (mono 400, 0.75–0.9rem, tabular, -0.01em): every number in tables, charts, plates and annotations.

### Named Rules
**The Tabular Figure Rule.** Every number is set in the mono with tabular figures, true minus (−), Indian grouping for rupees, and "pts" for percentage-point differences.

**The Sentence Headline Rule.** A figure's title is a full sentence carrying the finding and its number ("30% of this portfolio sits inside funds we can't see into yet."), never a label like "Exposure".

## Layout

Full-bleed masthead and figures strip, then a centered main column (max 1440px, 16px side padding mobile, 32px from 640px, 24px vertical). Figures sit on Newsprint with a 20px gap.

- **Look-through:** two columns from 1024px (1.55fr / 1fr): dumbbell left, sector bars right; the company table spans both below. Risk uses 1.3fr / 1fr. Below 1024px everything stacks in one column.
- **Figure insets:** 20px horizontal on mobile, 24px from 640px. Tables bleed to the figure edges and keep the same inset on their first and last cells; they scroll horizontally below 640px width rather than reflow.
- **Figures strip:** a 2×2 grid on mobile; from 640px a single row of cells divided by 1px vertical rules.
- **Dumbbell rows:** from 640px a three-column grid (plate 6.5–11rem / track / 6.5rem value); on mobile the plate moves above the track.
- **Action rows:** three columns from 768px (plate and stamp / score breakdown / reasons), stacked below.
- **News rows:** fixed table columns that never reflow; the masthead as-of stamp hides below 768px.

## Elevation & Depth

Completely flat. No box shadows anywhere. Hierarchy comes from rules and tone: each figure opens with a 2px ink rule, panels are white on Newsprint, tables use a 1px ink header rule and soft row rules, and the masthead is the only dark mass. The only ring is the 2px panel-coloured ring that lifts the direct dot off its bar in the dumbbell.

### Named Rules
**The Rule-Not-Shadow Rule.** Separate with rules (2px ink to open a figure, 1px rule between sections, rule-soft between rows), never with shadows or floating cards.

## Shapes

Square by default. Figures, panels, bars and table rows have no radius. Controls (buttons, inputs, the portfolio select) take a barely-there 3px corner; stamps and rule chips 2px. Circles are reserved for data: the dumbbell's direct dot and effective ring, and 4px bullet dots in notes. Bars are flat-ended. Dashed lines always mean a threshold: the cap line, the VaR cut, and the divider before "not yet visible" rows.

## Components

### Buttons
- **Shape:** 3px corners, 6px 12px padding, 0.875rem semibold, optional 16px leading icon.
- **Primary:** Masthead Navy fill with Masthead Ink text; hovers to Direct Navy; disabled fills Ink 3.
- **Quiet:** Panel White with a 1px Rule border and Ink text; border darkens to Ink 3 on hover; disabled text Ink 3.
- **Focus:** global 2px Direct Navy outline, 2px offset.

### Inputs / Fields
- **Style:** Panel White, 1px Rule border, 3px corners, 0.9rem text.
- **Focus:** border shifts to Direct Navy (outline suppressed). Hover darkens border to Ink 3.
- **Error:** a vermilion message with `role="alert"` below the form.

### Navigation
- **Masthead:** Masthead Navy bar with product name (Title), portfolio select (translucent white 10% fill, 25% border), "New portfolio", and the "Prices to … · news near-real-time" stamp.
- **Tabs:** 0.95rem text; inactive Masthead Ink Muted, active Masthead Ink semibold with a 3px Masthead Ink underline and `aria-current`. Horizontally scrollable on narrow screens. Routes are hash links, so every view is bookmarkable.

### Figure (signature)
The unit of every screen: 2px Ink top rule, Panel White, sentence headline, optional ink-2 dek (max 60ch), the graphic, then an optional 0.8rem ink-3 source line set off by a rule-soft divider stating data provenance. An optional aside (legend) sits right of the headline.

### Name Plate
Symbol (semibold ink) · sector (ink-3, truncates) · effective % (mono, 0.85em, ink-2). Funds show their name. Identical wherever a company appears; the compact variant drops the sector.

### Dumbbell (signature)
One row per company on a shared 0-to-max track: navy bar to the direct dot, ochre-hatch bar from direct to the effective ring, a dashed ink-2 cap line labelled "15% cap", and the effective value on the right (vermilion with alert triangle above cap; "+x pts via funds" in ochre beneath). "Not yet visible" rows follow a dashed divider, in italic ink-2 with the grey hatch.

### SectorBars
Label and value above a thin track; navy direct segment plus ochre-hatch fund segment against the dashed sector cap. The unmapped row is italic with the grey hatch and no cap line.

### WeightStrip
A single 28px 100% bar, one segment per holding separated by 2px panel gaps: navy for stocks, ochre hatch for funds, Rule grey for cash. Labels (name + %) appear under segments of 6% or more.

### TailHistogram
SVG bars in Direct Navy; bins beyond the VaR cut take a vermilion 45° hatch over Vermilion Wash; a dashed ink line marks the cut, annotated in HTML ("1-in-N bad day: −x%", "N days fell further") so text stays legible at phone width.

### SignedBar and ScoreBar
SignedBar diverges from a 1px ink-3 zero line: positive navy to the right, negative ink-2 to the left; direction carries the sign. ScoreBar is a 6px rule-soft track with a navy fill and the mono score beside it; null shows "n/a".

### Sortable Table
1px Ink header rule, 0.8rem ink-2 semibold headers, rule-soft row rules, subtle Newsprint row hover. Sortable headers are buttons with `aria-sort`; the active one shows a small drawn triangle. Numeric columns right-aligned in the mono.

### Delta
Signed mono figure with a drawn up/down triangle in ink-2 ahead of it. Never coloured green or red.

### Stamp
Action label in a 2px-bordered 2px-radius box, 0.8rem bold, 0.06em tracking: BUY/INCREASE filled Direct Navy with white text; REDUCE/SWITCH outlined in Ink; HOLD outlined Ink 3 with ink-2 text. When a cap overrides a call, the original action stays visible, struck through in ink-2, beside the new stamp, followed by vermilion-outlined rule chips naming the cap.

### Status
Loading: Panel White with a 2px Rule top rule and a pulsing "Loading …" line in ink-3. Error: 2px Vermilion top rule, "Couldn't load …" in semibold ink, the message in ink-2, and a quiet "Try again" button. Alerts: Vermilion Wash band with a 2px vermilion top rule and the alert triangle.

### Motion
One authored moment: chart marks draw out from their origin (`scaleX` 0 → 1, 700ms, cubic-bezier(0.16, 1, 0.3, 1)), staggered 40ms per row with the fund segment trailing by 200ms. Everything else is a plain colour transition. Reduced motion collapses all animation to 1ms.

### Print
Print forces a white ground and hides tabs and the "New portfolio" control; hatching and signs carry every encoding in greyscale.

## Do's and Don'ts

### Do:
- **Do** open every figure with a 2px Ink rule and a sentence headline that states the finding with its number.
- **Do** end every figure with a source line naming the data, model or rules version behind it.
- **Do** hatch fund exposure (ochre) and not-yet-visible exposure (grey) so they survive greyscale.
- **Do** set every number in Atkinson Hyperlegible Mono with tabular figures and a true minus.
- **Do** keep one name plate per company, identical in every view.
- **Do** keep a blocked action visible, struck through, next to the stamp and the cap that overrode it.
- **Do** show the disclaimer wherever recommendations appear, and say "near-real-time", never "real-time".

### Don't:
- **Don't** use vermilion for losses, emphasis or decoration; it means a limit was crossed or something failed.
- **Don't** colour gains green and losses red; use sign plus drawn triangle in ink.
- **Don't** use KPI cards, donuts, gauges or shadows; the figures strip is ruled cells, not cards.
- **Don't** introduce a dark theme or terminal styling; this is projected in lit rooms and printed.
- **Don't** add a second motion idea; marks draw from zero, nothing else moves.
- **Don't** use glyph or emoji icons; icons are authored inline SVG on a 16px grid with a 1.5 stroke.

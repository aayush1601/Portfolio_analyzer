---
name: Portfolio Intelligence
description: A Groww-grade investing app whose one twist is honesty about what you really own.
colors:
  canvas: "#f5f6f8"
  panel: "#ffffff"
  ink: "#1e2235"
  ink-2: "#565b70"
  ink-3: "#6e7387"
  line: "#e5e7ee"
  line-soft: "#f0f1f5"
  brand: "#00b386"
  brand-ink: "#00845f"
  brand-soft: "#e5f7f2"
  brand-deep: "#006c4e"
  loss: "#c53c22"
  loss-soft: "#fdece8"
  accent: "#5367ff"
  accent-ink: "#3a4ad8"
  accent-soft: "#eef0ff"
  via: "#e39a12"
  via-soft: "#fdf2d8"
  via-ink: "#7a4f00"
typography:
  display:
    fontFamily: "Manrope Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "3.1rem"
    fontWeight: 800
    lineHeight: 1.25
    letterSpacing: "-0.02em"
    fontFeature: "\"tnum\""
  title:
    fontFamily: "Manrope Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 700
    lineHeight: 1.375
  body:
    fontFamily: "Manrope Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.5
  label:
    fontFamily: "Manrope Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 700
    lineHeight: 1.4
  caption:
    fontFamily: "Manrope Variable, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  avatar-sm: "6px"
  control: "8px"
  avatar: "12px"
  card: "16px"
  pill: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  card-x: "20px"
  card-x-wide: "24px"
  gap: "20px"
  page-x: "32px"
components:
  button-primary:
    backgroundColor: "{colors.brand-ink}"
    textColor: "{colors.panel}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
  button-quiet:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "20px 24px"
  segmented:
    backgroundColor: "{colors.line-soft}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "4px"
  segmented-active:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
  chip-neutral:
    backgroundColor: "{colors.line-soft}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  chip-gain:
    backgroundColor: "{colors.brand-soft}"
    textColor: "{colors.brand-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  chip-loss:
    backgroundColor: "{colors.loss-soft}"
    textColor: "{colors.loss}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  chip-accent:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
  insight-pill:
    backgroundColor: "{colors.brand-soft}"
    textColor: "{colors.brand-ink}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  nav-tab:
    textColor: "{colors.ink-2}"
    padding: "18px 12px"
  nav-tab-active:
    textColor: "{colors.ink}"
    padding: "18px 12px"
---

# Design System: Portfolio Intelligence

## Overview

**Creative North Star: "The Honest Investing App"**

A retail investor should recognise this instantly as an established Indian investing app: white cards floating on a faint cool-grey canvas, one confident green, big tabular hero numbers, pill tabs and time-range charts. Its one twist is honesty about what you really own. Every surface that shows exposure splits it into what you hold directly (indigo) and what your funds add on top (amber hatch), and anything not yet visible is shown as grey hatch rather than guessed.

The world is light because it is projected in lit rooms and printed into a report. Density is generous: cards breathe at 20 to 24px, the grid gaps at 20px, and figures carry the hierarchy rather than decoration. Meaning never rides on colour alone: gains and losses carry a sign and a filled triangle, through-fund exposure is a hatch pattern that survives greyscale, and breaches carry an alert glyph.

Motion has exactly one idea: values travel along their axis. Bars draw out from zero, the effective-exposure ring travels from the direct dot to where you really are, and re-ranked lists glide rows to their new place. Insights are research-framed: labelled pills with reasons and a disclaimer, never trade buttons.

**Key Characteristics:**
- White 16px cards with a hairline border and a whisper of shadow on a cool canvas.
- Manrope throughout, weight 500 body, 700 to 800 for figures and titles, tabular numerals for every number.
- Green is the brand and gains; coral is losses and alerts; indigo is selection and direct exposure; amber hatch is exposure through funds.
- Signed figures always pair sign, arrow and colour.
- One motion idea: values travel along their axis.

## Colors

A cool, near-white neutral field carrying four signal hues, each with one job.

### Primary
- **Market Green** (brand): the app mark, the active tab underline, the value-chart line and soft area fill when the range is up, the gain side of signed bars, the Low band of the riskometer, the text-selection tint (brand-soft).
- **Deep Market Green** (brand-ink): primary button fills and gain text (Delta, gain chips, Add pills). Brand green is too light for white text or small type; brand-ink carries both. Hover deepens to **brand-deep** (#006c4e).

### Secondary
- **Signal Indigo** (accent): interactive selection and focus (focus ring, caret, field focus border), directly-held exposure in every bar and dot, score bars, histogram body, reason bullets. **Indigo Ink** (accent-ink) is the text on indigo-soft (Switch pill, accent chip, "See what you really own" link); indigo-soft also grounds the insights disclaimer banner.

### Tertiary
- **Coral Loss** (loss): losses, falling value line, breaches above a cap, error states, triggered-rule chips, the hatched VaR tail. Always paired with a down triangle, a minus sign or an alert glyph.
- **Fund Amber** (via): exposure that reaches you through funds, drawn as a 135-degree hatch (2px amber, 3px via-soft) with a 1px amber outline. The only solid amber use is the riskometer's Moderate band (the fund-factsheet convention). Text naming through-fund amounts uses **via-ink** (#7a4f00), the one dark amber ink.

### Neutral
- **Cool Canvas** (canvas): the page ground and the portfolio switcher fill; table-row hover at 70%.
- **Panel White** (panel): cards, top bar (95% with backdrop blur), active segment, quiet buttons, fields.
- **Ink** (ink): headings, figures, chart tooltip ground, riskometer needle.
- **Ink 2** (ink-2): secondary text, inactive tabs and segments, deks.
- **Ink 3** (ink-3): captions, axis labels, sources, overridden calls, the not-yet-visible hatch stroke.
- **Line** (line): card and field borders, table head rule. **Line Soft** (line-soft): row dividers, bar tracks, segmented and neutral chip grounds.

### Named Rules
**The One Job Per Hue Rule.** Green means brand and gain, coral means loss or alert, indigo means selection or direct, amber means through funds. Never borrow a hue for decoration.

**The Hatch Means Hidden Rule.** Amber hatch marks exposure that arrives through funds; grey hatch (1px ink-3 on line-soft, 6px period) marks holdings not yet visible. Hatch is never decorative and never used for anything else.

**The Ink-For-Text Rule.** Signal hues on small type use their ink variant (brand-ink, accent-ink, dark amber); the bright hue is for fills, lines and marks.

## Typography

**Display Font:** Manrope Variable (with ui-sans-serif, system-ui)
**Body Font:** Manrope Variable
**Label/Mono Font:** Manrope with tabular figures

**Character:** One friendly geometric grotesque doing everything; hierarchy comes from weight and size, not from a second family. Medium (500) body keeps it confident on a projector.

### Hierarchy
- **Display** (800, 2.3rem on phones rising to 3.1rem from 640px, tight, -0.02em, tabular): the Current value hero figure only.
- **Wordmark** (800, 1.05rem, -0.01em): "Portfolio Intelligence" beside the mark.
- **Title** (700, 1.08rem rising to 1.15rem, snug, balanced wrap): card titles, written as plain-language findings.
- **Figure** (700, 1.05rem, tabular): hero sub-stats (Invested, Total returns, 1D returns).
- **Body** (500, 15px root, 0.88 to 0.9rem in cards, 1.5): deks, reasons, table cells; deks cap at 72ch.
- **Label** (700 to 800, 0.78 to 0.85rem): buttons, segments, chips, pills, table heads; tabs are 0.92rem, 600 inactive and 800 active.
- **Caption** (500, 0.72 to 0.8rem, ink-3): stat labels, axis ends, sources, "not yet visible" sub-lines.

### Named Rules
**The Tabular Figures Rule.** Every number (money, percent, score, axis) is set with tabular numerals so columns and hero figures never jitter.

**The Sentence Case Rule.** No uppercase labels, no tracked-out small caps. Labels are short sentence-case words.

## Layout

Single centred column, max 1240px, page padding 16px (32px from 640px), 24px vertical. A sticky white top bar carries the mark and wordmark, underline tabs, and the portfolio switcher with a New portfolio button. Pages are grids of cards with 20px gaps: Overview pairs a fluid main column with a 340px right rail from 1024px (hero and value chart left; exposure-gap insight and allocation right; holdings list spanning both); Risk splits 1.3fr / 1fr. Cards pad 20px, 24px from 640px; list rows pad 14px vertically.

Below 768px the tab row drops to its own full-bleed line and scrolls horizontally; the switcher fills the remaining width and New portfolio collapses to its plus icon. Tables keep a 640px minimum and scroll inside their card; multi-column rows (insights, news) stack to one column. Weight and mini-bar columns hide on narrow screens; the effective figure stays.

Print: the canvas turns white and navigation, edit and new-portfolio controls disappear, so a page prints as its cards. Projector: nothing depends on thin strokes or subtle contrast; hatches and triangles carry meaning in greyscale.

## Elevation & Depth

Nearly flat. Cards lift off the canvas with a hairline border plus a soft two-layer shadow; nothing else floats except the active segment pill and the chart tooltip. Depth never encodes anything beyond "this is a card" and "this is selected".

### Shadow Vocabulary
- **Card whisper** (`box-shadow: 0 1px 2px rgb(30 34 53 / 0.04), 0 4px 16px -6px rgb(30 34 53 / 0.08)`): every card.
- **Segment lift** (`box-shadow: 0 1px 3px rgb(30 34 53 / 0.12)`): the active option in a segmented control.

### Named Rules
**The Whisper Rule.** Shadows are barely there; the border does the separating. Never deepen a card shadow for emphasis.

## Shapes

Friendly rounding at three sizes: 16px cards and status panels; 8px buttons, fields and error boxes; full pills for segments, chips, insight pills, the switcher and every bar and track. Bars are capsule-ended; the through-fund segment rounds only its right end so it reads as continuing the direct bar. Avatars are 12px tiles (6px at small size). Icons are authored inline SVG on a 16px grid with a 1.5 stroke and round caps; gain and loss triangles are filled. The app mark is a 9px-radius green tile holding a white lens over a rising line.

## Components

### Buttons
- **Shape:** gently rounded (8px).
- **Primary:** brand-ink fill, white bold 0.88rem label, 8px 14px; hover deepens; disabled falls to ink-3. The header New portfolio button uses the same fill as a full pill.
- **Quiet:** white with a line border, ink text; hover darkens the border to ink-3.
- **Focus:** global 2px indigo outline at 2px offset.

### Segmented control
A line-soft pill track with a 4px inset; options are bold 0.82rem pills, the active one white with the segment lift. Used for value-chart ranges (1M to 5Y), the holdings view, and news order.

### Chips and Insight pills
- **Chip:** full pill, bold 0.78rem, tinted ground with ink-variant text in five tones (neutral, gain, loss, accent, via).
- **Insight pill:** weight 800, 4px 12px: Add (green), Hold (neutral), Reduce (coral), Switch (indigo). When a cap overrides the scored call, the original call sits beside it in ink-3 with a 2px strike drawn through it, never hidden.

### Cards / Containers
- **Corner Style:** 16px. **Background:** panel. **Border:** 1px line. **Shadow:** card whisper.
- **Anatomy:** optional title (a finding sentence) with dek and right-side aside, body, optional source footer above a line-soft rule in 0.78rem ink-3.
- **Status:** loading is a plain card reading "Loading ..."; error is a loss-soft card with a coral-tinted border, the message and a Try again quiet button; stale data dims to 55% while refetching.

### Inputs / Fields
- **Style:** white, 1px line border, 8px radius, 0.9rem medium; hover border ink-3.
- **Focus:** border turns indigo. **Error:** loss-soft box with coral text.

### Navigation
White sticky bar with backdrop blur. Tabs are text links with a 3px bottom rule: inactive ink-2 semibold, active ink extrabold over a brand-green rule. The portfolio switcher is a canvas-filled pill select.

### Identity
- **Avatar:** two-initial monogram tile, stable tone per company from four tinted pairs (indigo, green, amber, neutral).
- **Plate:** symbol (bold) · sector (ink-3) · effective % (tabular), identical wherever a company appears.
- **Delta:** signed figure with a filled triangle; brand-ink up, coral down, ink-2 flat.

### Charts
- **ValueChart (hero):** a 2.25px line in brand green (coral if the range fell) over a soft vertical gradient fill; a dashed ink-3 Invested baseline labelled on the chart; hover crosshair, ringed dot and an ink tooltip with value and date. The line is deliberately static.
- **Dumbbell:** indigo direct bar and dot, amber-hatched through-fund extension, and an indigo ring at effective exposure that travels from the dot; dashed cap line; breaches go coral with an alert glyph; not-yet-visible rows in grey hatch below a dashed divider.
- **SectorBars:** the same direct-plus-hatch bar against the sector cap.
- **AllocationBar:** one 12px capsule split into stocks (indigo), mutual funds (amber hatch), cash (ink-3 at 40%), with a legend list.
- **Riskometer:** the semicircle fund-factsheet gauge, Low green / Moderate amber / High coral, inactive bands at 28%, ink needle easing to the score.
- **TailHistogram:** indigo day bars, the VaR tail hatched in coral, a dashed cut line annotated in words.
- **SignedBar / ScoreBar:** a diverging green-or-coral bar about a zero tick; a 0 to 100 indigo capsule with its number.

### Signature: What you hold / What you really own
The holdings card's segmented toggle re-ranks the list from statement holdings (value, weight, Delta) to look-through companies (direct-plus-hatch mini bar, effective %, "x% direct"), with unseen funds as italic grey-hatch rows. Rows glide to their new place through a View Transition.

### Motion
One idea, values travel along their axis, all on `cubic-bezier(0.16, 1, 0.3, 1)`:
- **draw-x** (700ms): bars grow from zero, staggered 40 to 60ms per row, the through-fund segment 200ms later.
- **travel-x** (700ms): the effective ring slides out from the direct dot.
- **glide** (300 to 600ms): needle, cut line and histogram bars ease to new values.
- **re-rank** (300ms View Transition): sortable tables, the holdings toggle and news order.
- **strike** (320ms after 450ms): the overridden call is struck once.
- **refetch:** content dims to 55% (150ms) and settles back (250ms).
- **Reduced motion:** animations and transitions collapse to 1ms and re-rank skips the View Transition.

## Do's and Don'ts

### Do:
- **Do** pair every gain or loss with a sign and a filled triangle, not just green or coral.
- **Do** split exposure into indigo direct plus amber-hatched through-funds, and show unseen funds as grey hatch instead of guessing.
- **Do** use brand-ink, not brand green, for button fills and gain text.
- **Do** set every number with tabular figures.
- **Do** write card titles as plain-language findings and keep the disclaimer wherever insights appear.
- **Do** animate only along the value's axis, on the one ease curve, with the reduced-motion path intact.

### Don't:
- **Don't** add trade-style Buy or Sell buttons; insights are labelled pills with reasons.
- **Don't** use amber hatch or grey hatch for anything other than through-fund and not-yet-visible exposure.
- **Don't** animate the value line drawing in; it is static by design.
- **Don't** add uppercase eyebrows or kickers above titles.
- **Don't** use Groww's logo, name, exact brand assets or copy; the reference is inspiration only.
- **Don't** go dark; the world is light for projectors and print.

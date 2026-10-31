---
name: Clear Context
description: Self-hosted fact-checking workspace; evidence for each detail of a claim.
colors:
  meta-blue: "#0064e0"
  meta-blue-deep: "#0050b5"
  meta-blue-wash: "#e5eefc"
  muse-blue: "#3b81e0"
  rail-navy: "#0f2742"
  rail-hover: "#19395d"
  rail-line: "#27445f"
  rail-ink: "#e8eef7"
  rail-muted: "#a3b5ca"
  jolly-cream: "#f3e6d6"
  jolly-cream-soft: "#fbf5ee"
  quote-highlight: "#f7dfc0"
  page: "#f4f7fb"
  surface: "#ffffff"
  ink: "#1c2b33"
  muted: "#536372"
  line: "#d8e1eb"
  line-strong: "#b0bfcf"
  success: "#1b6b45"
  success-soft: "#e2f1e8"
  warning-ink: "#6e4a00"
  warning-soft: "#fbf1df"
  danger: "#b42318"
  danger-soft: "#fdecea"
typography:
  headline:
    fontFamily: "Onest Variable, Segoe UI, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.026em"
  title:
    fontFamily: "Onest Variable, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 500
    lineHeight: 1.5
  body:
    fontFamily: "Onest Variable, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "Onest Variable, Segoe UI, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.4
  data:
    fontFamily: "JetBrains Mono Variable, ui-monospace, Consolas, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "14px"
  tile: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "36px"
components:
  button-primary:
    backgroundColor: "{colors.meta-blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    height: "42px"
  button-primary-hover:
    backgroundColor: "{colors.meta-blue-deep}"
  rail-item-active:
    backgroundColor: "{colors.jolly-cream}"
    textColor: "{colors.rail-navy}"
    rounded: "{rounded.sm}"
  quote-mark:
    backgroundColor: "{colors.quote-highlight}"
    textColor: "{colors.ink}"
    rounded: "{rounded.xs}"
  stage-glyph-tile:
    backgroundColor: "{colors.meta-blue-wash}"
    textColor: "{colors.meta-blue}"
    rounded: "{rounded.tile}"
    size: "88px"
---

# Design System: Clear Context

## Overview

**Creative North Star: "The Annotated Source"**

The workspace is a reading desk for evidence. A deep navy rail holds navigation and history; the work area is a cool white page where claims, sources and quoted passages are read closely. Meta blue marks every action and link. The cream of Muse's mascot appears only twice: on the brand mark and the active rail item, and as the highlighter over quoted source text, so warmth always means "this is the passage that matters".

Density is that of a working tool: compact rows, clear grouping, no marketing hero inside the app. Motion is reserved for real work in progress: each recorded investigation stage has its own drawn glyph that moves only while that stage runs.

**Key Characteristics:**
- Navy rail, white work surface, one blue for actions.
- Cream is a highlighter, never a background.
- Status color only where it carries a verdict on evidence.
- Stage glyphs instead of spinners; still under reduced motion.

## Colors

A restrained blue system with one warm accent.

### Primary
- **Meta Blue** (#0064e0): primary buttons, links, focus rings, the running stage. 5:1 on white.
- **Meta Blue Deep** (#0050b5): hover and pressed states.
- **Muse Blue** (#3b81e0): the upper letter of the mark only.

### Secondary
- **Jolly Cream** (#f3e6d6): the active rail item and the mark on dark grounds.
- **Quote Highlight** (#f7dfc0): `<mark>` over the exact source excerpt and text selection.

### Neutral
- **Rail Navy** (#0f2742) with **Rail Ink** (#e8eef7) and **Rail Muted** (#a3b5ca): the navigation rail.
- **Page** (#f4f7fb), **Surface** (#ffffff): work area and cards.
- **Ink** (#1c2b33), **Muted** (#536372): text. **Line** (#d8e1eb), **Line Strong** (#b0bfcf): dividers and input borders.

### States
Supported uses **Success** (#1b6b45 on #e2f1e8), contradicted uses **Danger** (#b42318 on #fdecea), unsettled details use the warning pair (#6e4a00 on #fbf1df). Mantine badges map these through `teal`, `red`, `orange`, `yellow` and `gray`.

**The Highlighter Rule.** Cream marks the passage a finding rests on. Do not use it for panels, page backgrounds or decoration.

**The One Blue Rule.** Blue never means "true". Verdict colors come only from the state palette.

## Typography

**Body and headings:** Onest Variable (Segoe UI fallback), full Latin Extended for Turkish.
**Data:** JetBrains Mono Variable for timestamps, counts, key previews and claim numbers; never as decoration.

### Hierarchy
- **Headline** (600, 34px, 1.2): page titles such as "Check the context" or the running stage name.
- **Title** (500, 20px, 1.5): claim statements in the report.
- **Body** (400, 14px, 1.7): explanations, source excerpts.
- **Label** (600, 13px): stage names, section headings in the rail and panels; sentence case.
- **Data** (400, 11–12px, mono, tabular numbers).

**The No Eyebrow Rule.** No small uppercase labels above headings. A number that orders claims sits beside the heading, not above it.

## Layout

A 244px fixed rail and a fluid work area (max 1160px for intake, report with a 280px aside). Below 900px the rail becomes a drawer opened from the top bar. Spacing follows 4/8/16/24/36px; more space above a heading than below it.

## Elevation & Depth

Flat. Cards are separated by a 1px line on a tinted page; there are no decorative shadows. Depth on the rail comes from tone (navy, hover navy, cream for active).

## Shapes

Inputs and cards use 10–14px radii; buttons 6px; stage glyph tiles 16px. Pills only for small badges.

## Components

- **Rail:** brand mark (dark tone), primary "New investigation" button, nav items, history with state words only for queued, running or failed items.
- **Process timeline:** circle markers; check for recorded stages, X for a stop, the stage glyph for the running stage. Words appear only for Running and Stopped; the rest stay available to screen readers.
- **Current stage:** an 88px blue-wash tile with the animated glyph, the stage title as the page heading and its description.
- **Evidence excerpt:** quoted text with a 1px rule; the matched passage in Quote Highlight.

## Do's and Don'ts

- Do derive progress from recorded backend events.
- Do keep the official Meta wordmark and Jolly image unaltered, as attribution only.
- Don't add pulsing dots, eyebrows, period-ended headings, italic accent words, gradient text, glow or glass.
- Don't add colored side borders thicker than 1px to callouts.
- Don't animate anything that is not actual work in progress.

## Interaction rules

- Clipboard, file picker and drag/drop feed the same bounded media intake. Previews stay local and removable; object URLs are released.
- An investigation starts only from the submit control. Examples fill the form; they do not submit it. Input survives request errors.
- Pending, running, complete, stopped and unavailable stay distinct. No invented percentages.
- One column on phones, accessible drawer navigation, 16px inputs, keyboard focus and reduced motion.

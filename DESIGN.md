---
name: Clear Context
description: Self-hosted fact-checking workspace; evidence for each detail of a claim.
colors:
  meta-blue: "#0064e0"
  meta-blue-bright: "#0b74ff"
  link-blue: "#5aa2ff"
  link-blue-soft: "#8dbdff"
  blue-wash: "#0f2442"
  rail-navy: "#0a1322"
  rail-hover: "#14233a"
  rail-ink: "#e8eef7"
  jolly-cream: "#f3e6d6"
  on-highlight: "#0b1626"
  page: "#060b14"
  surface: "#0d1726"
  ink: "#e8eef7"
  muted: "#98a9bf"
  line: "#1b2a42"
  line-strong: "#2d4264"
  success: "#5fd39a"
  success-soft: "#0f2a1f"
  warning-ink: "#f1c470"
  warning-soft: "#2a2110"
  danger: "#ff8f84"
  danger-soft: "#2e1411"

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
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    height: "42px"
  button-primary-hover:
    backgroundColor: "{colors.meta-blue-bright}"
  rail-item-active:
    backgroundColor: "{colors.jolly-cream}"
    textColor: "{colors.rail-navy}"
    rounded: "{rounded.sm}"
  quote-mark:
    backgroundColor: "{colors.jolly-cream}"
    textColor: "{colors.on-highlight}"
    rounded: "{rounded.xs}"
  stage-glyph-tile:
    backgroundColor: "{colors.blue-wash}"
    textColor: "{colors.link-blue}"
    rounded: "{rounded.tile}"
    size: "88px"
---

# Design System: Clear Context

## Overview

**Creative North Star: "The Annotated Source"**

A dark reading desk for evidence. Near-black navy holds the page, slightly lifted navy holds cards and the navigation rail, and cream appears only where a source passage is highlighted. Meta blue marks actions and links. Nothing glows for decoration: light on this screen means "this is the passage that matters".

Density is that of a working tool. Motion is reserved for real work in progress: each recorded investigation stage has its own drawn glyph that moves only while that stage runs, and it stays still under reduced motion.

**Key Characteristics:**
- Dark by default (page, rail, report); no light mode.
- One action blue; links use a lighter blue for contrast on dark.
- Cream is a highlighter and the mark, never a panel color.
- Verdict colors only from the state palette; blue never means "true".

## Colors

### Primary
- **Meta Blue** (#0064e0): filled buttons, white text. **Bright** (#0b74ff) on hover.
- **Link Blue** (#5aa2ff, soft #8dbdff): links, focus rings, the running stage.

### Secondary
- **Jolly Cream** (#f3e6d6): the active rail item, the logo, and highlighted source quotes (dark text #0b1626 on it).

### Neutral
- **Page** (#060b14), **Surface** (#0d1726), **Rail** (#0a1322, hover #14233a).
- **Ink** (#e8eef7), **Muted** (#98a9bf), **Line** (#1b2a42), **Line Strong** (#2d4264).

### States
Supported #5fd39a on #0f2a1f; contradicted #ff8f84 on #2e1411; unsettled #f1c470 on #2a2110.

**The Highlighter Rule.** Cream marks the passage a finding rests on. Do not use it for panels or decoration.

**The One Blue Rule.** Blue never means true.

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

Flat. Cards are one tone lighter than the page with a 1px line; no decorative shadows or glows. Depth comes from tone.

## Shapes

Inputs and cards use 10–14px radii; buttons 6px; stage glyph tiles 16px. Pills only for small badges.

## Components

- **Rail:** brand mark (dark tone), primary "New investigation" button, nav items, history with state words only for queued, running or failed items.
- **Process timeline:** circle markers; check for recorded stages, X for a stop, the stage glyph for the running stage. Words appear only for Running and Stopped; the rest stay available to screen readers.
- **Current stage:** an 88px blue-wash tile with the animated glyph, the stage title as the page heading and its description.
- **Evidence excerpt:** quoted text with a 1px rule; the matched passage in Quote Highlight.

## Do's and Don'ts

- Do derive progress from recorded backend events.
- Do keep the official Meta wordmark and Jolly image unaltered, as attribution only; the wordmark sits on a light chip because its lettering is dark.
- Don't add pulsing dots, eyebrows, period-ended headings, italic accent words, gradient text, glow or glass.
- Don't add colored side borders thicker than 1px to callouts.
- Don't animate anything that is not actual work in progress.

## Interaction rules

- Clipboard, file picker and drag/drop feed the same bounded media intake. Previews stay local and removable; object URLs are released.
- An investigation starts only from the submit control. Examples fill the form; they do not submit it. Input survives request errors.
- Pending, running, complete, stopped and unavailable stay distinct. No invented percentages.
- One column on phones, accessible drawer navigation, 16px inputs, keyboard focus and reduced motion.

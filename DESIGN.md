---
name: Clear Context
description: Self-hosted fact-checking workspace; evidence for each detail of a claim.
colors:
  blue-deep: "#0161dd"
  blue-bright: "#047bf2"
  gray: "#1f1f22"
  page-deep: "#18181a"
  surface-solid: "#2a2a2e"
  ink: "#ececef"
  muted: "#a2a2aa"
  success: "#5fd39a"
  warning: "#f1c470"
  danger: "#ff8f84"
typography:
  display:
    fontFamily: "Funnel Display Variable, Segoe UI, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  body:
    fontFamily: "Funnel Sans Variable, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "Funnel Sans Variable, Segoe UI, sans-serif"
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
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "36px"
components:
  button-primary:
    backgroundColor: "{colors.blue-deep}"
    textColor: "#ffffff"
    rounded: "{rounded.sm}"
    height: "42px"
  button-primary-hover:
    backgroundColor: "{colors.blue-bright}"
  glass-card:
    backgroundColor: "rgb(255 255 255 / 0.05)"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
---

# Design System: Clear Context

## Overview

**Creative North Star: "The Annotated Source"**

A reading desk for evidence, built from exactly three colors and one material: two blues taken from the logo, one gray, and glass. The gray (#1f1f22) is the page. Cards, the navigation rail and the sticky bar are glass: translucent, blurred, with a light top edge and a dark bottom edge, floating over a blurred copy of the logo so there is always something to refract. Blue marks every action, link and highlighted source passage.

Motion is reserved for real work in progress: each recorded investigation stage has a drawn glyph that moves only while that stage runs, and stays still under reduced motion.

**Key Characteristics:**
- Gray page, glass surfaces, two blues. No cream, no navy, no third accent.
- Glass is a material, not decoration: only where something sits behind it.
- Status colors (green, amber, red) exist only for verdicts and failures; blue never means "true".
- Headings in Funnel Display, text in Funnel Sans, data in JetBrains Mono.

## Colors

### The three
- **Deep Blue** (#0161dd): filled buttons, white text (5.5:1).
- **Bright Blue** (#047bf2): hover, glass tint, active navigation, quoted passages (at 32% opacity); links use a lightened mix of it for contrast on gray.
- **Gray** (#1f1f22): the page. Derived tones: rail #18181a at 70%, solid surface #2a2a2e, ink #ececef, muted #a2a2aa, lines at 10% white.

### Verdicts
Supported #5fd39a, unsettled #f1c470, contradicted #ff8f84, each as text on a 10-12% tint of itself.

**The Highlighter Rule.** The passage a finding rests on is marked with Bright Blue at 32%, never with a new color.

**The One Blue Rule.** Blue never means true.

## Typography

**Display:** Funnel Display for headings and the wordmark. **Text:** Funnel Sans, full Latin Extended for Turkish. **Data:** JetBrains Mono for timestamps, counts and claim numbers.

**The No Eyebrow Rule.** No small uppercase labels above headings; a number that orders claims sits beside the heading.

## Layout

A 244px rail and a fluid work area (intake max 1160px, report with a 280px aside). Below 900px the rail becomes a drawer. Spacing 4/8/16/24/36px.

## Elevation & Depth

Glass: `backdrop-filter: blur(18px) saturate(1.5)`, a 7% white to 3% white gradient fill, 1px inner top highlight, 1px inner bottom shadow, soft 30px drop shadow. Falls back to a solid #2a2a2e when transparency is reduced. The ambient backdrop is the six-piece logo, blurred, at 50% opacity.

## Shapes

10-14px radii on cards, 6px on buttons.

## Components

- **Rail:** the broken-C mark, the wordmark, a primary button, navigation, history with state words only for queued, running or failed.
- **Process timeline:** circle markers; check for recorded stages, X for a stop, the stage glyph for the running stage.
- **Evidence excerpt:** quoted text, matched passage in the blue highlight.

## Brand

Two logos, both generated with Muse Image 1.0 and finished by hand: the six-piece broken page (large uses) and the broken glass C (favicon, extension, rail). Rasters on purpose: the glass edges do not survive vectorizing. The Meta wordmark appears only as attribution, unaltered; it sits on a light chip because its lettering is dark. Jolly, the Muse mascot, appears once per investigation stage (progress page and step list) (illustrations generated with Muse Image 1.0, used with Meta's permission) and in place of the stage that failed.

## Do's and Don'ts

- Do derive progress from recorded backend events.
- Do keep glass to surfaces that have something behind them.
- Don't add pulsing dots, eyebrows, period-ended headings, italic accent words, gradient text, neon glow, or a fourth color.
- Don't animate anything that is not actual work in progress.

## Interaction rules

- Clipboard, file picker and drag/drop feed the same bounded media intake. Previews stay local and removable.
- An investigation starts only from the submit control. Examples fill the form; they do not submit it. Input survives request errors.
- Pending, running, complete, stopped and unavailable stay distinct. No invented percentages.
- One column on phones, drawer navigation, 16px inputs, keyboard focus, reduced motion and reduced transparency.

# Product

<!-- impeccable:product-schema 1 -->

Facts below come from the README, the code and the owner's written brief of November 1, 2026. Lines marked _(inferred)_ were not confirmed in an interview.

## Platform

web

## Users

- People who meet a claim, screenshot or video online and want to know what sources say before sharing it. They paste text or a link, attach media, or capture it from a page with the Chrome extension.
- The person who runs the server: one technical user who installs it, supplies their own API keys and decides when paid calls are allowed.
- Hackathon judges evaluating the product from the repository, the demo video and the landing page _(inferred from the hackathon deadline)_.

## Product Purpose

Clear Context separates a passage into checkable claims, researches each one and reports, detail by detail, whether recorded sources support it, contradict it, disagree, or leave it unsettled. For images and video it reads what the media shows, looks for earlier copies of the same picture and compares the caption with what is visible. Success is a report a reader can audit: every finding points to a quoted source passage.

## Positioning

It does not give a single true/false verdict. Each detail of a claim is assessed separately against literal source excerpts, and "unsettled" is an acceptable outcome. It is self-hosted with the user's own keys, without accounts or subscriptions.

## Operating Context

- Web app at `clearcontext.localhost`: input, history, progress built from recorded backend events, evidence report, settings.
- Chrome extension: capture text, a link, an image, a video frame or a page area; preview; start; brief status; open the web report.
- Models: Meta Muse Spark (claims, reading media, planning, judging) and Muse Voice Transcribe; research through Tavily, SerpApi (Google Lens, Bing) and Google Fact Check Tools.
- Landing page at `clearcontext.uslanozan.com.tr` (separate static site).

## Capabilities and Constraints

- Investigations start only on an explicit user action; paid calls are off until enabled in Settings.
- A queue runs at most two investigations at once by default.
- Videos up to 50 MB and 10 minutes are analyzed; larger ones are stored and reported as not analyzed.
- Not available: detection of AI-generated media, source-language detection, source publication dates beyond what search results show, a user list of trusted sources.

## Brand Commitments

- Name: Clear Context.
- Exactly three colors plus a material: two blues taken from the logo (#0161dd, #047bf2), the gray #1f1f22, and glass. Confirmed by the owner on November 1, 2026.
- Logos confirmed on November 1, 2026: the six-piece broken page (large uses) and the broken glass C (favicon, extension, rail). Font: Funnel Display with Funnel Sans.
- The official Meta wordmark and Muse Jolly image appear only as attribution, unaltered, without implying Meta ownership or endorsement. No derivative Jolly artwork or animation.
- No AI-slop patterns (impeccable.style/slop): no pulsing status dots, eyebrows above headings, periods ending headings, single italic words in headings, gradient text or decorative glow.

## Evidence on Hand

- Real recorded investigations in the local database (text, image and video cases).
- Official brand assets: `frontend/public/brand/meta.svg`, `frontend/public/brand/muse-logo.svg`. The official Jolly image is withheld until Meta answers the permission request sent on November 1, 2026.
- No demo video yet, no user testimonials, no usage numbers, no press. None of these may be invented.

## Product Principles

1. Evidence before verdicts: show the quoted passage, never a bare label.
2. Unsettled is an honest result; the interface must not make it look like failure.
3. Nothing paid happens without a visible user action.
4. Show only work that actually happened; progress comes from recorded events.

## Accessibility & Inclusion

Turkish and English content side by side, so fonts need full Latin Extended coverage. Keyboard focus, readable 16px input on phones, reduced-motion support and WCAG AA contrast.

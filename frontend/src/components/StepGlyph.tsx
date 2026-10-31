import type { ReactNode } from 'react';

// One drawn glyph per recorded investigation stage. The lines move only while that stage is
// running; with reduced motion they stay still and the stage title still says what happens.
const GLYPHS: Record<string, ReactNode> = {
  // The passage drops into the workspace.
  graph_started: (
    <>
      <path d="M10 30v8h28v-8" />
      <g className="glyph-drop">
        <path d="M24 8v19M17 20l7 7 7-7" />
      </g>
    </>
  ),
  // A frame with a line scanning down the picture.
  analyze_media: (
    <>
      <rect x="8" y="10" width="32" height="28" rx="3" />
      <path d="M13 33l7-8 5 5 4-4 6 7" />
      <path className="glyph-scan" d="M10 15h28" />
    </>
  ),
  // Lines of a linked page read one after another.
  fetch_links: (
    <>
      <rect className="glyph-reader" x="10" y="12" width="9" height="8" rx="2" />
      <path d="M12 16h24M12 25h24M12 34h16" />
    </>
  ),
  // One block of text separating into single statements.
  extract_claims: (
    <>
      <path className="glyph-split-up" d="M12 18h24" />
      <path d="M12 24h24" />
      <path className="glyph-split-down" d="M12 30h24" />
    </>
  ),
  // A route drawn between research questions.
  plan_queries: (
    <>
      <circle cx="12" cy="34" r="3" />
      <circle cx="24" cy="14" r="3" />
      <circle cx="36" cy="30" r="3" />
      <path className="glyph-draw" pathLength={1} d="M14 31L22 17M27 16l7 11" />
    </>
  ),
  // A lens moving over the results.
  retrieve_sources: (
    <>
      <path d="M8 40h32" />
      <g className="glyph-search">
        <circle cx="20" cy="20" r="8" />
        <path d="M26 26l7 7" />
      </g>
    </>
  ),
  // The relevant line in a source gets highlighted.
  select_passages: (
    <>
      <rect className="glyph-mark" x="10" y="20" width="28" height="8" rx="2" />
      <path d="M12 14h24M12 24h24M12 34h18" />
    </>
  ),
  // Each detail weighed against its evidence.
  assess_components: (
    <>
      <path d="M24 16v22M17 38h14" />
      <g className="glyph-tilt">
        <path d="M10 16h28" />
        <path d="M10 16l-4 9h8zM38 16l-4 9h8z" />
      </g>
    </>
  ),
  // The same lens, once more, for what stayed unsettled.
  followup_research: (
    <>
      <g className="glyph-search">
        <circle cx="20" cy="20" r="8" />
        <path d="M26 26l7 7" />
      </g>
      <path className="glyph-draw" pathLength={1} d="M33 9a10 10 0 0 1 5 9" />
    </>
  ),
  // A check drawn over the assessed evidence.
  evaluate_evidence: (
    <>
      <rect x="8" y="8" width="32" height="32" rx="4" />
      <path className="glyph-draw" pathLength={1} d="M15 25l6 6 12-13" />
    </>
  ),
  // The report written line by line.
  validate_report: (
    <>
      <path className="glyph-write glyph-write-1" pathLength={1} d="M12 14h24" />
      <path className="glyph-write glyph-write-2" pathLength={1} d="M12 24h24" />
      <path className="glyph-write glyph-write-3" pathLength={1} d="M12 34h14" />
    </>
  ),
  // The finished report filed away.
  report_saved: (
    <>
      <path d="M8 22v16h32V22" />
      <path d="M8 22l5-10h22l5 10H30a6 6 0 0 1-12 0z" />
      <g className="glyph-drop">
        <path d="M24 4v10" />
      </g>
    </>
  ),
};

interface Props {
  event: string;
  size?: number;
  animate?: boolean;
}

export function StepGlyph({ event, size = 48, animate = false }: Props) {
  return (
    <svg
      className={`step-glyph${animate ? ' is-animating' : ''}`}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {GLYPHS[event] ?? GLYPHS.graph_started}
    </svg>
  );
}

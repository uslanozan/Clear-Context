// Jolly, the Muse mascot, doing each recorded stage. Images are served from public/brand/jolly.
const EVENTS = new Set([
  'graph_started',
  'analyze_media',
  'fetch_links',
  'extract_claims',
  'plan_queries',
  'retrieve_sources',
  'select_passages',
  'assess_components',
  'followup_research',
  'evaluate_evidence',
  'validate_report',
  'report_saved',
]);

export function StepJolly({ event, size = 40 }: { event: string; size?: number }) {
  if (!EVENTS.has(event)) return null;
  return (
    <img
      className="step-jolly"
      src={`/brand/jolly/${event}.webp`}
      alt=""
      width={size}
      height={size}
      loading="lazy"
    />
  );
}

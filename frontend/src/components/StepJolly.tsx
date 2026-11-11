// Jolly, the Muse mascot, doing each recorded stage. Images are served from public/brand/jolly.
import { assetUrl } from '../lib/demo';
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
  // Shown in place of the stage that stopped.
  'failed',
]);

export function StepJolly({ event, size = 40 }: { event: string; size?: number }) {
  if (!EVENTS.has(event)) return null;
  return (
    <img
      className="step-jolly"
      src={assetUrl(`brand/jolly/${event}.webp`)}
      alt=""
      width={size}
      height={size}
      loading="lazy"
    />
  );
}

import { Check, Circle, LoaderCircle, X } from 'lucide-react';
import type { ResearchStep } from '../lib/types';

const BASE_STAGES = [
  {
    event: 'graph_started',
    title: 'Receive input',
    detail: 'Save the original passage in your workspace.',
  },
  {
    event: 'extract_claims',
    title: 'Separate claims',
    detail: 'Identify individual statements, keeping the original wording.',
  },
  {
    event: 'evaluate_evidence',
    title: 'Check evidence',
    detail: 'Assess the available evidence and identify unresolved details.',
  },
  {
    event: 'validate_report',
    title: 'Validate report',
    detail: 'Check claim references and the evidence structure.',
  },
  {
    event: 'report_saved',
    title: 'Save results',
    detail: 'Keep the report and model usage for later inspection.',
  },
];

const RESEARCH_STAGES = [
  { event: 'plan_queries', title: 'Plan searches', detail: 'Map research questions to claims.' },
  {
    event: 'retrieve_sources',
    title: 'Find sources',
    detail: 'Search and read sources within the available budget.',
  },
  {
    event: 'select_passages',
    title: 'Select passages',
    detail: 'Find relevant passages in the collected sources.',
  },
  {
    event: 'assess_components',
    title: 'Assess details',
    detail: 'Compare each detail with its source evidence.',
  },
];

const FOLLOWUP_STAGE = {
  event: 'followup_research',
  title: 'Search again',
  detail: 'Look once more for details the first sources left unsettled.',
};

export function ProcessTimeline({
  steps = [],
  isRunning = false,
  planned = false,
  hasError = false,
  researchEnabled = false,
}: {
  steps?: ResearchStep[];
  isRunning?: boolean;
  planned?: boolean;
  hasError?: boolean;
  researchEnabled?: boolean;
}) {
  const researchActive =
    researchEnabled ||
    steps.some((step) => RESEARCH_STAGES.some((stage) => stage.event === step.name));
  // The follow-up round is conditional, so it appears only after it was recorded.
  const researchStages = steps.some((step) => step.name === FOLLOWUP_STAGE.event)
    ? [...RESEARCH_STAGES, FOLLOWUP_STAGE]
    : RESEARCH_STAGES;
  const STAGES = researchActive
    ? [...BASE_STAGES.slice(0, 2), ...researchStages, ...BASE_STAGES.slice(2)]
    : BASE_STAGES;
  const failure = steps.find((step) => step.status === 'failed');
  const lastCompleted = STAGES.reduce(
    (last, stage, index) => (steps.some((step) => step.name === stage.event) ? index : last),
    -1,
  );
  const failedIndex = failure ? Math.min(lastCompleted + 1, STAGES.length - 1) : -1;
  return (
    <section
      className="process-timeline"
      aria-label={planned ? 'Investigation workflow' : 'Investigation activity'}
    >
      <h3>{planned ? 'The investigation' : 'Investigation steps'}</h3>
      {hasError && (
        <p role="status" className="muted">
          Activity could not be loaded. No steps are assumed complete.
        </p>
      )}
      <ol>
        {STAGES.map((stage, index) => {
          const event = steps.find((step) => step.name === stage.event);
          const failed = index === failedIndex;
          const active = isRunning && !failure && index === lastCompleted + 1;
          const state = event ? 'complete' : failed ? 'failed' : active ? 'active' : 'waiting';
          const label = planned
            ? 'Not started'
            : event
              ? 'Complete'
              : failed
                ? 'Stopped'
                : active
                  ? 'Running'
                  : 'Pending';
          return (
            <li
              key={stage.event}
              className={`process-step ${state}`}
              aria-current={active ? 'step' : undefined}
            >
              <span className="process-marker" aria-hidden="true">
                {event ? (
                  <Check size={14} />
                ) : failed ? (
                  <X size={14} />
                ) : active ? (
                  <LoaderCircle size={15} className="spin" />
                ) : (
                  <Circle size={11} />
                )}
              </span>
              <div className="process-copy">
                <div>
                  <strong>{stage.title}</strong>
                  <span className="process-state">{label}</span>
                </div>
                <p>{stage.detail}</p>
                {event && (
                  <time dateTime={event.created_at}>
                    {new Date(event.created_at).toLocaleTimeString('en-GB')}
                  </time>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      {failure && (
        <p className="step-failure" role="status">
          The investigation stopped at {new Date(failure.created_at).toLocaleTimeString('en-GB')}.
          Later steps did not run.
        </p>
      )}
      {planned && <p className="process-note">Image and video analysis are not connected yet.</p>}
    </section>
  );
}

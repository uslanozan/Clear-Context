import { Check, Circle, LoaderCircle, X } from 'lucide-react';
import type { ResearchStep } from '../lib/types';

const STAGES = [
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
    detail: 'Mark claims unresolved when no source evidence is available.',
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

export function ProcessTimeline({
  steps = [],
  isRunning = false,
  planned = false,
  hasError = false,
}: {
  steps?: ResearchStep[];
  isRunning?: boolean;
  planned?: boolean;
  hasError?: boolean;
}) {
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
      {planned && (
        <p className="process-note">Source search and visual analysis are not connected yet.</p>
      )}
    </section>
  );
}

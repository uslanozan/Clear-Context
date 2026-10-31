import { Check, Circle, X } from 'lucide-react';
import {
  BASE_STAGES,
  FOLLOWUP_STAGE,
  LINK_STAGE,
  MEDIA_STAGE,
  RESEARCH_STAGES,
} from '../lib/stages';
import type { ResearchStep } from '../lib/types';
import { StepGlyph } from './StepGlyph';

/** The stages this investigation shows, in order, given what was recorded so far. */
export function stageOrder(steps: ResearchStep[], researchEnabled = false) {
  const researchActive =
    researchEnabled ||
    steps.some((step) => RESEARCH_STAGES.some((stage) => stage.event === step.name));
  // The follow-up round is conditional, so it appears only after it was recorded.
  const researchStages = steps.some((step) => step.name === FOLLOWUP_STAGE.event)
    ? [...RESEARCH_STAGES, FOLLOWUP_STAGE]
    : RESEARCH_STAGES;
  // Link and media reading only run when links or files were given.
  const optional = [LINK_STAGE, MEDIA_STAGE].filter((stage) =>
    steps.some((step) => step.name === stage.event),
  );
  const baseStages = [BASE_STAGES[0], ...optional, ...BASE_STAGES.slice(1)];
  const extract = baseStages.findIndex((stage) => stage.event === 'extract_claims') + 1;
  return researchActive
    ? [...baseStages.slice(0, extract), ...researchStages, ...baseStages.slice(extract)]
    : baseStages;
}

/** The stage after the last recorded one: what a running investigation is doing now. */
export function runningStage(steps: ResearchStep[]) {
  const stages = stageOrder(steps);
  const lastCompleted = stages.reduce(
    (last, stage, index) => (steps.some((step) => step.name === stage.event) ? index : last),
    -1,
  );
  return stages[Math.min(lastCompleted + 1, stages.length - 1)];
}

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
  const STAGES = stageOrder(steps, researchEnabled);
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
                  <StepGlyph event={stage.event} size={17} animate />
                ) : (
                  <Circle size={11} />
                )}
              </span>
              <div className="process-copy">
                <div>
                  <strong>{stage.title}</strong>
                  {/* Only running and stopped stages need words; markers show the rest. */}
                  <span
                    className={active || failed ? 'process-state' : 'process-state visually-hidden'}
                  >
                    {label}
                  </span>
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
    </section>
  );
}

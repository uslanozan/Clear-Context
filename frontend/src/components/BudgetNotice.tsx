import { Button } from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { RESEARCH_MODES } from '../lib/modes';
import type { Investigation, Report } from '../lib/types';

type Action = 'rerun' | 'continue';

function BudgetActions({ investigation, deep }: { investigation: Investigation; deep: boolean }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const start = useMutation({
    mutationFn: (action: Action) =>
      action === 'rerun'
        ? api.rerun(investigation.id, 'deep')
        : api.continueResearch(investigation.id, 'deep'),
    retry: false,
    onSuccess: (created: Investigation) => {
      queryClient.setQueryData(['investigation', created.id], created);
      void queryClient.invalidateQueries({ queryKey: ['history'] });
      navigate(`/investigations/${created.id}`);
    },
  });
  return (
    <>
      <div className="budget-actions">
        {!deep && (
          <Button
            size="xs"
            variant="default"
            loading={start.isPending && start.variables === 'rerun'}
            disabled={start.isPending}
            onClick={() => start.mutate('rerun')}
          >
            Run again in Deep
          </Button>
        )}
        <Button
          size="xs"
          loading={start.isPending && start.variables === 'continue'}
          disabled={start.isPending}
          onClick={() => start.mutate('continue')}
        >
          Research remaining details
        </Button>
      </div>
      {start.isError && (
        <p className="budget-error" role="alert">
          The new run could not start. Try again.
        </p>
      )}
    </>
  );
}

/** Budget, opinion and continuation notes for a report; new runs start only on a click. */
export function BudgetNotice({
  investigation,
  report,
}: {
  investigation: Investigation;
  report: Report;
}) {
  const summary = report.research_summary;
  const limited = summary?.budget_limited ?? 0;
  const mode = investigation.research_mode ?? 'balanced';
  const modeLabel = RESEARCH_MODES.find((item) => item.value === mode)?.label ?? mode;
  const parent = investigation.parent_id;
  if (!parent && !limited && !summary?.not_checkable) return null;

  return (
    <>
      {parent && (
        <p className="report-origin" role="note">
          {investigation.relation === 'continue'
            ? 'This report continues an earlier one: details its budget did not reach were researched again, the rest were copied. Images and links are in the '
            : 'This is a new run of an earlier report in another mode. Compare it with the '}
          <Link to={`/investigations/${parent}`}>earlier report</Link>.
        </p>
      )}
      {limited > 0 && (
        <div className="budget-notice" role="status">
          <strong>
            {limited} {limited === 1 ? 'detail' : 'details'} did not fit the {modeLabel} research
            budget
          </strong>
          <p>
            {mode === 'deep'
              ? 'Research the remaining details as a continuation of this report. Settled details are copied; cached searches and pages are reused.'
              : 'Run the whole report again in Deep, or research only the remaining details. Both start new paid calls; cached searches and pages are reused.'}
          </p>
          <BudgetActions investigation={investigation} deep={mode === 'deep'} />
        </div>
      )}
      {!!summary?.not_checkable && (
        <p className="muted small" role="note">
          {summary.not_checkable} {summary.not_checkable === 1 ? 'detail is' : 'details are'} an
          opinion, value judgment or personal experience and{' '}
          {summary.not_checkable === 1 ? 'was' : 'were'} not researched.
        </p>
      )}
    </>
  );
}

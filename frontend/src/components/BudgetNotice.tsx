import { useState } from 'react';
import { Button, Modal } from '@mantine/core';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { completeEstimate, modeLabel } from '../lib/modes';
import type { Investigation, Report } from '../lib/types';
import { DEMO } from '../lib/demo';

type Action = 'rerun' | 'continue' | 'complete';

function BudgetActions({
  investigation,
  deep,
  remaining,
}: {
  investigation: Investigation;
  deep: boolean;
  remaining: number;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const estimate = completeEstimate(remaining);
  const start = useMutation({
    mutationFn: (action: Action) =>
      action === 'rerun'
        ? api.rerun(investigation.id, 'deep')
        : api.continueResearch(investigation.id, action === 'complete' ? 'complete' : 'deep'),
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
        <Button
          size="xs"
          variant="default"
          disabled={start.isPending}
          loading={start.isPending && start.variables === 'complete'}
          onClick={() => setConfirming(true)}
        >
          Research every remaining claim
        </Button>
      </div>
      <Modal
        opened={confirming}
        onClose={() => setConfirming(false)}
        title="Research every remaining claim?"
        centered
        closeButtonProps={{ 'aria-label': 'Cancel' }}
      >
        <div className="budget-confirm">
          <p>
            {estimate.researched} {estimate.researched === 1 ? 'claim' : 'claims'} will be
            researched with a budget that reaches each of them, in batches of eight. This uses up to
            about {estimate.searches} searches and {estimate.modelCalls} model calls and can take
            several minutes.
          </p>
          {estimate.left > 0 && (
            <p>
              {estimate.left} more {estimate.left === 1 ? 'claim stays' : 'claims stay'} for another
              run; one run researches at most 40.
            </p>
          )}
          <p className="muted small">
            Claims that state the same fact are researched once. Settled details are copied; cached
            searches and pages are reused.
          </p>
          <div className="settings-actions">
            <Button variant="default" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button
              loading={start.isPending}
              onClick={() => {
                setConfirming(false);
                start.mutate('complete');
              }}
            >
              Start research
            </Button>
          </div>
        </div>
      </Modal>
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
  const label = modeLabel(mode);
  const remaining = summary?.budget_limited_claim_ids?.length ?? 0;
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
            {limited} {limited === 1 ? 'detail' : 'details'} did not fit the {label} research budget
          </strong>
          <p>
            {mode === 'deep'
              ? 'Research the remaining details as a continuation of this report. Settled details are copied; cached searches and pages are reused.'
              : 'Run the whole report again in Deep, or research only the remaining details. Both start new paid calls; cached searches and pages are reused.'}
          </p>
          {!DEMO && (
            <BudgetActions
              investigation={investigation}
              deep={mode === 'deep' || mode === 'complete'}
              remaining={remaining}
            />
          )}
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

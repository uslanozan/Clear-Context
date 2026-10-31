import { Badge } from '@mantine/core';
import { COMPONENT_STATUS } from '../../src/lib/labels';
import type { ReportSummary } from './summary';

/** A short report summary; evidence and sources stay in the web report. */
export function SummaryView({ summary }: { summary: ReportSummary }) {
  return (
    <div className="ext-summary">
      {summary.media.map((item, index) => (
        <div key={index} className="ext-summary-media">
          <strong>{item.kind === 'video' ? 'Video' : 'Image'}</strong>
          <p>
            {item.earliest
              ? `Earliest page found with the same picture: ${item.earliest}.`
              : 'No dated page with the same picture was found.'}
          </p>
          {item.mismatches.map((detail) => (
            <p key={detail} className="ext-mismatch">
              Does not fit the {item.kind}: <span dir="auto">{detail}</span>
            </p>
          ))}
        </div>
      ))}
      {summary.claims.length ? (
        <p className="muted small">
          No overall verdict: each detail of a claim is assessed on its own.
        </p>
      ) : (
        <p>No claims to check were found: nothing here states a fact that sources could settle.</p>
      )}
      <ol className="ext-summary-claims">
        {summary.claims.map((claim, index) => (
          <li key={index}>
            <p dir="auto">{claim.text}</p>
            <div className="ext-badges">
              {claim.counts.length ? (
                claim.counts.map(([status, count]) => (
                  <Badge
                    key={status}
                    variant="light"
                    color={COMPONENT_STATUS[status].color}
                    tt="none"
                  >
                    {count} {COMPONENT_STATUS[status].label.toLowerCase()}
                  </Badge>
                ))
              ) : (
                <Badge variant="light" color="gray" tt="none">
                  Not researched
                </Badge>
              )}
            </div>
          </li>
        ))}
      </ol>
      {summary.hiddenClaims > 0 && (
        <p className="muted small">
          {summary.hiddenClaims} more {summary.hiddenClaims === 1 ? 'claim is' : 'claims are'} in
          the report.
        </p>
      )}
      {summary.budgetLimited > 0 && (
        <p className="muted small">
          {summary.budgetLimited} {summary.budgetLimited === 1 ? 'claim was' : 'claims were'} left
          by the research budget; the report can research them.
        </p>
      )}
      {summary.unreadableLinks > 0 && (
        <p className="muted small">
          {summary.unreadableLinks === 1 ? 'A link' : `${summary.unreadableLinks} links`} could not
          be read.
        </p>
      )}
    </div>
  );
}

import type { ReactNode } from 'react';
import { COMPONENT_STATUS } from '../lib/labels';
import type { Report, ResearchOverview } from '../lib/types';

// What each recorded stage did in this investigation, taken only from the saved report and
// the research workspace. A stage with nothing recorded gets no detail rather than a guess.

const NEED_STATUS: Record<string, string> = {
  planned: 'Researched',
  needs_context: 'Needs context',
  budget_deferred: 'Left for later (budget)',
  not_checkable: 'Not checkable',
};

function site(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function Facts({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="step-facts">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function SearchLabel({ query }: { query: ResearchOverview['queries'][number] }) {
  if (!query.query) return <span className="muted">Reverse image lookup</span>;
  return <code className="step-query">{query.query}</code>;
}

function List({ items, empty }: { items: ReactNode[]; empty: string }) {
  if (!items.length) return <p className="muted">{empty}</p>;
  return (
    <ul className="step-list">
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  );
}

export function stageDetails(
  report: Report,
  research: ResearchOverview | undefined,
): Partial<Record<string, ReactNode>> {
  const media = report.media ?? [];
  const links = report.links ?? [];
  const components = report.findings.flatMap((finding) => finding.components ?? []);
  const counts = components.reduce<Record<string, number>>((all, component) => {
    all[component.status] = (all[component.status] ?? 0) + 1;
    return all;
  }, {});
  const initial = research?.queries.filter((query) => query.origin !== 'followup') ?? [];
  const followup = research?.queries.filter((query) => query.origin === 'followup') ?? [];
  const summary = report.research_summary;
  const calls = report.model_usage.reduce<Record<string, number>>((all, usage) => {
    all[usage.task] = (all[usage.task] ?? 0) + 1;
    return all;
  }, {});
  const tokens = report.model_usage.reduce(
    (sum, usage) => sum + (usage.input_tokens ?? 0) + (usage.output_tokens ?? 0),
    0,
  );

  return {
    graph_started: (
      <Facts
        items={[
          [
            'Text',
            `${(report.analyzed_text ?? '').length.toLocaleString('en')} characters analyzed`,
          ],
          ['Files', media.length ? `${media.length} attached` : 'None'],
          ['Links', links.length ? `${links.length} in the text` : 'None'],
        ]}
      />
    ),
    analyze_media: (
      <List
        empty="No files were read."
        items={media.map((item) => (
          <>
            <strong>{item.filename}</strong> · {item.kind}, {item.analysis.status.replace('_', ' ')}
            {item.origin.matches.length > 0 && ` · found on ${item.origin.matches.length} pages`}
            {!!item.prior_checks?.reviews.length &&
              ` · ${item.prior_checks.reviews.length} published fact checks`}
            {!!item.analysis.speech?.length && ` · ${item.analysis.speech.length} speech turns`}
          </>
        ))}
      />
    ),
    fetch_links: (
      <List
        empty="No links were read."
        items={links.map((link) => (
          <>
            <strong>{link.site ?? site(link.url)}</strong> · {link.status.replace('_', ' ')}
            {link.reason && ` · ${link.reason}`}
          </>
        ))}
      />
    ),
    extract_claims: (
      <>
        <Facts
          items={[
            ['Claims', String(report.claims.length)],
            ...(report.extraction_coverage
              ? ([['Coverage', report.extraction_coverage.status]] as [string, string][])
              : []),
          ]}
        />
        <List
          empty="No checkable claims."
          items={report.claims.map((claim) => claim.statement || claim.text)}
        />
      </>
    ),
    plan_queries: research && (
      <>
        <Facts
          items={[
            ['Research needs', String(research.needs.length)],
            ['Searches planned', String(initial.length)],
          ]}
        />
        <List
          empty="No research needs were recorded."
          items={research.needs.map((need) => (
            <>
              {need.description}{' '}
              <span className="muted">· {NEED_STATUS[need.status] ?? need.status}</span>
            </>
          ))}
        />
        <List
          empty=""
          items={initial.map((query) => (
            <SearchLabel query={query} />
          ))}
        />
      </>
    ),
    retrieve_sources: (
      <>
        {research && (
          <Facts
            items={[
              ['Search results', String(research.results)],
              ['Different pages', String(research.sources_found)],
              ['Pages cited', String(report.sources.length)],
            ]}
          />
        )}
        <List
          empty="No sources were cited."
          items={report.sources.map((source) => (
            <>
              <strong>{site(source.url)}</strong>
              {source.source_type && (
                <span className="muted"> · {source.source_type.replace('_', ' ')}</span>
              )}
            </>
          ))}
        />
      </>
    ),
    select_passages: (
      <Facts
        items={[
          ...(research
            ? ([['Pages read for passages', String(research.selections)]] as [string, string][])
            : []),
          ['Quoted passages kept', String(report.evidence.length)],
          ...report.limitations
            .filter((text) => /passage/i.test(text))
            .map((text) => ['Note', text] as [string, string]),
        ]}
      />
    ),
    assess_components: (
      <Facts
        items={[
          ['Details judged', String(components.length)],
          ...Object.entries(counts).map(
            ([status, count]) =>
              [
                COMPONENT_STATUS[status as keyof typeof COMPONENT_STATUS]?.label ?? status,
                String(count),
              ] as [string, string],
          ),
        ]}
      />
    ),
    followup_research: (
      <List
        empty="No second-round searches were recorded."
        items={followup.map((query) => (
          <SearchLabel query={query} />
        ))}
      />
    ),
    evaluate_evidence: summary && (
      <Facts
        items={[
          ['Needs assessed', String(summary.assessed)],
          ['Left by the budget', String(summary.budget_limited)],
          ['Need more context', String(summary.needs_context)],
          ['Not checkable', String(summary.not_checkable)],
          ['Failed', String(summary.failed)],
        ]}
      />
    ),
    validate_report: (
      <Facts
        items={[
          ['Findings', String(report.findings.length)],
          [
            'Evidence links',
            String(report.findings.reduce((sum, f) => sum + f.evidence_ids.length, 0)),
          ],
          ['Limitations noted', String(report.limitations.length)],
        ]}
      />
    ),
    report_saved: (
      <Facts
        items={[
          ['Model calls', String(report.model_usage.length)],
          ...Object.entries(calls).map(
            ([task, count]) => [task.replace(/_/g, ' '), String(count)] as [string, string],
          ),
          ['Tokens', tokens.toLocaleString('en')],
        ]}
      />
    ),
  };
}

import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button } from '@mantine/core';
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Download,
  FileSearch,
  FileText,
  Link2,
  ShieldCheck,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { ProcessTimeline } from './ProcessTimeline';
import { stageDetails } from './StepDetails';
import { api } from '../lib/api';
import { ClaimSource } from './ClaimSource';
import { BudgetNotice } from './BudgetNotice';
import { LinkFindings } from './LinkFindings';
import { MediaFindings } from './MediaFindings';
import { EvidenceExcerpt, SourceTypeLabel, sourceDisplayName } from './EvidenceExcerpt';
import { ClaimVerdict, DetailTag } from './VerdictTag';
import { COMPONENT_STATUS, STATUS_ORDER } from '../lib/labels';
import { modeLabel } from '../lib/modes';
import type { Investigation, Report, ResearchStep } from '../lib/types';

/** Lists excerpts under one label per source, so repeated excerpts do not repeat the source. */
function EvidenceGroups({
  ids,
  evidence,
  sources,
  labelFor,
}: {
  ids: string[];
  evidence: Report['evidence'];
  sources: Report['sources'];
  labelFor: (id: string) => string;
}) {
  const groups: { key: string; label: string; items: Report['evidence'] }[] = [];
  for (const id of ids) {
    const item = evidence.find((entry) => entry.id === id);
    if (!item) continue;
    const label = labelFor(id);
    const key = `${label}|${item.source_id}`;
    const group = groups.find((entry) => entry.key === key);
    if (group) group.items.push(item);
    else groups.push({ key, label, items: [item] });
  }
  return (
    <>
      {groups.map((group) => (
        <div className="evidence-group" key={group.key}>
          <span className="evidence-group-label">{group.label}</span>
          {group.items.map((item, index) => (
            <EvidenceExcerpt
              key={item.id}
              evidence={item}
              source={sources.find((source) => source.id === item.source_id)}
              showSource={index === 0}
            />
          ))}
        </div>
      ))}
    </>
  );
}

/** Counts of detail results, settled outcomes first, e.g. "1 supported · 2 insufficient evidence". */
function detailSummary(components: NonNullable<Report['findings'][number]['components']>) {
  return STATUS_ORDER.map((status) => {
    const count = components.filter((component) => component.status === status).length;
    return count ? `${count} ${COMPONENT_STATUS[status].label.toLowerCase()}` : null;
  })
    .filter(Boolean)
    .join(' · ');
}

function normalizeText(text: string): string {
  return text.trim().replace(/\s+/g, ' ').toLowerCase();
}

export function Activity({
  steps,
  isRunning = false,
  hasError = false,
  details,
  onOpenChange,
}: {
  steps: ResearchStep[];
  isRunning?: boolean;
  hasError?: boolean;
  details?: Partial<Record<string, ReactNode>>;
  onOpenChange?: (event: string | null) => void;
}) {
  return (
    <ProcessTimeline
      steps={steps}
      isRunning={isRunning}
      hasError={hasError}
      details={details}
      onOpenChange={onOpenChange}
    />
  );
}

export function ReportView({
  investigation,
  report,
  steps,
}: {
  investigation: Investigation;
  report: Report;
  steps: ResearchStep[];
}) {
  // Searches and research needs live in the research workspace, not in the report.
  const research = useQuery({
    queryKey: ['research', investigation.id],
    queryFn: ({ signal }) => api.research(investigation.id, signal),
    staleTime: Infinity,
  });
  // An open stage widens the side column so its details are easier to read.
  const [stageOpen, setStageOpen] = useState(false);
  const evidenceMissing = report.sources.length === 0;
  // Only label the mode when source research actually ran for this report.
  const researchModeLabel = steps.some((step) => step.name === 'plan_queries')
    ? modeLabel(investigation.research_mode ?? 'balanced')
    : undefined;
  const usageGroups = [...new Set(report.model_usage.map((usage) => usage.model_id))].map(
    (modelId) => {
      const calls = report.model_usage.filter((usage) => usage.model_id === modelId);
      return {
        model_id: modelId,
        calls: calls.length,
        input_tokens: calls.every((usage) => usage.input_tokens !== null)
          ? calls.reduce((sum, usage) => sum + (usage.input_tokens ?? 0), 0)
          : null,
        output_tokens: calls.every((usage) => usage.output_tokens !== null)
          ? calls.reduce((sum, usage) => sum + (usage.output_tokens ?? 0), 0)
          : null,
      };
    },
  );

  const coverage = report.extraction_coverage;
  const ranges = coverage?.chunks.filter((chunk) => chunk.status !== 'split') ?? [];
  const processedRanges = ranges.filter((chunk) => chunk.status === 'processed').length;

  function exportJson() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }),
    );
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `clear-context-${report.investigation_id}.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // The browser's print dialog saves the PDF; a print stylesheet lays the report out on paper.
  function exportPdf() {
    const title = document.title;
    document.title = `clear-context-${report.investigation_id}`;
    window.addEventListener('afterprint', () => (document.title = title), { once: true });
    window.print();
  }

  return (
    <div className="report-page">
      <Link to="/" className="back-link">
        <ArrowLeft size={14} /> Back to workspace
      </Link>
      <div className="report-title-row">
        <div>
          <h1>Investigation report</h1>
          <p className="report-subtitle">
            {new Date(investigation.created_at).toLocaleDateString('en-GB', {
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            })}
            <span>·</span>
            {report.claims.length} {report.claims.length === 1 ? 'claim' : 'claims'} extracted
            {researchModeLabel && (
              <>
                <span>·</span>
                {researchModeLabel} research
              </>
            )}
            {report.mode === 'mock' && (
              <>
                <span>·</span>Development preview
              </>
            )}
          </p>
        </div>
      </div>
      {coverage && coverage.status === 'partial' && (
        <Alert color="orange" title="Claim extraction is partial" mb="md">
          Some parts need another extraction pass. This report may omit claims.
        </Alert>
      )}
      {evidenceMissing && (
        <div className="evidence-notice">
          <span className="notice-icon">
            <CircleHelp size={20} />
          </span>
          <div>
            <strong>
              {report.claims.length
                ? 'Claims extracted; evidence is still missing'
                : 'No claims to check were found'}
            </strong>
            <p>
              {report.claims.length
                ? 'These statements haven’t been verified. No source evidence is available in this report.'
                : coverage?.status === 'partial'
                  ? 'Part of the input was not processed, so a claim may have been missed.'
                  : 'Nothing in the input states a fact that sources could settle.'}
            </p>
          </div>
          {!!report.claims.length && <span className="notice-tag">NEEDS EVIDENCE</span>}
        </div>
      )}
      <div className={`report-grid${stageOpen ? ' stage-open' : ''}`}>
        <div className="report-main">
          <section className="input-section" aria-labelledby="input-heading">
            <div className="section-heading">
              <h2 id="input-heading">Your input</h2>
            </div>
            <div className="input-card">
              <p className="original-text" dir="auto">
                {investigation.text ||
                  'No text was entered. Claims come from text read from the images.'}
              </p>
            </div>
          </section>
          {!!report.links?.length && <LinkFindings links={report.links} />}
          {!!report.media?.length && <MediaFindings media={report.media} />}
          <div className="section-heading">
            <h2>Claim by claim</h2>
            <span>
              {report.claims.length} {report.claims.length === 1 ? 'claim' : 'claims'}
            </span>
          </div>
          <div className="claim-list">
            {report.claims.map((claim, index) => {
              const finding = report.findings.find((item) => item.claim_id === claim.id);
              const hasComponents = !!finding?.components?.length;
              const claimStatement = claim.statement || claim.text;
              // A single component that repeats the claim needs no second heading.
              const singleRedundantComponent =
                finding?.components?.length === 1 &&
                normalizeText(finding.components[0].description) === normalizeText(claimStatement);
              const evidence = report.evidence.filter((item) =>
                finding?.evidence_ids.includes(item.id),
              );
              return (
                <article className="claim-card" key={claim.id}>
                  <div className="claim-topline">
                    <span className="claim-number" aria-label={`Claim ${index + 1}`}>
                      {index + 1}
                    </span>
                    <h3 dir="auto">{claim.statement || claim.text}</h3>
                    {finding && (
                      <div className="claim-verdict">
                        <ClaimVerdict assessment={finding.assessment} perDetail={hasComponents} />
                        {hasComponents && (
                          <span className="claim-verdict-summary">
                            {detailSummary(finding.components ?? [])}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                  {claim.context_status === 'ambiguous' && (
                    <p className="claim-explanation">The source context is ambiguous.</p>
                  )}
                  <ClaimSource claim={claim} input={report.analyzed_text ?? investigation.text} />
                  <p className={hasComponents ? 'claim-verdict-note' : 'claim-explanation'}>
                    {finding?.explanation || 'A finding is not available for this claim.'}
                  </p>
                  {finding?.components?.length ? (
                    <div className="component-assessments">
                      <h4>{singleRedundantComponent ? 'Evidence' : 'Evidence by detail'}</h4>
                      {finding.components.map((component, componentIndex) => (
                        <section
                          className="detail-card"
                          key={`${component.description}-${componentIndex}`}
                        >
                          <header className="detail-head">
                            <DetailTag status={component.status} />
                            {!singleRedundantComponent && (
                              <strong className="detail-title" dir="auto">
                                {component.description}
                              </strong>
                            )}
                          </header>
                          <p className="detail-note" dir="auto">
                            {component.explanation}
                          </p>
                          <EvidenceGroups
                            ids={component.evidence_ids}
                            evidence={evidence}
                            sources={report.sources}
                            labelFor={(id) =>
                              component.evidence_relations?.[id] === 'contradicts'
                                ? 'Contradicting source'
                                : 'Supporting source'
                            }
                          />
                          <EvidenceGroups
                            ids={component.context_evidence_ids ?? []}
                            evidence={evidence}
                            sources={report.sources}
                            labelFor={() =>
                              'Reviewed for this research question; not cited for this detail'
                            }
                          />
                        </section>
                      ))}
                    </div>
                  ) : (
                    evidence.map((item) => (
                      <EvidenceExcerpt
                        key={item.id}
                        evidence={item}
                        source={report.sources.find((source) => source.id === item.source_id)}
                      />
                    ))
                  )}
                  <div className="claim-source-line">
                    <Link2 size={13} />
                    <span>
                      {evidence.length
                        ? `${evidence.length} linked evidence excerpt${evidence.length === 1 ? '' : 's'}`
                        : 'No evidence attached'}
                    </span>
                  </div>
                </article>
              );
            })}
          </div>
          <BudgetNotice investigation={investigation} report={report} />
          <div className="report-endnote">
            <ShieldCheck size={17} />
            <p>
              <strong>A useful distinction:</strong> no supporting evidence is not the same as
              evidence that a claim is false.
            </p>
          </div>
          <div className="report-actions">
            <Button
              variant="default"
              size="sm"
              leftSection={<FileText size={14} />}
              onClick={exportPdf}
            >
              Export PDF
            </Button>
            <Button
              variant="default"
              size="sm"
              leftSection={<Download size={14} />}
              onClick={exportJson}
            >
              Export JSON
            </Button>
            <span>PDF for reading and sharing · JSON with every recorded field</span>
          </div>
          <details className="technical-details">
            <summary>
              <ChevronRight size={15} aria-hidden="true" /> Technical details
            </summary>
            <dl className="technical-facts">
              <div>
                <dt>Report</dt>
                <dd>
                  {report.investigation_id} · revision {report.revision}
                </dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>
                  {report.mode === 'mock' ? 'Development preview' : 'Meta models'}
                  {researchModeLabel && ` · ${researchModeLabel} research`}
                </dd>
              </div>
              {coverage && (
                <div>
                  <dt>Claim extraction</dt>
                  <dd>
                    {processedRanges} of {ranges.length} input{' '}
                    {ranges.length === 1 ? 'range' : 'ranges'} processed in {coverage.model_calls}{' '}
                    model {coverage.model_calls === 1 ? 'call' : 'calls'}. Processing every range
                    does not guarantee that every claim was found.
                  </dd>
                </div>
              )}
            </dl>
            {!!report.limitations.length && (
              <>
                <h4>Scope and limitations</h4>
                <ul>
                  {report.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </>
            )}
          </details>
        </div>
        <aside className="report-aside" aria-label="Evidence and investigation details">
          <section className="side-panel evidence-panel">
            <div className="side-panel-heading">
              <h3>Source evidence</h3>
              <span>{report.sources.length}</span>
            </div>
            {!report.sources.length ? (
              <div className="evidence-empty">
                <FileSearch size={24} strokeWidth={1.5} aria-hidden="true" />
                <strong>No sources collected</strong>
                <p>Source links and excerpts will appear here when available.</p>
              </div>
            ) : (
              <ul className="source-list">
                {report.sources.map((source) => {
                  const safe = /^https?:\/\//i.test(source.url);
                  return (
                    <li key={source.id}>
                      {safe ? (
                        <a href={source.url} target="_blank" rel="noopener noreferrer">
                          {sourceDisplayName(source)}
                          <ArrowUpRight size={13} />
                        </a>
                      ) : (
                        <span>{sourceDisplayName(source)}</span>
                      )}
                      <SourceTypeLabel type={source.source_type} />
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
          <Activity
            steps={steps}
            details={stageDetails(report, research.data)}
            onOpenChange={(event) => setStageOpen(event !== null)}
          />
          <section className="side-panel usage-panel">
            <h3>Model usage</h3>
            {report.model_usage.length ? (
              usageGroups.map((usage, index) => (
                <div key={`${usage.model_id}-${index}`}>
                  <p className="model-name">
                    {usage.model_id
                      .replace('muse-spark-', 'Muse Spark ')
                      .replace('muse-wonder-', 'Muse Wonder ')}
                  </p>
                  <p className="muted">{usage.calls} recorded model calls</p>
                  <div className="token-pair">
                    <div>
                      <span>Input tokens</span>
                      <strong>
                        {usage.input_tokens?.toLocaleString('en-US') ?? 'Not reported'}
                      </strong>
                    </div>
                    <div>
                      <span>Output tokens</span>
                      <strong>
                        {usage.output_tokens?.toLocaleString('en-US') ?? 'Not reported'}
                      </strong>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted">No model calls in this preview.</p>
            )}
          </section>
          <div className="saved-note">
            <CheckCheck size={15} /> Saved to your workspace
          </div>
        </aside>
      </div>
    </div>
  );
}

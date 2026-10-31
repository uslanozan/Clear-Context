import { useState } from 'react';
import { Accordion, Alert, Badge, Button } from '@mantine/core';
import {
  ArrowLeft,
  ArrowUpRight,
  Check,
  CheckCheck,
  CircleHelp,
  Copy,
  Download,
  FileSearch,
  Link2,
  ShieldCheck,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { ProcessTimeline } from './ProcessTimeline';
import { ClaimSource } from './ClaimSource';
import { LinkFindings } from './LinkFindings';
import { MediaFindings } from './MediaFindings';
import { EvidenceExcerpt, SourceTypeLabel, sourceDisplayName } from './EvidenceExcerpt';
import { RESEARCH_MODES } from '../lib/modes';
import type { Assessment, Investigation, Report, ResearchStep } from '../lib/types';

const ASSESSMENTS: Record<Assessment, { label: string; color: string }> = {
  supported: { label: 'Supported', color: 'teal' },
  contradicted: { label: 'Contradicted', color: 'red' },
  mixed: { label: 'Mixed evidence', color: 'orange' },
  unresolved: { label: 'Unresolved', color: 'yellow' },
};

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
        <div key={group.key}>
          <span className="muted">{group.label}</span>
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

function normalizeText(text: string): string {
  return text.trim().replace(/\s+/g, ' ').toLowerCase();
}

export function Activity({
  steps,
  isRunning = false,
  hasError = false,
}: {
  steps: ResearchStep[];
  isRunning?: boolean;
  hasError?: boolean;
}) {
  return <ProcessTimeline steps={steps} isRunning={isRunning} hasError={hasError} />;
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
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const evidenceMissing = report.sources.length === 0;
  // Only label the mode when source research actually ran for this report.
  const researchModeLabel = steps.some((step) => step.name === 'plan_queries')
    ? RESEARCH_MODES.find((mode) => mode.value === (investigation.research_mode ?? 'balanced'))
        ?.label
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
  const coverageDetails = coverage && (
    <details className="claim-provenance">
      <summary>Review processing coverage</summary>
      <ul>
        {(coverage.notes ?? []).map((note, index) => (
          <li key={index}>{note}</li>
        ))}
      </ul>
      <p>{coverage.model_calls} model calls recorded</p>
      <ul>
        {coverage.chunks
          .filter((chunk) => chunk.status !== 'split')
          .map((chunk) => (
            <li key={`${chunk.start}-${chunk.end}`}>
              Characters {chunk.start + 1}–{chunk.end}:{' '}
              {chunk.status === 'processed' ? 'processed' : 'needs further extraction'}
            </li>
          ))}
      </ul>
    </details>
  );

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setCopyError(false);
      window.setTimeout(() => setCopied(false), 2500);
    } catch {
      setCopyError(true);
    }
  }

  function exportReport() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }),
    );
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `clear-context-${report.investigation_id}.json`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
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
        <Button
          variant="default"
          leftSection={copied ? <Check size={14} /> : <Copy size={14} />}
          onClick={() => void copyLink()}
        >
          {copied ? 'Link copied' : 'Copy link'}
        </Button>
      </div>
      {copyError && (
        <Alert color="orange" mb="md">
          The link couldn’t be copied. You can copy it from your address bar.
        </Alert>
      )}
      {coverage && coverage.status === 'partial' && (
        <Alert color="orange" title="Claim extraction is partial" mb="md">
          Some parts need another extraction pass. This report may omit claims.
          {coverageDetails}
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
                : 'No factual claims were extracted'}
            </strong>
            <p>
              {report.claims.length
                ? 'These statements haven’t been verified. No source evidence is available in this report.'
                : 'Check extraction coverage before treating an empty result as a passage without factual claims.'}
            </p>
          </div>
          <span className="notice-tag">NEEDS EVIDENCE</span>
        </div>
      )}
      <div className="report-grid">
        <div className="report-main">
          <Accordion className="original-passage" variant="separated" radius="md">
            <Accordion.Item value="original">
              <Accordion.Control icon={<FileSearch size={17} />}>
                Original passage<span className="original-label">Your starting point</span>
              </Accordion.Control>
              <Accordion.Panel>
                <p className="original-text">
                  {investigation.text ||
                    'No text was entered. Claims come from text read from the images.'}
                </p>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
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
              const assessment = finding ? ASSESSMENTS[finding.assessment] : null;
              // With per-detail results, an unresolved claim means "no overall verdict",
              // not "nothing was found".
              const assessmentLabel =
                hasComponents && finding?.assessment === 'unresolved'
                  ? 'No overall verdict'
                  : assessment?.label;
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
                    <span className="claim-number">CLAIM {String(index + 1).padStart(2, '0')}</span>
                    {assessment && (
                      <Badge
                        color={assessment.color}
                        variant="light"
                        leftSection={<CircleHelp size={11} />}
                        tt="none"
                        fw={550}
                      >
                        {assessmentLabel}
                      </Badge>
                    )}
                  </div>
                  <h3 dir="auto">{claim.statement || claim.text}</h3>
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
                        <section key={`${component.description}-${componentIndex}`}>
                          {!singleRedundantComponent && (
                            <>
                              <strong dir="auto">{component.description}</strong>{' '}
                            </>
                          )}
                          <Badge
                            variant="light"
                            color={
                              {
                                supported: 'teal',
                                contradicted: 'red',
                                conflicting: 'orange',
                                insufficient: 'yellow',
                                not_assessed: 'gray',
                              }[component.status]
                            }
                            tt="none"
                          >
                            {
                              {
                                supported: 'Supported',
                                contradicted: 'Contradicted',
                                conflicting: 'Sources disagree',
                                insufficient: 'Insufficient evidence',
                                not_assessed: 'Not assessed',
                              }[component.status]
                            }
                          </Badge>
                          <p dir="auto">{component.explanation}</p>
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
          {coverage && coverage.status !== 'partial' && (
            <div className="coverage-note">
              <p>Processing all input ranges does not guarantee that every claim was identified.</p>
              {coverageDetails}
            </div>
          )}
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
              leftSection={<Download size={14} />}
              onClick={exportReport}
            >
              Export report
            </Button>
            <span>JSON · Includes findings and available evidence</span>
          </div>
          <Accordion className="limitations" variant="default">
            <Accordion.Item value="limitations">
              <Accordion.Control>Scope & limitations</Accordion.Control>
              <Accordion.Panel>
                <ul>
                  {report.limitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
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
          <Activity steps={steps} />
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

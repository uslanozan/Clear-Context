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
import { EvidenceExcerpt } from './EvidenceExcerpt';
import type { Assessment, Investigation, Report, ResearchStep } from '../lib/types';

const ASSESSMENTS: Record<Assessment, { label: string; color: string }> = {
  supported: { label: 'Supported', color: 'teal' },
  contradicted: { label: 'Contradicted', color: 'red' },
  mixed: { label: 'Mixed evidence', color: 'orange' },
  unresolved: { label: 'Unresolved', color: 'yellow' },
};

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
      {report.extraction_coverage && (
        <Alert
          color={report.extraction_coverage.status === 'partial' ? 'orange' : 'gray'}
          title={
            report.extraction_coverage.status === 'partial'
              ? 'Claim extraction is partial'
              : 'Input ranges processed'
          }
          mb="md"
        >
          {report.extraction_coverage.status === 'partial'
            ? 'Some parts need another extraction pass. This report may omit claims.'
            : 'Processing all input ranges does not guarantee that every claim was identified.'}
          <details className="claim-provenance">
            <summary>Review processing coverage</summary>
            <ul>
              {(report.extraction_coverage.notes ?? []).map((note, index) => (
                <li key={index}>{note}</li>
              ))}
            </ul>
            <p>{report.extraction_coverage.model_calls} model calls recorded</p>
            <ul>
              {report.extraction_coverage.chunks
                .filter((chunk) => chunk.status !== 'split')
                .map((chunk) => (
                  <li key={`${chunk.start}-${chunk.end}`}>
                    Characters {chunk.start + 1}–{chunk.end}:{' '}
                    {chunk.status === 'processed' ? 'processed' : 'needs further extraction'}
                  </li>
                ))}
            </ul>
          </details>
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
                ? 'These statements haven’t been verified. Source research is not connected yet, so every finding remains unresolved.'
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
                <p className="original-text">{investigation.text}</p>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
          <div className="section-heading">
            <h2>Claim by claim</h2>
            <span>{String(report.claims.length).padStart(2, '0')} statements</span>
          </div>
          <div className="claim-list">
            {report.claims.map((claim, index) => {
              const finding = report.findings.find((item) => item.claim_id === claim.id);
              const assessment = finding ? ASSESSMENTS[finding.assessment] : null;
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
                        {assessment.label}
                      </Badge>
                    )}
                  </div>
                  <h3 dir="auto">{claim.statement || claim.text}</h3>
                  {claim.context_status === 'ambiguous' && (
                    <p className="claim-explanation">The source context is ambiguous.</p>
                  )}
                  <ClaimSource claim={claim} input={investigation.text} />
                  <p className="claim-explanation">
                    {finding?.explanation || 'A finding is not available for this claim.'}
                  </p>
                  {evidence.map((item) => (
                    <EvidenceExcerpt
                      key={item.id}
                      evidence={item}
                      source={report.sources.find((source) => source.id === item.source_id)}
                    />
                  ))}
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
                <p>
                  When source research is connected, you’ll inspect the links and excerpts here.
                </p>
              </div>
            ) : (
              <ul className="source-list">
                {report.sources.map((source) => {
                  const safe = /^https?:\/\//i.test(source.url);
                  return (
                    <li key={source.id}>
                      {safe ? (
                        <a href={source.url} target="_blank" rel="noopener noreferrer">
                          {source.title || source.url}
                          <ArrowUpRight size={13} />
                        </a>
                      ) : (
                        <span>{source.title}</span>
                      )}
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

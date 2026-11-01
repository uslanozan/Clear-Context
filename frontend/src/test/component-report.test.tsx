import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ReportView } from '../components/ReportView';
import type { Investigation, Report } from '../lib/types';

it('shows component status, directional source and highlighted source text', () => {
  const investigation: Investigation = {
    id: 'i1',
    text: 'A bridge opened in 2017.',
    status: 'completed',
    mode: 'meta',
    revision: 1,
    created_at: '2026-10-30T12:00:00Z',
    updated_at: '2026-10-30T12:00:01Z',
    error_code: null,
    model_usage: [],
  };
  const report: Report = {
    investigation_id: 'i1',
    mode: 'meta',
    revision: 1,
    claims: [{ id: 'c1', text: investigation.text }],
    sources: [
      {
        id: 's1',
        url: 'https://example.org/bridge',
        title: 'Bridge record',
        content: 'Record: opened in 2019.',
      },
    ],
    evidence: [{ id: 'e1', claim_id: 'c1', source_id: 's1', excerpt: 'opened in 2019' }],
    findings: [
      {
        id: 'f1',
        claim_id: 'c1',
        assessment: 'unresolved',
        explanation: 'Review each detail.',
        evidence_ids: ['e1'],
        components: [
          {
            description: 'Opened in 2017',
            status: 'contradicted',
            explanation: 'The source states 2019.',
            evidence_ids: ['e1'],
            evidence_relations: { e1: 'contradicts' },
            context_evidence_ids: [],
          },
        ],
      },
    ],
    limitations: [],
    model_usage: [],
  };
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { enabled: false } } })}
    >
      <MantineProvider>
        <MemoryRouter>
          <ReportView investigation={investigation} report={report} steps={[]} />
        </MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
  expect(screen.getByText('Evidence by detail')).toBeInTheDocument();
  expect(screen.getByText('Contradicting source')).toBeInTheDocument();
  expect(screen.getByText('opened in 2019').tagName).toBe('MARK');
  expect(screen.getAllByRole('link', { name: /Bridge record/ }).length).toBeGreaterThan(0);
  expect(screen.getByText('No overall verdict')).toBeInTheDocument();
  // The claim header summarizes the recorded detail results.
  expect(screen.getByText('1 contradicted')).toBeInTheDocument();
  expect(screen.getByText('1 claim')).toBeInTheDocument();
  expect(screen.getByText('Technical details')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Export JSON' })).toBeInTheDocument();
  // PDF export goes through the browser's print dialog and restores the page title afterwards.
  const print = vi.spyOn(window, 'print').mockImplementation(() => {});
  document.title = 'Clear Context';
  fireEvent.click(screen.getByRole('button', { name: 'Export PDF' }));
  expect(print).toHaveBeenCalledOnce();
  expect(document.title).toBe('clear-context-i1');
  window.dispatchEvent(new Event('afterprint'));
  expect(document.title).toBe('Clear Context');
  print.mockRestore();
});

it('names a source once for several excerpts and shows readable source names', () => {
  const investigation: Investigation = {
    id: 'i3',
    text: 'A bridge opened in 2019.',
    status: 'completed',
    mode: 'meta',
    revision: 1,
    created_at: '2026-10-30T12:00:00Z',
    updated_at: '2026-10-30T12:00:01Z',
    error_code: null,
    model_usage: [],
  };
  const report: Report = {
    investigation_id: 'i3',
    mode: 'meta',
    revision: 1,
    claims: [{ id: 'c1', text: investigation.text }],
    sources: [
      {
        id: 's1',
        url: 'https://www.example.org/bridge',
        title: 'https://www.example.org/bridge',
        content: 'The bridge opened in 2019. It carries two lanes.',
      },
    ],
    evidence: [
      { id: 'e1', claim_id: 'c1', source_id: 's1', excerpt: 'opened in 2019' },
      { id: 'e2', claim_id: 'c1', source_id: 's1', excerpt: 'carries two lanes' },
    ],
    findings: [
      {
        id: 'f1',
        claim_id: 'c1',
        assessment: 'unresolved',
        explanation: 'Review each detail.',
        evidence_ids: ['e1', 'e2'],
        components: [
          {
            description: 'Opened in 2019',
            status: 'supported',
            explanation: 'Stated by the source.',
            evidence_ids: ['e1', 'e2'],
            evidence_relations: { e1: 'supports', e2: 'supports' },
            context_evidence_ids: [],
          },
        ],
      },
    ],
    limitations: [],
    model_usage: [],
  };
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { enabled: false } } })}
    >
      <MantineProvider>
        <MemoryRouter>
          <ReportView investigation={investigation} report={report} steps={[]} />
        </MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
  expect(screen.getAllByText('Supporting source')).toHaveLength(1);
  expect(screen.getByText('opened in 2019').tagName).toBe('MARK');
  expect(screen.getByText('carries two lanes').tagName).toBe('MARK');
  // One link in the excerpt group and one in the sidebar list, both by domain.
  expect(screen.getAllByRole('link', { name: /^example\.org/ })).toHaveLength(2);
  expect(screen.queryByRole('link', { name: /https:\/\// })).not.toBeInTheDocument();
});

it('omits a component heading that repeats the only claim', () => {
  const investigation: Investigation = {
    id: 'i2',
    text: 'A bridge opened in 2019.',
    status: 'completed',
    mode: 'meta',
    revision: 1,
    created_at: '2026-10-30T12:00:00Z',
    updated_at: '2026-10-30T12:00:01Z',
    error_code: null,
    model_usage: [],
  };
  const report: Report = {
    investigation_id: 'i2',
    mode: 'meta',
    revision: 1,
    claims: [{ id: 'c1', text: investigation.text }],
    sources: [],
    evidence: [],
    findings: [
      {
        id: 'f1',
        claim_id: 'c1',
        assessment: 'unresolved',
        explanation: 'Review each detail.',
        evidence_ids: [],
        components: [
          {
            description: 'A bridge  opened in 2019.',
            status: 'insufficient',
            explanation: 'No source states the year.',
            evidence_ids: [],
            evidence_relations: {},
            context_evidence_ids: [],
          },
        ],
      },
    ],
    limitations: [],
    model_usage: [],
    extraction_coverage: { status: 'processed', model_calls: 1, chunks: [], notes: [] },
  };
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { enabled: false } } })}
    >
      <MantineProvider>
        <MemoryRouter>
          <ReportView investigation={investigation} report={report} steps={[]} />
        </MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
  expect(screen.getByRole('heading', { name: 'Evidence' })).toBeInTheDocument();
  expect(screen.queryByText('A bridge  opened in 2019.')).not.toBeInTheDocument();
  expect(screen.getByText('No source states the year.')).toBeInTheDocument();
  // Non-partial coverage is a quiet note, not an alert box.
  expect(screen.queryByText('Input ranges processed')).not.toBeInTheDocument();
  expect(screen.getByText(/does not guarantee that every claim/)).toBeInTheDocument();
});

it('separates unassessed details from insufficient evidence and labels need-level context', () => {
  const investigation: Investigation = {
    id: 'i4',
    text: 'A bridge opened in 2019 and the mayor opened it.',
    status: 'completed',
    mode: 'meta',
    revision: 1,
    created_at: '2026-10-30T12:00:00Z',
    updated_at: '2026-10-30T12:00:01Z',
    error_code: null,
    model_usage: [],
  };
  const report: Report = {
    investigation_id: 'i4',
    mode: 'meta',
    revision: 1,
    claims: [{ id: 'c1', text: investigation.text }],
    sources: [
      {
        id: 's1',
        url: 'https://example.org/bridge',
        title: 'Bridge record',
        content: 'The bridge opened in 2019.',
      },
    ],
    evidence: [{ id: 'e1', claim_id: 'c1', source_id: 's1', excerpt: 'opened in 2019' }],
    findings: [
      {
        id: 'f1',
        claim_id: 'c1',
        assessment: 'unresolved',
        explanation: 'Review each detail.',
        evidence_ids: ['e1'],
        components: [
          {
            description: 'The mayor opened it',
            status: 'insufficient',
            explanation: 'The source does not say who opened it.',
            evidence_ids: [],
            evidence_relations: {},
            context_evidence_ids: ['e1'],
          },
          {
            description: 'Visitor numbers in the opening year',
            status: 'not_assessed',
            explanation:
              'Evidence assessment did not complete (failed); this detail was not evaluated.',
            evidence_ids: [],
            evidence_relations: {},
            context_evidence_ids: [],
          },
        ],
      },
    ],
    limitations: [],
    model_usage: [],
  };
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { enabled: false } } })}
    >
      <MantineProvider>
        <MemoryRouter>
          <ReportView investigation={investigation} report={report} steps={[]} />
        </MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
  expect(screen.getByText('Insufficient evidence')).toBeInTheDocument();
  expect(screen.getByText('Not assessed')).toBeInTheDocument();
  expect(
    screen.getByText('Reviewed for this research question; not cited for this detail'),
  ).toBeInTheDocument();
  expect(screen.queryByText(/evidence is insufficient/)).not.toBeInTheDocument();
});

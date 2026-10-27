import { MantineProvider } from '@mantine/core';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { ClaimSource } from '../components/ClaimSource';
import { ReportView } from '../components/ReportView';
import type { Investigation, Report } from '../lib/types';
import { theme } from '../theme';

describe('Claim provenance', () => {
  it('highlights source using Unicode code points instead of UTF-16 indexes', () => {
    const input = '😀 Marie Curie. She won in 1911.';
    render(
      <ClaimSource
        input={input}
        claim={{
          id: 'claim',
          text: 'She won in 1911.',
          statement: 'Marie Curie won in 1911.',
          source_span: { start: 15, end: 31, text: 'She won in 1911.' },
          context_spans: [{ start: 2, end: 14, text: 'Marie Curie.' }],
        }}
      />,
    );
    fireEvent.click(screen.getByText('Inspect source passage'));
    expect(screen.getByText('She won in 1911.').tagName).toBe('MARK');
    expect(screen.getByText('Marie Curie.')).toBeInTheDocument();
  });

  it('does not highlight a saved location that mismatches the input', () => {
    render(
      <ClaimSource
        input="Original"
        claim={{
          id: 'claim',
          text: 'Changed',
          source_span: { start: 0, end: 7, text: 'Changed' },
        }}
      />,
    );
    expect(screen.getByText('The saved source location could not be matched.')).toBeInTheDocument();
    expect(screen.queryByText('Inspect source passage')).not.toBeInTheDocument();
  });

  it('shows partial extraction separately from factual uncertainty', () => {
    const investigation: Investigation = {
      id: 'local',
      text: 'A fact.',
      status: 'completed',
      mode: 'meta',
      revision: 1,
      created_at: '2026-10-27T12:00:00Z',
      updated_at: '2026-10-27T12:00:01Z',
      error_code: null,
      model_usage: [],
    };
    const report: Report = {
      investigation_id: 'local',
      mode: 'meta',
      revision: 1,
      claims: [{ id: 'claim', text: 'A fact.', statement: 'A statement to investigate.' }],
      sources: [],
      evidence: [],
      findings: [
        {
          id: 'finding',
          claim_id: 'claim',
          assessment: 'unresolved',
          explanation: 'No evidence collected.',
          evidence_ids: [],
        },
      ],
      limitations: [],
      model_usage: [],
      extraction_coverage: {
        status: 'partial',
        model_calls: 1,
        notes: [],
        chunks: [{ start: 0, end: 7, status: 'partial', reason: 'response_capacity' }],
      },
    };
    render(
      <MantineProvider theme={theme}>
        <MemoryRouter>
          <ReportView investigation={investigation} report={report} steps={[]} />
        </MemoryRouter>
      </MantineProvider>,
    );
    expect(screen.getByText('Claim extraction is partial')).toBeInTheDocument();
    expect(screen.getByText('Unresolved')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'A statement to investigate.' }),
    ).toBeInTheDocument();
  });
});

import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { BudgetNotice } from '../components/BudgetNotice';
import type { Investigation, Report } from '../lib/types';

const investigation = {
  id: 'parent',
  text: 'Article',
  status: 'completed',
  mode: 'meta',
  research_mode: 'balanced',
  revision: 1,
  created_at: '2026-10-31T00:00:00Z',
  updated_at: '2026-10-31T00:00:00Z',
  error_code: null,
  model_usage: [],
} as Investigation;

const report = {
  investigation_id: 'parent',
  claims: [],
  sources: [],
  evidence: [],
  findings: [],
  limitations: [],
  model_usage: [],
  research_summary: {
    planned: 6,
    assessed: 6,
    budget_limited: 9,
    needs_context: 1,
    not_checkable: 2,
    failed: 0,
    budget_limited_claim_ids: ['c1'],
  },
} as unknown as Report;

function renderNotice(props: { investigation: Investigation; report: Report }) {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MantineProvider>
        <MemoryRouter>
          <BudgetNotice {...props} />
        </MemoryRouter>
      </MantineProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

it('offers Deep and a continuation only on a click, and notes skipped opinions', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({ ...investigation, id: 'child', relation: 'continue' }), {
      status: 202,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  renderNotice({ investigation, report });
  expect(
    screen.getByText('9 details did not fit the Balanced research budget'),
  ).toBeInTheDocument();
  expect(screen.getByText(/2 details are an opinion/)).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Research remaining details' }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  const [url, init] = fetchMock.mock.calls[0];
  expect(String(url)).toContain('/investigations/parent/continue');
  expect(JSON.parse(String((init as RequestInit).body))).toEqual({ research_mode: 'deep' });
});

it('offers only a continuation in Deep and links a continuation to its parent', () => {
  renderNotice({
    investigation: {
      ...investigation,
      research_mode: 'deep',
      parent_id: 'p0',
      relation: 'continue',
    },
    report,
  });
  expect(screen.queryByRole('button', { name: 'Run again in Deep' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Research remaining details' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'earlier report' })).toHaveAttribute(
    'href',
    '/investigations/p0',
  );
});

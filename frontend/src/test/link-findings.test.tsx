import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { LinkFindings } from '../components/LinkFindings';
import type { LinkFinding } from '../lib/types';

const read: LinkFinding = {
  url: 'https://news.example/a',
  status: 'read',
  title: 'Bakanlık izin verdi',
  site: 'news.example',
  published_on: '2024-04-18',
  text_chars: 1200,
  truncated: true,
  media_ids: ['m1'],
  reason: null,
};

it('shows read, unreadable and unopened links with an honest date note', () => {
  render(
    <MantineProvider>
      <LinkFindings
        links={[
          read,
          {
            ...read,
            url: 'https://x.com/u/status/1',
            status: 'failed',
            title: null,
            site: 'x.com',
            published_on: null,
            media_ids: [],
            reason: 'This link could not be read. Paste the post’s text or attach a screenshot.',
          },
          {
            ...read,
            url: 'javascript:alert(1)',
            status: 'not_read',
            title: 'bad',
            published_on: null,
            truncated: false,
          },
        ]}
      />
    </MantineProvider>,
  );
  expect(screen.getByRole('link', { name: /Bakanlık izin verdi/ })).toHaveAttribute(
    'href',
    'https://news.example/a',
  );
  expect(screen.getByText(/reported by a search index/)).toBeInTheDocument();
  expect(screen.getByText(/first part only/)).toBeInTheDocument();
  expect(screen.getByText(/not used as evidence for its own claims/)).toBeInTheDocument();
  expect(screen.getByText('Could not be read')).toBeInTheDocument();
  expect(screen.getByText(/attach a screenshot/)).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /bad/ })).not.toBeInTheDocument();
});

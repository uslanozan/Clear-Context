import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { MediaFindings } from '../components/MediaFindings';
import type { MediaFinding } from '../lib/types';

const base: MediaFinding = {
  id: 'm1',
  kind: 'image',
  mime_type: 'image/png',
  filename: 'post.png',
  analysis: {
    status: 'analyzed',
    content_type: 'post_screenshot',
    visible_text: 'BREAKING: protests in France',
    observations: ['A crowd holds flags.'],
    context_cues: ['Shop signs are written in Hungarian.'],
    note: null,
  },
  origin: {
    status: 'matches_found',
    provider: 'serpapi_lens',
    reason: null,
    matches: [
      {
        page_url: 'https://news.example/2019/budapest',
        page_title: '<b>Budapest</b> protest',
        image_url: null,
        match: 'full',
      },
      { page_url: 'javascript:alert(1)', page_title: 'bad', image_url: null, match: 'partial' },
    ],
    best_guess_labels: ['budapest protest'],
  },
};

function renderMedia(media: MediaFinding[]) {
  render(
    <MantineProvider>
      <MediaFindings media={media} />
    </MantineProvider>,
  );
}

it('separates read text, observations and cues, and labels matches as leads', () => {
  renderMedia([base]);
  expect(screen.getByAltText('Uploaded image 1: post.png')).toHaveAttribute('src', '/api/media/m1');
  expect(screen.getByText('BREAKING: protests in France')).toBeInTheDocument();
  expect(screen.getByText(/Model transcription/)).toBeInTheDocument();
  expect(screen.getByText('Shop signs are written in Hungarian.')).toBeInTheDocument();
  expect(screen.getByText(/not conclusions/)).toBeInTheDocument();
  const link = screen.getByRole('link', { name: /Budapest protest/ });
  expect(link).toHaveAttribute('href', 'https://news.example/2019/budapest');
  expect(screen.queryByRole('link', { name: /bad/ })).not.toBeInTheDocument();
  expect(
    screen.getByText(/does not prove where or when it was first published/),
  ).toBeInTheDocument();
});

it('states an unchecked origin and an unanalyzed file plainly', () => {
  renderMedia([
    {
      ...base,
      analysis: {
        ...base.analysis,
        status: 'not_analyzed',
        visible_text: '',
        observations: [],
        context_cues: [],
        note: 'Preview mode: images are not sent to a model.',
      },
      origin: {
        status: 'not_checked',
        provider: null,
        reason: 'No reverse image search provider is configured.',
        matches: [],
        best_guess_labels: [],
      },
    },
  ]);
  expect(screen.getByText('Not analyzed')).toBeInTheDocument();
  expect(screen.getByText(/Preview mode: images are not sent/)).toBeInTheDocument();
  expect(screen.getByText(/original source and date remain unresolved/)).toBeInTheDocument();
  expect(screen.queryByText('Text read from the image')).not.toBeInTheDocument();
});

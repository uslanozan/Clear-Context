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

it('shows caption checks as a model assessment and the earliest dated same-image page', () => {
  renderMedia([
    {
      ...base,
      analysis: {
        ...base.analysis,
        visible_text: 'JE-779\n1996',
        claim_text: [],
        caption_checks: [
          {
            caption_detail: 'A conductor from Konya',
            assessment: 'inconsistent',
            visible_basis: ['Signs on the train use Chinese characters.'],
          },
        ],
      },
      origin: {
        status: 'matches_found',
        provider: 'serpapi_lens',
        reason: null,
        matches: [
          {
            page_url: 'https://forum.example/same-driver',
            page_title: 'Same driver, 26 years apart',
            image_url: null,
            match: 'full',
            source: 'Forum',
            date_text: 'Feb 12, 2025',
            published_on: '2025-02-12',
          },
          {
            page_url: 'https://check.example/train',
            page_title: 'Fact check: trains',
            image_url: null,
            match: 'full',
            source: 'Check',
            date_text: 'Feb 24, 2025',
            published_on: '2025-02-24',
          },
          {
            page_url: 'https://other.example/train',
            page_title: 'A similar train',
            image_url: null,
            match: 'similar',
          },
        ],
        best_guess_labels: [],
      },
    },
  ]);
  expect(screen.getByText('Caption compared with the image')).toBeInTheDocument();
  expect(screen.getByText(/It is not evidence/)).toBeInTheDocument();
  expect(screen.getByText('Does not fit the image')).toBeInTheDocument();
  expect(screen.getByText('Signs on the train use Chinese characters.')).toBeInTheDocument();
  expect(screen.getByText(/No statements to check/)).toBeInTheDocument();
  expect(screen.getByText(/Earliest dated page found/)).toHaveTextContent(
    'Earliest dated page found: Forum, Feb 12, 2025',
  );
  expect(screen.getByText('Same image (2)')).toBeInTheDocument();
  expect(screen.getByText('Similar images')).toBeInTheDocument();
  expect(screen.getByText('Check · Feb 24, 2025')).toBeInTheDocument();
});

it('lists published fact checks with the publisher rating labeled as theirs', () => {
  renderMedia([
    {
      ...base,
      prior_checks: {
        status: 'found',
        provider: 'google_fact_check',
        reason: null,
        reviews: [
          {
            url: 'https://www.dogrulukpayi.com/a',
            title: 'Fotoğraf Konya’yı mı gösteriyor?',
            publisher: 'Doğruluk Payı',
            site: 'dogrulukpayi.com',
            rating: 'Yanlış',
            review_date: '2025-02-24',
            claim_text: null,
          },
        ],
      },
    },
  ]);
  expect(screen.getByText('Published fact checks of this image')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Konya’yı mı gösteriyor/ })).toHaveAttribute(
    'href',
    'https://www.dogrulukpayi.com/a',
  );
  expect(screen.getByText('Yanlış')).toBeInTheDocument();
  expect(screen.getByText(/not adopted as a verdict/)).toBeInTheDocument();
});

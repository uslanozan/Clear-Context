import { render, screen } from '@testing-library/react';
import { EvidenceExcerpt } from '../components/EvidenceExcerpt';

const evidence = { id: 'e1', claim_id: 'c1', source_id: 's1', excerpt: 'opened in 2019' };
const source = {
  id: 's1',
  title: 'Opening record',
  url: 'https://example.org/bridge',
  content: 'The bridge opened in 2019 after construction.',
};

it('highlights an exact unique excerpt and links the source', () => {
  render(<EvidenceExcerpt evidence={evidence} source={source} />);
  expect(screen.getByText('opened in 2019').tagName).toBe('MARK');
  expect(screen.getByRole('link', { name: /Opening record/ })).toHaveAttribute('href', source.url);
});

it('drops page chrome and partial words around the excerpt and marks cut context', () => {
  const content = `| 29 | 30 | 31 | By: Site Editors Tower opens ${'x'.repeat(10)} the quoted claim sentence. ${'filler '.repeat(40)}end`;
  const { container } = render(
    <EvidenceExcerpt
      evidence={{ ...evidence, excerpt: 'the quoted claim sentence.' }}
      source={{ ...source, content }}
    />,
  );
  const quote = container.querySelector('blockquote')!;
  expect(quote.textContent).not.toMatch(/\|/);
  expect(quote.textContent).toMatch(/^… By: Site Editors/);
  expect(quote.textContent).toMatch(/ …$/);
  expect(screen.getByText('the quoted claim sentence.').tagName).toBe('MARK');
});

it('shows the domain when the stored title is only a URL', () => {
  render(
    <EvidenceExcerpt
      evidence={evidence}
      source={{ ...source, title: 'https://www.example.org/bridge' }}
    />,
  );
  expect(screen.getByRole('link', { name: /^example\.org/ })).toHaveAttribute('href', source.url);
});

it('does not highlight an ambiguous match or link an unsafe URL', () => {
  render(
    <EvidenceExcerpt
      evidence={evidence}
      source={{ ...source, content: 'opened in 2019; opened in 2019', url: 'javascript:alert(1)' }}
    />,
  );
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('Source context could not be located uniquely.')).toBeInTheDocument();
});

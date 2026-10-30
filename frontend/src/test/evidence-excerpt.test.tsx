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

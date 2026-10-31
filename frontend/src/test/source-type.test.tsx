import { render, screen } from '@testing-library/react';
import { SourceTypeLabel } from '../components/EvidenceExcerpt';

it('labels social and fact-check sources and leaves ordinary pages unlabeled', () => {
  const { rerender, container } = render(<SourceTypeLabel type="social" />);
  expect(screen.getByText('Social post or forum')).toBeInTheDocument();
  rerender(<SourceTypeLabel type="fact_check" />);
  expect(screen.getByText('Fact check')).toBeInTheDocument();
  rerender(<SourceTypeLabel type="web" />);
  expect(container).toBeEmptyDOMElement();
  rerender(<SourceTypeLabel type={null} />);
  expect(container).toBeEmptyDOMElement();
});

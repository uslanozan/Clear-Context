import { render, screen } from '@testing-library/react';
import { HelpGuide } from '../components/HelpGuide';

it('explains every detail result and the claim-wide tag', () => {
  render(<HelpGuide />);
  for (const label of [
    'Supported',
    'Contradicted',
    'Sources disagree',
    'Insufficient evidence',
    'Not assessed',
    'No overall verdict',
  ]) {
    expect(screen.getByText(label)).toBeInTheDocument();
  }
  expect(screen.getByText(/not the same as false/)).toBeInTheDocument();
});

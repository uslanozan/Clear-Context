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
    'All details supported',
    'Mixed results',
    'Not settled',
  ]) {
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  }
  expect(screen.getByText(/not the same as false/)).toBeInTheDocument();
});

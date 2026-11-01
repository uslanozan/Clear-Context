import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ProcessTimeline } from '../components/ProcessTimeline';

const started = {
  name: 'graph_started',
  status: 'running' as const,
  created_at: '2026-10-27T09:00:00Z',
};

describe('Recorded investigation steps', () => {
  it('never presents the planned workflow as completed work', () => {
    render(<ProcessTimeline planned />);
    expect(screen.getAllByText('Not started')).toHaveLength(5);
    expect(screen.queryByText('Complete')).not.toBeInTheDocument();
  });
  it('shows only the next stage as running after a recorded event', () => {
    render(<ProcessTimeline steps={[started]} isRunning />);
    const stages = screen.getAllByRole('listitem');
    expect(within(stages[0]).getByText('Complete')).toBeInTheDocument();
    expect(within(stages[1]).getByText('Running')).toBeInTheDocument();
    expect(screen.getAllByText('Pending')).toHaveLength(3);
  });
  it('shows a stop and leaves later stages pending', () => {
    render(
      <ProcessTimeline
        steps={[
          started,
          { name: 'investigation_failed', status: 'failed', created_at: started.created_at },
        ]}
      />,
    );
    expect(screen.getByText('Stopped')).toBeInTheDocument();
    expect(screen.queryByText('Running')).not.toBeInTheDocument();
    expect(screen.getAllByText('Pending')).toHaveLength(3);
  });
  it('lists the follow-up search only when it was recorded', () => {
    const step = (name: string) => ({
      name,
      status: 'completed' as const,
      created_at: started.created_at,
    });
    const research = ['plan_queries', 'retrieve_sources', 'select_passages', 'assess_components'];
    const { rerender } = render(<ProcessTimeline steps={research.map(step)} />);
    expect(screen.queryByText('Search again')).not.toBeInTheDocument();
    rerender(<ProcessTimeline steps={[...research, 'followup_research'].map(step)} />);
    const followup = screen.getByText('Search again').closest('li')!;
    expect(within(followup).getByText('Complete')).toBeInTheDocument();
  });
  it('shows image reading only for investigations with attached files', () => {
    const step = (name: string) => ({
      name,
      status: 'completed' as const,
      created_at: started.created_at,
    });
    render(
      <ProcessTimeline steps={['graph_started', 'analyze_media', 'extract_claims'].map(step)} />,
    );
    const stages = screen.getAllByRole('listitem');
    expect(within(stages[1]).getByText('Read images and video')).toBeInTheDocument();
    expect(within(stages[2]).getByText('Separate claims')).toBeInTheDocument();
  });
  it('distinguishes unavailable activity from completed work', () => {
    render(<ProcessTimeline hasError />);
    expect(screen.getByRole('status')).toHaveTextContent('Activity could not be loaded');
    expect(screen.queryByText('Complete')).not.toBeInTheDocument();
  });
  it('opens the recorded details of a stage on demand', () => {
    render(
      <ProcessTimeline
        steps={[started]}
        details={{
          graph_started: <p>120 characters analyzed</p>,
          extract_claims: <p>never shown</p>,
        }}
      />,
    );
    expect(screen.queryByText('120 characters analyzed')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Receive input/ }));
    expect(screen.getByText('120 characters analyzed')).toBeInTheDocument();
    // A stage without a record offers no details, even if some exist.
    expect(screen.queryByRole('button', { name: /Separate claims/ })).not.toBeInTheDocument();
  });
});

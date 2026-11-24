import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import PausedBanner from './PausedBanner';

const PAUSE = { engine: 'gemini', label: 'Gemini', reason: 'Gemini daily free quota used up', pausedAt: 'T' };

describe('PausedBanner', () => {
  it('says which engine is paused and why', () => {
    render(<PausedBanner paused={[PAUSE]} busy={false} onResume={vi.fn()} />);
    expect(screen.getByRole('status')).toHaveTextContent('Gemini paused: Gemini daily free quota used up');
  });

  it('Resume carries on with the queue', async () => {
    const onResume = vi.fn();
    render(<PausedBanner paused={[PAUSE]} busy={false} onResume={onResume} />);
    await userEvent.click(screen.getByRole('button', { name: 'Resume' }));
    expect(onResume).toHaveBeenCalled();
  });

  it('shows nothing when no engine is paused', () => {
    const { container } = render(<PausedBanner paused={[]} busy={false} onResume={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });
});

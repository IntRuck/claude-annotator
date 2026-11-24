import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ActivityLog from './ActivityLog';

const ENTRIES = [
  { id: 3, level: 'error', message: 'b.jpg: ERROR Gemini HTTP 500', jobId: 2, imageId: 7, createdAt: '2026-11-24T08:05:09Z' },
  { id: 2, level: 'info', message: 'a.jpg: 3 box(es) in 2.1s (via gemini)', jobId: 1, imageId: 6, createdAt: '2026-11-24T08:05:01Z' },
  { id: 1, level: 'info', message: 'Queued 2 image(s) for Gemini (gemini-x)', jobId: null, imageId: null, createdAt: '2026-11-24T08:05:00Z' },
];

describe('ActivityLog', () => {
  it('lists entries newest first with their time', () => {
    render(<ActivityLog entries={ENTRIES} onSelectImage={vi.fn()} />);
    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining('b.jpg: ERROR Gemini HTTP 500'),
      expect.stringContaining('a.jpg: 3 box(es)'),
      expect.stringContaining('Queued 2 image(s)'),
    ]);
    expect(items[0]).toHaveTextContent(/\d\d:\d\d:\d\d/);
    expect(items[0]).toHaveClass('error');
  });

  it('a line about an image opens that image', async () => {
    const onSelectImage = vi.fn();
    render(<ActivityLog entries={ENTRIES} onSelectImage={onSelectImage} />);
    await userEvent.click(screen.getByRole('button', { name: /a\.jpg: 3 box/ }));
    expect(onSelectImage).toHaveBeenCalledWith(6);
  });

  it('says so when nothing happened yet', () => {
    render(<ActivityLog entries={[]} onSelectImage={vi.fn()} />);
    expect(screen.getByText('Nothing yet.')).toBeInTheDocument();
  });
});

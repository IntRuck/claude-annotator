import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ReviewPanel from './ReviewPanel';

const image = (extra = {}) => ({ id: 1, status: 'auto', flagged: false, flagReason: '', flagNote: '', ...extra });

function renderPanel(props = {}) {
  const handlers = { onApprove: vi.fn(), onFlag: vi.fn() };
  render(<ReviewPanel image={image()} dirty={false} {...handlers} {...props} />);
  return handlers;
}

describe('ReviewPanel (Approve / Flag, like today)', () => {
  it('approves', async () => {
    const h = renderPanel();
    await userEvent.click(screen.getByRole('button', { name: '✓ Approve (R)' }));
    expect(h.onApprove).toHaveBeenCalled();
  });

  it('shows when the image is already approved', () => {
    renderPanel({ image: image({ status: 'reviewed' }) });
    expect(screen.getByRole('button', { name: '✓ Approved (R = next)' })).toBeInTheDocument();
  });

  it('flags, then shows the reason and note fields that save on their own', async () => {
    const h = renderPanel();
    await userEvent.click(screen.getByRole('button', { name: '🚩 Flag for later (G)' }));
    expect(h.onFlag).toHaveBeenCalledWith(true, '', '');
  });

  it('a flagged image offers reasons and a note, and unflagging', async () => {
    const h = renderPanel({ image: image({ flagged: true, flagReason: 'unsure', flagNote: '' }) });
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Flag reason' }), 'wrong class');
    expect(h.onFlag).toHaveBeenLastCalledWith(true, 'wrong class', '');
    await userEvent.type(screen.getByRole('textbox', { name: 'Flag note' }), 'left can{Enter}');
    expect(h.onFlag).toHaveBeenLastCalledWith(true, 'unsure', 'left can');
    await userEvent.click(screen.getByRole('button', { name: '🚩 Flagged (G to unflag)' }));
    expect(h.onFlag).toHaveBeenLastCalledWith(false, '', '');
  });

  it('reminds you about unsaved changes', () => {
    renderPanel({ dirty: true });
    expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();
  });
});

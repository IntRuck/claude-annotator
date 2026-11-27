import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import BoxPanel from './BoxPanel';

const classes = [{ index: 0, name: 'can' }, { index: 1, name: 'jar' }];
const boxes = [{ cls: 0, x1: 0, y1: 0, x2: 0.5, y2: 0.5 }, { cls: 7, x1: 0.5, y1: 0.5, x2: 1, y2: 1 }];

function renderPanel(extra = {}) {
  const handlers = { onSelect: vi.fn(), onChangeClass: vi.fn(), onDelete: vi.fn(), onToggleHidden: vi.fn() };
  render(<BoxPanel boxes={boxes} classes={classes} selected={0} hidden={new Set([1])} {...handlers} {...extra} />);
  return handlers;
}

describe('BoxPanel (the Boxes tab)', () => {
  it('lists each box with its class, and marks one whose class ID is not in the list', () => {
    renderPanel();
    const rows = screen.getAllByRole('listitem');
    expect(within(rows[0]).getByRole('combobox')).toHaveValue('0');
    expect(within(rows[1]).getByRole('option', { name: 'ID 7 (unknown)' })).toBeInTheDocument();
    expect(rows[0]).toHaveClass('selected');
  });

  it('changes a box class, hides/shows and deletes', async () => {
    const h = renderPanel();
    const rows = screen.getAllByRole('listitem');
    await userEvent.selectOptions(within(rows[0]).getByRole('combobox'), '1');
    expect(h.onChangeClass).toHaveBeenCalledWith(0, 1);
    await userEvent.click(within(rows[1]).getByRole('button', { name: 'Show box' }));
    expect(h.onToggleHidden).toHaveBeenCalledWith(1);
    await userEvent.click(within(rows[0]).getByRole('button', { name: 'Delete box' }));
    expect(h.onDelete).toHaveBeenCalledWith(0);
  });

  it('says how to add boxes when there are none', () => {
    renderPanel({ boxes: [], selected: -1, hidden: new Set() });
    expect(screen.getByText(/Drag on the image to draw one/)).toBeInTheDocument();
  });

  it('an outlined box shows the outline mark and Remove outline; a plain box shows neither', async () => {
    const onRemoveOutline = vi.fn();
    const outlined = { ...boxes[0], points: [[0, 0], [0.5, 0], [0.25, 0.5]] };
    renderPanel({ boxes: [outlined, boxes[1]], onRemoveOutline });
    const rows = screen.getAllByRole('listitem');
    expect(within(rows[0]).getByTitle('Has an outline')).toBeInTheDocument();
    await userEvent.click(within(rows[0]).getByRole('button', { name: 'Remove outline' }));
    expect(onRemoveOutline).toHaveBeenCalledWith(0);
    expect(within(rows[1]).queryByTitle('Has an outline')).not.toBeInTheDocument();
    expect(within(rows[1]).queryByRole('button', { name: 'Remove outline' })).not.toBeInTheDocument();
  });
});

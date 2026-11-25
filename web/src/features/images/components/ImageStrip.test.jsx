import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ImageStrip from './ImageStrip';

const image = (id, fileName, extra = {}) => ({
  id, fileName, status: 'unlabeled', boxCount: 0, flagged: false, flagReason: '', flagNote: '', note: '', ...extra,
});
const items = [
  image(1, 'a.jpg', { status: 'auto', boxCount: 3 }),
  image(2, 'b.jpg', { status: 'reviewed', flagged: true, flagReason: 'wrong class' }),
  image(3, 'c.jpg', { status: 'error', note: 'gemini: timeout' }),
];
const counts = { all: 3, unlabeled: 0, auto: 1, edited: 0, reviewed: 1, flagged: 1, error: 1 };

function renderStrip(props = {}) {
  const handlers = { onSelect: vi.fn(), onFilterChange: vi.fn() };
  render(<ImageStrip items={items} counts={counts} filter="all" currentId={2} {...handlers} {...props} />);
  return handlers;
}

describe('ImageStrip', () => {
  it('shows a thumbnail per image, loaded lazily through the API', () => {
    renderStrip();
    const thumb = screen.getByRole('button', { name: /a\.jpg/ });
    const img = thumb.querySelector('img');
    expect(img).toHaveAttribute('src', '/api/images/1/thumb');
    expect(img).toHaveAttribute('loading', 'lazy');
  });

  it('shows the status colour, box count and flag on each thumbnail', () => {
    renderStrip();
    const a = screen.getByRole('button', { name: /a\.jpg/ });
    expect(a.querySelector('.dot')).toHaveClass('s-auto');
    expect(within(a).getByText('3')).toBeInTheDocument();
    const b = screen.getByRole('button', { name: /b\.jpg/ });
    expect(within(b).getByText('🚩')).toBeInTheDocument();
    expect(b).toHaveAttribute('title', expect.stringContaining('wrong class'));
    expect(screen.getByRole('button', { name: /c\.jpg/ })).toHaveAttribute('title', expect.stringContaining('gemini: timeout'));
  });

  it('marks the current image and selects another on click', async () => {
    const { onSelect } = renderStrip();
    expect(screen.getByRole('button', { name: /b\.jpg/ })).toHaveAttribute('aria-current', 'true');
    await userEvent.click(screen.getByRole('button', { name: /c\.jpg/ }));
    expect(onSelect).toHaveBeenCalledWith(3);
  });

  it('shows the position in the filtered list and steps with the arrows', async () => {
    const { onSelect } = renderStrip();
    expect(screen.getByText('2', { selector: '.pos' })).toBeInTheDocument();
    expect(screen.getByText('/ 3', { exact: false })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next image' }));
    expect(onSelect).toHaveBeenLastCalledWith(3);
    await userEvent.click(screen.getByRole('button', { name: 'Previous image' }));
    expect(onSelect).toHaveBeenLastCalledWith(1);
  });

  it('offers every filter with its count', async () => {
    const { onFilterChange } = renderStrip();
    const select = screen.getByRole('combobox', { name: 'Filter images' });
    expect(within(select).getByRole('option', { name: '🚩 Flagged (1)' })).toBeInTheDocument();
    expect(within(select).getByRole('option', { name: 'Labeled by AI (not checked) (1)' })).toBeInTheDocument();
    await userEvent.selectOptions(select, 'flagged');
    expect(onFilterChange).toHaveBeenCalledWith('flagged');
  });

  it('says why the list is empty', () => {
    const { unmount } = render(<ImageStrip items={[]} counts={{ ...counts, all: 0 }} filter="all" currentId={null} onSelect={() => {}} onFilterChange={() => {}} />);
    expect(screen.getByText(/No images yet/)).toBeInTheDocument();
    unmount();
    render(<ImageStrip items={[]} counts={counts} filter="edited" currentId={null} onSelect={() => {}} onFilterChange={() => {}} />);
    expect(screen.getByText('No images match this filter.')).toBeInTheDocument();
  });

  it('offers a picked set of images (from the health check) as its own filter', async () => {
    const { onFilterChange } = renderStrip({ custom: { label: 'Tiny boxes', count: 2 } });
    const select = screen.getByRole('combobox', { name: 'Filter images' });
    expect(within(select).getByRole('option', { name: 'Tiny boxes (2)' })).toHaveValue('custom');
    await userEvent.selectOptions(select, 'custom');
    expect(onFilterChange).toHaveBeenCalledWith('custom');
  });

  it('has no picked-set filter until one is picked', () => {
    renderStrip();
    expect(screen.queryByRole('option', { name: /\(2\)/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(7);
  });
});

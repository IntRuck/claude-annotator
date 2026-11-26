import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import ClassList from './ClassList';

const classes = Array.from({ length: 10 }, (_, i) => ({ index: i, name: `sku_${i}`, detectorPrompt: '', description: '' }));

describe('ClassList', () => {
  it('shows the 1-9 shortcut key only for the first nine classes', () => {
    render(<ClassList classes={classes} currentIndex={0} onPick={() => {}} onOpenSkus={() => {}} />);
    expect(screen.getByRole('button', { name: /sku_0/ })).toHaveTextContent('1');
    expect(screen.getByRole('button', { name: /sku_8/ })).toHaveTextContent('9');
    expect(screen.getByRole('button', { name: /sku_9/ }).querySelector('.key')).toBeEmptyDOMElement();
  });

  it('marks the current class and picks one on click', async () => {
    const onPick = vi.fn();
    render(<ClassList classes={classes.slice(0, 3)} currentIndex={1} onPick={onPick} onOpenSkus={() => {}} />);
    expect(screen.getByRole('button', { name: /sku_1/ })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(screen.getByRole('button', { name: /sku_2/ }));
    expect(onPick).toHaveBeenCalledWith(2);
  });

  it('shows box counts for this image when given', () => {
    render(<ClassList classes={classes.slice(0, 2)} currentIndex={0} counts={{ 1: 4 }} onPick={() => {}} onOpenSkus={() => {}} />);
    expect(screen.getByRole('button', { name: /sku_1/ })).toHaveTextContent('4');
  });

  it('has an Edit SKUs button under the list', async () => {
    const onOpenSkus = vi.fn();
    render(<ClassList classes={classes.slice(0, 2)} currentIndex={0} onPick={() => {}} onOpenSkus={onOpenSkus} />);
    await userEvent.click(screen.getByRole('button', { name: 'Edit SKUs' }));
    expect(onOpenSkus).toHaveBeenCalledOnce();
  });

  it('offers to add SKUs when there are none', async () => {
    const onOpenSkus = vi.fn();
    render(<ClassList classes={[]} currentIndex={0} onPick={() => {}} onOpenSkus={onOpenSkus} />);
    await userEvent.click(screen.getByRole('button', { name: 'Add SKUs' }));
    expect(onOpenSkus).toHaveBeenCalled();
  });
});

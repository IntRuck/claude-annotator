import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Menu } from './index';

function setup(extra = {}) {
  const onImport = vi.fn();
  const onDelete = vi.fn();
  render(
    <div>
      <p>Outside</p>
      <Menu label="More" items={[
        { label: 'Import dataset', onSelect: onImport },
        { label: 'Delete…', onSelect: onDelete, danger: true },
      ]} {...extra}>⋯</Menu>
    </div>,
  );
  return { onImport, onDelete, trigger: screen.getByRole('button', { name: 'More' }) };
}

describe('Menu', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('is closed until its button is clicked, then focuses the first item', async () => {
    const { trigger } = setup();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    await userEvent.click(trigger);

    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('menuitem', { name: 'Import dataset' })).toHaveFocus();
  });

  it('runs the chosen item and closes', async () => {
    const { trigger, onDelete } = setup();
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole('menuitem', { name: 'Delete…' }));
    expect(onDelete).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('Escape closes it and puts focus back on the button', async () => {
    const { trigger } = setup();
    await userEvent.click(trigger);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('a click outside closes it', async () => {
    const { trigger } = setup();
    await userEvent.click(trigger);
    await userEvent.click(screen.getByText('Outside'));
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('arrow keys move between items and wrap around', async () => {
    const { trigger } = setup();
    await userEvent.click(trigger);
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Delete…' })).toHaveFocus();
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Import dataset' })).toHaveFocus();
    await userEvent.keyboard('{ArrowUp}');
    expect(screen.getByRole('menuitem', { name: 'Delete…' })).toHaveFocus();
  });

  it('keys pressed in the menu do not reach page-wide shortcuts', async () => {
    const onWindowKey = vi.fn();
    window.addEventListener('keydown', onWindowKey);
    const { trigger } = setup();
    await userEvent.click(trigger);
    await userEvent.keyboard('r{ArrowDown}');
    window.removeEventListener('keydown', onWindowKey);
    expect(onWindowKey).not.toHaveBeenCalled();
  });

  it('marks dangerous items', async () => {
    const { trigger } = setup();
    await userEvent.click(trigger);
    expect(screen.getByRole('menuitem', { name: 'Delete…' })).toHaveClass('danger');
  });

  describe('tickable items', () => {
    function setupTicks() {
      const onDark = vi.fn();
      render(
        <Menu label="More" items={[
          { label: 'Import dataset', onSelect: vi.fn() },
          { separator: true },
          { label: 'Light theme', onSelect: vi.fn(), checked: false },
          { label: 'Dark theme', onSelect: onDark, checked: true },
        ]}>⋯</Menu>,
      );
      return { onDark, trigger: screen.getByRole('button', { name: 'More' }) };
    }

    it('say which one is ticked', async () => {
      const { trigger } = setupTicks();
      await userEvent.click(trigger);
      expect(screen.getByRole('menuitemradio', { name: 'Dark theme' })).toHaveAttribute('aria-checked', 'true');
      expect(screen.getByRole('menuitemradio', { name: 'Light theme' })).toHaveAttribute('aria-checked', 'false');
    });

    it('are reached with the arrow keys like the others, and run when chosen', async () => {
      const { trigger, onDark } = setupTicks();
      await userEvent.click(trigger);
      await userEvent.keyboard('{ArrowDown}');
      expect(screen.getByRole('menuitemradio', { name: 'Light theme' })).toHaveFocus();
      await userEvent.keyboard('{ArrowDown}{Enter}');
      expect(onDark).toHaveBeenCalledOnce();
    });
  });

  it('shows the button content and a tooltip', () => {
    setup({ title: 'Project tools' });
    expect(screen.getByRole('button', { name: 'More' })).toHaveTextContent('⋯');
    expect(screen.getByRole('button', { name: 'More' })).toHaveAttribute('title', 'Project tools');
  });
});

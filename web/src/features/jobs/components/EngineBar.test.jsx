import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import EngineBar from './EngineBar';

const SETTINGS = { engine: 'gemini', model: 'gemini-3.5-flash-lite', extra: '' };
const IDLE = { queued: 0, running: [] };

function renderBar(props = {}) {
  const handlers = { onChange: vi.fn(), onRunAll: vi.fn(), onRefineAll: vi.fn(), onStop: vi.fn() };
  render(<EngineBar settings={SETTINGS} summary={IDLE} notice="" busy={false} {...handlers} {...props} />);
  return handlers;
}

describe('EngineBar', () => {
  it('shows the engine, its model and extra instructions', () => {
    renderBar();
    expect(screen.getByRole('combobox', { name: 'AI engine' })).toHaveValue('gemini');
    expect(screen.getByRole('combobox', { name: 'Gemini model' })).toHaveValue('gemini-3.5-flash-lite');
    expect(screen.getByRole('textbox', { name: 'Extra instructions for the AI' })).toHaveValue('');
  });

  it('reports option changes', async () => {
    const { onChange } = renderBar();
    await userEvent.type(screen.getByRole('textbox', { name: 'Extra instructions for the AI' }), 'x');
    expect(onChange).toHaveBeenLastCalledWith({ extra: 'x' });
  });

  it('Label all unlabeled runs the batch', async () => {
    const { onRunAll } = renderBar();
    await userEvent.click(screen.getByRole('button', { name: 'Label all unlabeled' }));
    expect(onRunAll).toHaveBeenCalled();
  });

  it('Refine all asks the AI to review its own unapproved labels', async () => {
    const { onRefineAll } = renderBar();
    await userEvent.click(screen.getByRole('button', { name: 'Refine all' }));
    expect(onRefineAll).toHaveBeenCalled();
  });

  it('Stop is only on while images are waiting', async () => {
    renderBar();
    expect(screen.getByRole('button', { name: /Stop/ })).toBeDisabled();
  });

  it('Stop cancels the waiting images', async () => {
    const { onStop } = renderBar({ summary: { queued: 3, running: [{ id: 1, fileName: 'b.jpg' }] } });
    await userEvent.click(screen.getByRole('button', { name: /Stop/ }));
    expect(onStop).toHaveBeenCalled();
  });

  it('says what the AI is doing', () => {
    renderBar({ summary: { queued: 3, running: [{ id: 1, fileName: 'b.jpg' }] } });
    expect(screen.getByText('Labeling b.jpg… · 3 waiting')).toBeInTheDocument();
  });

  it('shows a notice instead when a button found nothing to do', () => {
    renderBar({ notice: 'Nothing to label' });
    expect(screen.getByText('Nothing to label')).toBeInTheDocument();
  });

  it('can not start another batch while one is being queued', () => {
    renderBar({ busy: true });
    expect(screen.getByRole('button', { name: 'Label all unlabeled' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Refine all' })).toBeDisabled();
  });
});

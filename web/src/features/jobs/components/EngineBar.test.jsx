import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
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

  describe('what the worker reported', () => {
    const status = (gemini, lastSeenAt = new Date().toISOString()) => ({
      workerOnline: true, lastSeenAt, paused: [],
      engines: { gemini: { label: 'Gemini', ready: true, note: '', models: [], supportsRefine: true, ...gemini } },
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('suggests the models the key can use', () => {
      renderBar({ engineStatus: status({ models: ['gemini-4-pro', 'gemini-4-flash'] }) });
      const options = [...document.querySelectorAll('#gemini-models option')].map((o) => o.value);
      expect(options).toEqual(['gemini-4-pro', 'gemini-4-flash']);
    });

    it('falls back to the usual models before the worker reported any', () => {
      renderBar();
      expect(document.querySelectorAll('#gemini-models option')).toHaveLength(2);
    });

    it('warns when the chosen engine can not run, with the reason', () => {
      renderBar({ engineStatus: status({ ready: false, note: 'No Gemini API key. Put GEMINI_API_KEY=...' }) });
      expect(screen.getByText(/No Gemini API key/)).toHaveClass('engine-note', 'bad');
    });

    it('says when the worker is not running', () => {
      renderBar({ engineStatus: status({}, null) });
      expect(screen.getByText('Worker offline')).toBeInTheDocument();
    });

    it('notices the worker going quiet without asking the server again', () => {
      vi.useFakeTimers();
      vi.setSystemTime(Date.parse('2026-11-24T10:00:00Z'));
      renderBar({ engineStatus: status({}, '2026-11-24T09:59:30Z') });
      expect(screen.queryByText('Worker offline')).not.toBeInTheDocument();

      act(() => vi.advanceTimersByTime(20000));

      expect(screen.getByText('Worker offline')).toBeInTheDocument();
    });
  });

  it('can not start another batch while one is being queued', () => {
    renderBar({ busy: true });
    expect(screen.getByRole('button', { name: 'Label all unlabeled' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Refine all' })).toBeDisabled();
  });
});

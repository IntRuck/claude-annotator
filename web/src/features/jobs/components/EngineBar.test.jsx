import { act, fireEvent, render, screen } from '@testing-library/react';
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

  describe('options per engine, like today', () => {
    const CLAUDE = { engine: 'claude', model: 'sonnet', extra: '', grid: false };
    const OLLAMA = { engine: 'ollama', model: 'qwen3-vl:4b', extra: '', grid: false };
    const DINO = { engine: 'grounding_dino', model: 'IDEA-Research/grounding-dino-tiny', extra: '', threshold: 0.35 };

    it('offers all five engines', () => {
      renderBar();
      const engines = screen.getByRole('combobox', { name: 'AI engine' });
      expect([...engines.options].map((o) => o.textContent)).toEqual([
        'Gemini (API key)', 'Claude (your plan)', 'Local VLM (Ollama)', 'Grounding DINO', 'YOLO-World / YOLOE']);
    });

    it('changing the engine asks for that engine', async () => {
      const { onChange } = renderBar();
      await userEvent.selectOptions(screen.getByRole('combobox', { name: 'AI engine' }), 'ollama');
      expect(onChange).toHaveBeenLastCalledWith({ engine: 'ollama' });
    });

    it('Claude picks one of its three models from a list', async () => {
      const { onChange } = renderBar({ settings: CLAUDE });
      const model = screen.getByRole('combobox', { name: 'Claude model' });
      expect([...model.options].map((o) => o.textContent)).toEqual(['Sonnet', 'Haiku', 'Opus']);
      await userEvent.selectOptions(model, 'opus');
      expect(onChange).toHaveBeenLastCalledWith({ model: 'opus' });
    });

    it('Claude and Ollama can draw a grid on the image the AI sees', async () => {
      const { onChange } = renderBar({ settings: OLLAMA });
      await userEvent.click(screen.getByRole('checkbox', { name: /grid/ }));
      expect(onChange).toHaveBeenLastCalledWith({ grid: true });
    });

    it('Gemini has no grid switch', () => {
      renderBar();
      expect(screen.queryByRole('checkbox', { name: /grid/ })).not.toBeInTheDocument();
    });

    it('Ollama suggests the models pulled into it', () => {
      renderBar({
        settings: OLLAMA,
        engineStatus: { workerOnline: true, lastSeenAt: new Date().toISOString(), paused: [],
                        engines: { ollama: { ready: true, note: '', models: ['gemma3:4b', 'qwen3-vl:8b'] } } },
      });
      expect(screen.getByRole('combobox', { name: 'Ollama model' })).toHaveValue('qwen3-vl:4b');
      const options = [...document.querySelectorAll('#ollama-models option')].map((o) => o.value);
      expect(options).toEqual(['gemma3:4b', 'qwen3-vl:8b']);
    });

    it('a detector takes a minimum confidence instead of extra instructions', () => {
      const { onChange } = renderBar({ settings: DINO });
      const conf = screen.getByRole('spinbutton', { name: 'Minimum confidence' });
      expect(conf).toHaveValue(0.35);
      expect(screen.queryByRole('textbox', { name: 'Extra instructions for the AI' })).not.toBeInTheDocument();

      fireEvent.change(conf, { target: { value: '0.5' } });

      expect(onChange).toHaveBeenLastCalledWith({ threshold: 0.5 });
    });

    it('Grounding DINO comes in two sizes', () => {
      renderBar({ settings: DINO });
      const size = screen.getByRole('combobox', { name: 'Grounding DINO size' });
      expect([...size.options].map((o) => o.textContent)).toEqual(['tiny', 'base (more VRAM)']);
    });

    it('a detector can not refine', () => {
      renderBar({ settings: DINO });
      expect(screen.getByRole('button', { name: 'Refine all' })).toBeDisabled();
    });
  });

  it('can not start another batch while one is being queued', () => {
    renderBar({ busy: true });
    expect(screen.getByRole('button', { name: 'Label all unlabeled' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Refine all' })).toBeDisabled();
  });

  describe('Ollama model', () => {
    const OLLAMA = { engine: 'ollama', model: 'qwen3-vl:4b', extra: '', grid: false };
    const status = (models) => ({ workerOnline: true, lastSeenAt: new Date().toISOString(), paused: [],
      engines: { ollama: { ready: true, note: '', models } } });

    it("switches to a pulled vision model when the chosen one isn't pulled", () => {
      const { onChange } = renderBar({ settings: OLLAMA, engineStatus: status(['llama3.2:latest', 'llava:7b']) });
      expect(onChange).toHaveBeenCalledWith({ model: 'llava:7b' });
    });

    it('warns when none of the pulled models can see images', () => {
      const { onChange } = renderBar({ settings: OLLAMA, engineStatus: status(['llama3.2:latest', 'gemma3:270m']) });
      expect(screen.getByText(/qwen3-vl:4b isn't pulled in Ollama/)).toHaveClass('engine-note', 'bad');
      expect(onChange).not.toHaveBeenCalled();
    });

    it("doesn't fight you while you type a model name: it only checks when the model list or engine changes", () => {
      const handlers = { onChange: vi.fn(), onRunAll: vi.fn(), onRefineAll: vi.fn(), onStop: vi.fn() };
      const models = status(['llava:7b']);
      const { rerender } = render(<EngineBar settings={{ ...OLLAMA, model: 'llava:7b' }} summary={IDLE} notice="" busy={false}
                                             engineStatus={models} {...handlers} />);
      rerender(<EngineBar settings={{ ...OLLAMA, model: 'q' }} summary={IDLE} notice="" busy={false}
                          engineStatus={models} {...handlers} />);
      expect(handlers.onChange).not.toHaveBeenCalled();
      rerender(<EngineBar settings={{ ...OLLAMA, model: 'q' }} summary={IDLE} notice="" busy={false}
                          engineStatus={status(['llava:7b', 'moondream:latest'])} {...handlers} />);
      expect(handlers.onChange).toHaveBeenCalledWith({ model: 'llava:7b' });
    });

    it('leaves a pulled model alone', () => {
      const { onChange } = renderBar({ settings: OLLAMA, engineStatus: status(['qwen3-vl:4b']) });
      expect(onChange).not.toHaveBeenCalled();
      expect(screen.queryByText(/isn't pulled/)).not.toBeInTheDocument();
    });
  });
});

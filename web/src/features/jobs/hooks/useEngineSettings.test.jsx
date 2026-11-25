import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useEngineSettings } from './useEngineSettings';

describe('useEngineSettings', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('starts with Gemini and its default model', () => {
    const { result } = renderHook(() => useEngineSettings());
    expect(result.current[0]).toMatchObject({ engine: 'gemini', model: 'gemini-3.5-flash-lite', extra: '', grid: false });
  });

  it('remembers changes for next time, like today', () => {
    const first = renderHook(() => useEngineSettings());
    act(() => first.result.current[1]({ model: 'gemini-3.5-flash', extra: 'top shelf only' }));
    expect(first.result.current[0].model).toBe('gemini-3.5-flash');

    const next = renderHook(() => useEngineSettings());
    expect(next.result.current[0]).toMatchObject({ engine: 'gemini', model: 'gemini-3.5-flash', extra: 'top shelf only' });
  });

  it('switching engine picks its default model, and switching back brings the model you used', () => {
    const { result } = renderHook(() => useEngineSettings());
    act(() => result.current[1]({ engine: 'ollama' }));
    expect(result.current[0].model).toBe('qwen3-vl:4b');
    act(() => result.current[1]({ model: 'gemma3:4b' }));
    act(() => result.current[1]({ engine: 'gemini' }));
    expect(result.current[0].model).toBe('gemini-3.5-flash-lite');

    act(() => result.current[1]({ engine: 'ollama' }));

    expect(result.current[0].model).toBe('gemma3:4b');
  });

  it('switching to a detector starts at its own confidence', () => {
    const { result } = renderHook(() => useEngineSettings());
    act(() => result.current[1]({ engine: 'grounding_dino' }));
    expect(result.current[0].threshold).toBe(0.35);
    act(() => result.current[1]({ engine: 'yolo_world' }));
    expect(result.current[0].threshold).toBe(0.25);
  });

  it('settings saved before the other engines existed still load', () => {
    localStorage.setItem('annotator.engine', JSON.stringify({ engine: 'gemini', model: 'gemini-x', extra: '' }));
    const { result } = renderHook(() => useEngineSettings());
    act(() => result.current[1]({ engine: 'claude' }));
    expect(result.current[0]).toMatchObject({ engine: 'claude', model: 'sonnet' });
  });

  it('still works when the browser blocks storage', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    const { result } = renderHook(() => useEngineSettings());
    act(() => result.current[1]({ extra: 'x' }));
    expect(result.current[0].extra).toBe('x');
  });
});

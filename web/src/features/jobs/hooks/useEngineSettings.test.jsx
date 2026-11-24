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
    expect(result.current[0]).toEqual({ engine: 'gemini', model: 'gemini-3.5-flash-lite', extra: '' });
  });

  it('remembers changes for next time, like today', () => {
    const first = renderHook(() => useEngineSettings());
    act(() => first.result.current[1]({ model: 'gemini-3.5-flash', extra: 'top shelf only' }));
    expect(first.result.current[0].model).toBe('gemini-3.5-flash');

    const next = renderHook(() => useEngineSettings());
    expect(next.result.current[0]).toEqual({ engine: 'gemini', model: 'gemini-3.5-flash', extra: 'top shelf only' });
  });

  it('still works when the browser blocks storage', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    const { result } = renderHook(() => useEngineSettings());
    act(() => result.current[1]({ extra: 'x' }));
    expect(result.current[0].extra).toBe('x');
  });
});

import { describe, expect, it } from 'vitest';
import { ENGINES, engineOptions } from './engines';

const SETTINGS = { model: 'm', extra: 'top shelf', grid: true, threshold: 0.4 };

describe('engines', () => {
  it('offers all five engines, Gemini first', () => {
    expect(ENGINES.map((e) => e.value)).toEqual(['gemini', 'claude', 'ollama', 'grounding_dino', 'yolo_world']);
  });

  it('detectors can not refine', () => {
    expect(ENGINES.filter((e) => !e.supportsRefine).map((e) => e.value)).toEqual(['grounding_dino', 'yolo_world']);
  });
});

describe('engineOptions: only what the chosen engine takes', () => {
  it('Gemini: model and extra instructions', () => {
    expect(engineOptions({ engine: 'gemini', ...SETTINGS })).toEqual({ model: 'm', extra: 'top shelf' });
  });

  it('Claude and Ollama: also the grid switch', () => {
    expect(engineOptions({ engine: 'claude', ...SETTINGS })).toEqual({ model: 'm', extra: 'top shelf', grid: true });
    expect(engineOptions({ engine: 'ollama', ...SETTINGS, grid: undefined })).toEqual(
      { model: 'm', extra: 'top shelf', grid: false });
  });

  it('detectors: model and confidence, no extra instructions', () => {
    expect(engineOptions({ engine: 'grounding_dino', ...SETTINGS })).toEqual({ model: 'm', threshold: 0.4 });
  });

  it('a detector without a confidence yet uses its own default', () => {
    expect(engineOptions({ engine: 'yolo_world', model: 'm', threshold: null })).toEqual({ model: 'm', threshold: 0.25 });
  });
});

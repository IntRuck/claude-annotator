import { describe, expect, it } from 'vitest';
import { ENGINES, engineOptions, ollamaModelCheck } from './engines';

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

describe('ollamaModelCheck (today: the page switched to a pulled vision model)', () => {
  const NOT_PULLED = "qwen3-vl:4b isn't pulled in Ollama, and none of its models can see images. Run: ollama pull qwen3-vl:4b";

  it('keeps a model that is pulled', () => {
    expect(ollamaModelCheck('ollama', 'qwen3-vl:4b', ['qwen3-vl:4b'])).toEqual({});
  });

  it("switches to a pulled vision model when the chosen one isn't pulled", () => {
    expect(ollamaModelCheck('ollama', 'qwen3-vl:4b', ['llama3.2:latest', 'qwen2.5vl:7b'])).toEqual({ switchTo: 'qwen2.5vl:7b' });
    expect(ollamaModelCheck('ollama', 'qwen3-vl:4b', ['llava:7b'])).toEqual({ switchTo: 'llava:7b' });
  });

  it('warns with the pull command when no pulled model can see images', () => {
    expect(ollamaModelCheck('ollama', 'qwen3-vl:4b', ['llama3.2:latest', 'gemma3:270m'])).toEqual({ warning: NOT_PULLED });
  });

  it('counts gemma3 as a vision model, except its text-only 270m and 1b sizes', () => {
    expect(ollamaModelCheck('ollama', 'x', ['gemma3:4b'])).toEqual({ switchTo: 'gemma3:4b' });
    expect(ollamaModelCheck('ollama', 'x', ['gemma3:latest'])).toEqual({ switchTo: 'gemma3:latest' });
    expect(ollamaModelCheck('ollama', 'x', ['gemma3:1b']).switchTo).toBeUndefined();
  });

  it('says nothing for other engines, or before the worker has listed the models', () => {
    expect(ollamaModelCheck('gemini', 'qwen3-vl:4b', ['llava:7b'])).toEqual({});
    expect(ollamaModelCheck('ollama', 'qwen3-vl:4b', undefined)).toEqual({});
    expect(ollamaModelCheck('ollama', 'qwen3-vl:4b', [])).toEqual({});
  });
});

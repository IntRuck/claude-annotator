/** Engines the bar offers. More (Claude CLI, Ollama, detectors) arrive in a later slice. */
export const ENGINES = [
  {
    value: 'gemini',
    label: 'Gemini (API key)',
    modelLabel: 'Gemini model',
    defaultModel: 'gemini-3.5-flash-lite',
    models: ['gemini-3.5-flash-lite', 'gemini-3.5-flash'],
  },
];

export const engineInfo = (value) => ENGINES.find((e) => e.value === value) ?? ENGINES[0];

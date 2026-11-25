import { useState } from 'react';
import { ENGINES, engineInfo } from '../lib/engines';

const KEY = 'annotator.engine';
const DEFAULTS = {
  engine: ENGINES[0].value, model: ENGINES[0].defaultModel, extra: '', grid: false, threshold: null, models: {},
};

function load() {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    return DEFAULTS;
  }
}

/** Switching engine brings back the model last used with it (else its default) and a detector's own confidence.
 * `models` remembers the model per engine. */
function applyChange(settings, patch) {
  const next = { ...settings, ...patch };
  if (patch.engine && patch.engine !== settings.engine) {
    const info = engineInfo(patch.engine);
    next.model = patch.model ?? settings.models?.[patch.engine] ?? info.defaultModel;
    next.threshold = info.threshold ?? null;
  }
  next.models = { ...settings.models, [settings.engine]: settings.model, [next.engine]: next.model };
  return next;
}

/** The chosen engine and its options, remembered in this browser (like today). */
export function useEngineSettings() {
  const [settings, setSettings] = useState(load);
  const update = (patch) => {
    const next = applyChange(settings, patch);
    setSettings(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Storage blocked (private window): the choice just isn't remembered.
    }
  };
  return [settings, update];
}

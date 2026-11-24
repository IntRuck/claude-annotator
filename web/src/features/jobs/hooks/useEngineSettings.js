import { useState } from 'react';
import { ENGINES } from '../lib/engines';

const KEY = 'annotator.engine';
const DEFAULTS = { engine: ENGINES[0].value, model: ENGINES[0].defaultModel, extra: '' };

function load() {
  try {
    return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || '{}') };
  } catch {
    return DEFAULTS;
  }
}

/** The chosen engine, model and extra instructions, remembered in this browser (like today). */
export function useEngineSettings() {
  const [settings, setSettings] = useState(load);
  const update = (patch) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      // Storage blocked (private window): the choice just isn't remembered.
    }
  };
  return [settings, update];
}

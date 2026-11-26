import { useEffect, useSyncExternalStore } from 'react';
import { readChoice, resolveTheme, saveChoice } from '../lib/theme';

// One shared choice for every component that asks (the projects page switch, the workspace menu), kept in the
// browser's storage; components re-render when it changes.
const listeners = new Set();
const subscribeChoice = (onChange) => {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
};
const setChoice = (choice) => {
  saveChoice(choice);
  listeners.forEach((onChange) => onChange());
};

const DARK = '(prefers-color-scheme: dark)';
const subscribeComputer = (onChange) => {
  const media = window.matchMedia?.(DARK);
  media?.addEventListener('change', onChange);
  return () => media?.removeEventListener('change', onChange);
};
const computerIsDark = () => Boolean(window.matchMedia?.(DARK).matches);

/** `{ choice, setChoice, theme }`: choice is 'light' | 'dark' | 'auto', theme is what the page shows. Puts the theme on
 * `<html data-theme>` (index.css swaps the colours) and follows the computer while on Auto. */
export function useTheme() {
  const choice = useSyncExternalStore(subscribeChoice, readChoice);
  const prefersDark = useSyncExternalStore(subscribeComputer, computerIsDark);
  const theme = resolveTheme(choice, prefersDark);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  return { choice, setChoice, theme };
}

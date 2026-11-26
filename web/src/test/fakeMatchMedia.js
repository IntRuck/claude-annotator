import { vi } from 'vitest';

/** Stands in for the computer's light/dark setting in tests: `const media = fakeMatchMedia(true)` says the computer
 * is dark; `act(() => media.change(false))` switches it. Undo with `vi.unstubAllGlobals()`. */
export function fakeMatchMedia(matches) {
  const listeners = new Set();
  const media = {
    matches,
    addEventListener: (_type, fn) => listeners.add(fn),
    removeEventListener: (_type, fn) => listeners.delete(fn),
    change(next) {
      media.matches = next;
      listeners.forEach((fn) => fn({ matches: next }));
    },
  };
  vi.stubGlobal('matchMedia', () => media);
  return media;
}

import { afterEach, describe, expect, it } from 'vitest';
import { readChoice, resolveTheme, saveChoice } from './theme';

describe('resolveTheme', () => {
  it.each([
    ['light', true, 'light'], ['light', false, 'light'],
    ['dark', false, 'dark'], ['dark', true, 'dark'],
    ['auto', true, 'dark'], ['auto', false, 'light'],
  ])('%s, with the computer dark = %s, is %s', (choice, prefersDark, want) => {
    expect(resolveTheme(choice, prefersDark)).toBe(want);
  });
});

describe('the saved choice', () => {
  afterEach(() => {
    localStorage.clear();
  });

  it('is Auto when nothing is saved', () => {
    expect(readChoice()).toBe('auto');
  });

  it('comes back after saving', () => {
    saveChoice('dark');
    expect(localStorage.getItem('annotator-theme')).toBe('dark');
    expect(readChoice()).toBe('dark');
  });

  it('counts anything else saved as Auto', () => {
    localStorage.setItem('annotator-theme', 'purple');
    expect(readChoice()).toBe('auto');
  });
});

import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fakeMatchMedia } from '@/test/fakeMatchMedia';
import ThemeSwitch from './ThemeSwitch';

const pageTheme = () => document.documentElement.dataset.theme;

describe('ThemeSwitch', () => {
  let media;
  beforeEach(() => {
    media = fakeMatchMedia(false);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it('starts on Auto, following the computer', () => {
    render(<ThemeSwitch />);
    expect(screen.getByRole('radio', { name: 'Auto' })).toBeChecked();
    expect(pageTheme()).toBe('light');
  });

  it('choosing Dark turns the page dark and remembers it', async () => {
    render(<ThemeSwitch />);
    await userEvent.click(screen.getByRole('radio', { name: 'Dark' }));
    expect(screen.getByRole('radio', { name: 'Dark' })).toBeChecked();
    expect(pageTheme()).toBe('dark');
    expect(localStorage.getItem('annotator-theme')).toBe('dark');
  });

  it('on Auto, follows the computer switching to dark', () => {
    render(<ThemeSwitch />);
    act(() => media.change(true));
    expect(pageTheme()).toBe('dark');
  });

  it('Light stays light while the computer is dark', async () => {
    media = fakeMatchMedia(true);
    render(<ThemeSwitch />);
    await userEvent.click(screen.getByRole('radio', { name: 'Light' }));
    expect(pageTheme()).toBe('light');
  });

  it('opens on the choice saved earlier', () => {
    localStorage.setItem('annotator-theme', 'dark');
    render(<ThemeSwitch />);
    expect(screen.getByRole('radio', { name: 'Dark' })).toBeChecked();
    expect(pageTheme()).toBe('dark');
  });
});

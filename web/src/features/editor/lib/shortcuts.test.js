import { describe, expect, it } from 'vitest';
import { commandFor } from './shortcuts';

const key = (k, extra = {}) => ({ key: k, ctrlKey: false, metaKey: false, shiftKey: false, target: { tagName: 'CANVAS' }, ...extra });

describe('commandFor (today\'s keyboard shortcuts)', () => {
  it.each([
    ['a', 'prev'], ['ArrowLeft', 'prev'], ['d', 'next'], ['ArrowRight', 'next'],
    ['r', 'approve'], ['g', 'flag'], ['s', 'save'], ['b', 'boxTool'], ['v', 'panTool'],
    ['h', 'solo'], ['l', 'names'], ['f', 'fit'], ['Delete', 'delete'], ['Backspace', 'delete'],
    ['Escape', 'deselect'], [' ', 'panHold'], ['D', 'next'], ['o', 'outlineTool'], ['Enter', 'closeOutline'],
  ])('%s -> %s', (k, command) => {
    expect(commandFor(key(k))).toBe(command);
  });

  it('1-9 pick a class', () => {
    expect(commandFor(key('1'))).toEqual({ pickClass: 0 });
    expect(commandFor(key('9'))).toEqual({ pickClass: 8 });
    expect(commandFor(key('0'))).toBeNull();
  });

  it('Ctrl/Cmd+Z undoes; Ctrl+Y and Ctrl+Shift+Z redo; Ctrl+S saves; other Ctrl keys do nothing', () => {
    expect(commandFor(key('z', { ctrlKey: true }))).toBe('undo');
    expect(commandFor(key('z', { metaKey: true }))).toBe('undo');
    expect(commandFor(key('y', { ctrlKey: true }))).toBe('redo');
    expect(commandFor(key('Z', { ctrlKey: true, shiftKey: true }))).toBe('redo');
    expect(commandFor(key('s', { ctrlKey: true }))).toBe('save');
    expect(commandFor(key('d', { ctrlKey: true }))).toBeNull();
  });

  it('is off while typing in a field, except Esc which leaves the field', () => {
    for (const tagName of ['INPUT', 'SELECT', 'TEXTAREA']) {
      expect(commandFor(key('d', { target: { tagName } }))).toBeNull();
      expect(commandFor(key('Escape', { target: { tagName } }))).toBe('blur');
    }
  });

  it('is off while a dialog is open', () => {
    expect(commandFor(key('d'), { dialogOpen: true })).toBeNull();
  });
});

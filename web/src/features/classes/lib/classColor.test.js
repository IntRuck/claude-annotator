import { describe, expect, it } from 'vitest';
import { classColor } from './classColor';

describe('classColor', () => {
  it('spreads hues by the golden angle, same as today\'s app', () => {
    expect(classColor(0)).toBe('hsl(0 80% 50%)');
    expect(classColor(1)).toBe('hsl(137.508 80% 50%)');
    expect(classColor(3)).toBe(`hsl(${(3 * 137.508) % 360} 80% 50%)`);
  });

  it('is stable for the same class index', () => {
    expect(classColor(42)).toBe(classColor(42));
  });
});

import { describe, expect, it } from 'vitest';
import { CUSTOM, apiFilter, keepOnly } from './filters';

describe('image filters', () => {
  it('asks the API for all images when a picked set is shown', () => {
    expect(apiFilter(CUSTOM)).toBe('all');
    expect(apiFilter('auto')).toBe('auto');
  });

  it('keeps only the picked images, in list order, with the counts unchanged', () => {
    const data = { items: [{ id: 1 }, { id: 2 }, { id: 3 }], counts: { all: 3 } };
    expect(keepOnly(data, [3, 1, 9])).toEqual({ items: [{ id: 1 }, { id: 3 }], counts: { all: 3 } });
  });
});

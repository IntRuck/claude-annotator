import { describe, expect, it } from 'vitest';
import { arrangeProjects, SORTS } from './listing';

const P = [
  { id: 1, name: 'shelf A', description: 'Store 3', createdAt: '2026-11-01T00:00:00Z', lastChangedAt: '2026-11-20T00:00:00Z' },
  { id: 2, name: 'Fridge', description: 'Drinks, store 5', createdAt: '2026-11-10T00:00:00Z', lastChangedAt: '2026-11-24T00:00:00Z' },
  { id: 3, name: 'Bakery', description: '', createdAt: '2026-11-05T00:00:00Z', lastChangedAt: '2026-11-05T00:00:00Z' },
];
const names = (list) => list.map((p) => p.name);

describe('arrangeProjects', () => {
  it('puts the most recently changed first by default', () => {
    expect(names(arrangeProjects(P))).toEqual(['Fridge', 'shelf A', 'Bakery']);
  });

  it('sorts by name ignoring capitals', () => {
    expect(names(arrangeProjects(P, { sort: 'name' }))).toEqual(['Bakery', 'Fridge', 'shelf A']);
  });

  it('sorts newest created first', () => {
    expect(names(arrangeProjects(P, { sort: 'newest' }))).toEqual(['Fridge', 'Bakery', 'shelf A']);
  });

  it('search matches the name or the description, ignoring capitals and spaces around it', () => {
    expect(names(arrangeProjects(P, { query: ' SHELF ' }))).toEqual(['shelf A']);
    expect(names(arrangeProjects(P, { query: 'store' }))).toEqual(['Fridge', 'shelf A']);
  });

  it('does not change the list it was given', () => {
    const copy = [...P];
    arrangeProjects(P, { sort: 'name' });
    expect(P).toEqual(copy);
  });

  it('offers each sort with a label', () => {
    expect(SORTS.map(([value]) => value)).toEqual(['changed', 'name', 'newest']);
  });
});

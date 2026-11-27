import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useEffect, useReducer } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fitView, toStage } from '../lib/geometry';
import { editorReducer, initialEditor } from '../lib/history';
import Editor from './Editor';

// Konva needs a real canvas; a stand-in renders each shape as a div.
vi.mock('react-konva', () => import('@/test/konvaStub'));

const IMAGE = { id: 1, width: 200, height: 100, flagged: false, flagReason: '' };
const CLASSES = [{ index: 0, name: 'can' }, { index: 1, name: 'jar' }];
// jsdom has no layout: the canvas keeps its 800x600 starting size, and its corner is at (0, 0).
const VIEW = fitView(200, 100, 800, 600);
const PLAIN = { cls: 0, x1: 0.6, y1: 0.6, x2: 0.9, y2: 0.9, source: 'ai' };
const seen = { state: null }; // the editor state after the last render

function Harness({ boxes = [], selected = -1 }) {
  const [state, dispatch] = useReducer(editorReducer, { ...initialEditor, boxes, selected });
  useEffect(() => { seen.state = state; });
  const editor = { state, dispatch, save: vi.fn(() => Promise.resolve()), conflict: false, error: null, reload: vi.fn() };
  return (
    <Editor editor={editor} image={IMAGE} imageUrl="/api/images/1/file" classes={CLASSES} currentClass={1}
            hidden={new Set()} solo={false} setSolo={vi.fn()} dialogOpen={false} onPickClass={vi.fn()} onStep={vi.fn()}
            onApprove={vi.fn()} onToggleFlag={vi.fn()} onNeedClasses={vi.fn()} />
  );
}

function clickAt(container, [fx, fy]) {
  const [clientX, clientY] = toStage(VIEW, { iw: 200, ih: 100 }, [fx, fy]);
  fireEvent.mouseDown(container.querySelector('.editor-canvas'), { clientX, clientY, button: 0 });
  fireEvent.mouseUp(window);
}

const rounded = (points) => points.map((p) => p.map((v) => Number(v.toFixed(6))));
const TRIANGLE = [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]];

describe('Editor: the Outline tool', () => {
  it('O, three clicks and Enter add an outlined object of the current class', async () => {
    const { container } = render(<Harness />);
    await userEvent.keyboard('o');
    expect(screen.getByTitle(/Outline tool/)).toHaveAttribute('aria-pressed', 'true');
    TRIANGLE.forEach((dot) => clickAt(container, dot));
    expect(screen.getAllByTestId('draft-dot')).toHaveLength(3);
    await userEvent.keyboard('{Enter}');

    expect(seen.state.boxes).toHaveLength(1);
    expect(seen.state.boxes[0]).toMatchObject({ cls: 1, source: 'human' });
    expect(rounded(seen.state.boxes[0].points)).toEqual(TRIANGLE);
    expect(screen.queryByTestId('draft-outline')).not.toBeInTheDocument();
  });

  it('Backspace and Ctrl+Z while drawing remove only the last dot; the boxes are untouched', async () => {
    const { container } = render(<Harness boxes={[PLAIN]} />);
    await userEvent.keyboard('o');
    clickAt(container, [0.1, 0.1]);
    clickAt(container, [0.5, 0.1]);
    clickAt(container, [0.2, 0.2]);
    await userEvent.keyboard('{Backspace}');
    await userEvent.keyboard('{Control>}z{/Control}');
    expect(seen.state.boxes).toEqual([PLAIN]);
    expect(screen.getAllByTestId('draft-dot')).toHaveLength(1);

    clickAt(container, [0.5, 0.1]);
    clickAt(container, [0.3, 0.5]);
    await userEvent.keyboard('{Enter}');
    expect(seen.state.boxes).toHaveLength(2);
    expect(rounded(seen.state.boxes[1].points)).toEqual(TRIANGLE);
  });

  it('Esc while drawing cancels the outline and keeps the selected box selected', async () => {
    const { container } = render(<Harness boxes={[PLAIN]} selected={0} />);
    await userEvent.keyboard('o');
    clickAt(container, [0.1, 0.1]);
    clickAt(container, [0.5, 0.1]);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByTestId('draft-outline')).not.toBeInTheDocument();
    expect(seen.state.selected).toBe(0);
    await userEvent.keyboard('{Escape}');
    expect(seen.state.selected).toBe(-1);
  });

  it('with a box selected, the outline goes onto that box and it keeps its class', async () => {
    const { container } = render(<Harness boxes={[PLAIN]} selected={0} />);
    await userEvent.keyboard('o');
    [[0.65, 0.65], [0.85, 0.65], [0.75, 0.85]].forEach((dot) => clickAt(container, dot));
    await userEvent.keyboard('{Enter}');
    expect(seen.state.boxes).toHaveLength(1);
    expect(seen.state.boxes[0]).toMatchObject({ cls: 0, source: 'human' });
    expect(rounded(seen.state.boxes[0].points)).toEqual([[0.65, 0.65], [0.85, 0.65], [0.75, 0.85]]);
    expect(seen.state.boxes[0].x2).toBeCloseTo(0.85);
  });

  it('Enter on a focused button still presses it when no outline is being drawn', async () => {
    render(<Harness />);
    screen.getByTitle('Keyboard shortcuts').focus();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByText('Remove the last dot')).toBeInTheDocument();
  });
});

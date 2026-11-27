import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import EditorCanvas from './EditorCanvas';

// Konva needs a real canvas; a stand-in renders each shape as a div so we can check what is drawn.
vi.mock('react-konva', () => import('@/test/konvaStub'));

const classes = [{ index: 0, name: 'can' }, { index: 1, name: 'jar' }];
const boxes = [{ cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5 }, { cls: 1, x1: 0.6, y1: 0.6, x2: 0.9, y2: 0.9 }];
const display = { brightness: 1, contrast: 1, showAnnotations: true, showNames: true, fillBoxes: false };

function renderCanvas(props = {}) {
  return render(
    <EditorCanvas imageUrl="/api/images/1/file" img={{ iw: 200, ih: 100 }} boxes={boxes} classes={classes}
                  selected={-1} hidden={new Set()} solo={false} display={display} view={{ scale: 1, ox: 0, oy: 0 }}
                  tool="box" spaceHeld={false} currentClass={0} draft={null}
                  onView={vi.fn()} onPointerDown={vi.fn()} onPointerMove={vi.fn()} onPointerUp={vi.fn()} {...props} />,
  );
}

describe('EditorCanvas', () => {
  it('draws the image with brightness/contrast and a box per box with its class colour and name', () => {
    renderCanvas({ display: { ...display, brightness: 1.5, contrast: 0.8 } });
    expect(screen.getByTestId('stage-image')).toHaveStyle({ filter: 'brightness(1.5) contrast(0.8)' });
    const drawn = screen.getAllByTestId('box');
    expect(drawn).toHaveLength(2);
    expect(drawn[0]).toHaveAttribute('data-stroke', 'hsl(0 80% 50%)');
    expect(screen.getByText('can')).toBeInTheDocument();
    expect(screen.getByText('jar')).toBeInTheDocument();
  });

  it('hides class names (L), hidden boxes, and everything but the selected box in solo mode (H)', () => {
    const { unmount } = renderCanvas({ display: { ...display, showNames: false }, hidden: new Set([1]) });
    expect(screen.getAllByTestId('box')).toHaveLength(1);
    expect(screen.queryByText('can')).not.toBeInTheDocument();
    unmount();
    renderCanvas({ solo: true, selected: 1 });
    expect(screen.getAllByTestId('box')).toHaveLength(1);
    expect(screen.getAllByTestId('handle')).toHaveLength(4);
  });

  it('draws nothing over the image when annotations are switched off', () => {
    renderCanvas({ display: { ...display, showAnnotations: false } });
    expect(screen.queryAllByTestId('box')).toHaveLength(0);
  });

  it('shows the box being drawn as a dashed preview', () => {
    renderCanvas({ draft: { a: [0.1, 0.1], b: [0.3, 0.3] } });
    expect(screen.getByTestId('draft')).toBeInTheDocument();
  });

  describe('outlines', () => {
    // View scale 1 on a 200x100 image: dot (x, y) is drawn at stage (200x, 100y).
    const outlined = { cls: 0, x1: 0.1, y1: 0.1, x2: 0.5, y2: 0.5, points: [[0.1, 0.1], [0.5, 0.1], [0.3, 0.5]] };

    it('draws an outlined object as its outline, not its box', () => {
      renderCanvas({ boxes: [outlined, boxes[1]] });
      const outline = screen.getByTestId('outline');
      expect(outline).toHaveAttribute('data-points', '20,10,100,10,60,50');
      expect(outline).toHaveAttribute('data-closed', 'true');
      expect(outline).toHaveAttribute('data-stroke', 'hsl(0 80% 50%)');
      expect(screen.getAllByTestId('box')).toHaveLength(1); // only the plain box
      expect(screen.getByText('can')).toBeInTheDocument();
    });

    it('a selected outline shows a handle on every dot', () => {
      renderCanvas({ boxes: [outlined], selected: 0 });
      expect(screen.getAllByTestId('handle')).toHaveLength(3);
    });

    it('draws the outline in progress with a dashed line to the pointer', () => {
      renderCanvas({ outlineDraft: { points: [[0.1, 0.1], [0.5, 0.1]], hover: [80, 40] } });
      expect(screen.getByTestId('draft-outline')).toHaveAttribute('data-points', '20,10,100,10');
      expect(screen.getByTestId('draft-outline')).toHaveAttribute('data-closed', 'false');
      expect(screen.getByTestId('draft-next')).toHaveAttribute('data-points', '100,10,80,40');
      expect(screen.getByTestId('draft-next')).toHaveAttribute('data-dash', 'yes');
      expect(screen.getAllByTestId('draft-dot')).toHaveLength(2);
    });

    it('reports hover and double-click as stage points', () => {
      const onHover = vi.fn();
      const onDoubleClick = vi.fn();
      const { container } = renderCanvas({ onHover, onDoubleClick });
      const wrap = container.querySelector('.editor-canvas');
      fireEvent.mouseMove(wrap, { clientX: 30, clientY: 40 });
      fireEvent.doubleClick(wrap, { clientX: 5, clientY: 6 });
      expect(onHover).toHaveBeenCalledWith([30, 40]);
      expect(onDoubleClick).toHaveBeenCalledWith([5, 6]);
    });
  });
});

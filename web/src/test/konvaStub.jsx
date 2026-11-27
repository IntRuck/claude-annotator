/* Stand-in for react-konva in tests (jsdom has no real canvas). Each shape renders as a div. */
export const Stage = ({ children }) => <div data-testid="stage">{children}</div>;
export const Layer = ({ children }) => <div>{children}</div>;
export const Group = ({ children }) => <div>{children}</div>;
export const Rect = ({ name, stroke, fill }) => <div data-testid={name ?? 'rect'} data-stroke={stroke} data-fill={fill ?? ''} />;
export const Text = ({ text }) => <span>{text}</span>;
export const Line = ({ name, stroke, fill, points, closed, dash }) => (
  <div data-testid={name ?? 'line'} data-stroke={stroke} data-fill={fill ?? ''} data-points={(points ?? []).join(',')}
       data-closed={String(Boolean(closed))} data-dash={dash ? 'yes' : ''} />
);

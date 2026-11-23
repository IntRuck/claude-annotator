import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '@/app/App';

describe('App', () => {
  it('shows the app name on the home page', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Claude Annotator' })).toBeInTheDocument();
  });
});

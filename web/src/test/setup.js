import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach } from 'vitest';

// Vitest globals are off, so Testing Library can't register its own cleanup: unmount after each test.
afterEach(() => cleanup());

// findBy*/waitFor wait up to 3 s (default 1 s). With every test file running in parallel on a busy laptop,
// the first render of the workspace page can take over a second.
configure({ asyncUtilTimeout: 3000 });

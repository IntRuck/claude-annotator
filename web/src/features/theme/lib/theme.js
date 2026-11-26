/** Light / Dark / Auto. Auto follows the computer's setting. The same rule runs in index.html before the app loads,
 * so the page doesn't flash white: keep the two in step. */
export const THEME_KEY = 'annotator-theme';
export const CHOICES = ['light', 'dark', 'auto'];

/** The theme the page shows: 'light' | 'dark'. */
export function resolveTheme(choice, prefersDark) {
  if (choice === 'auto') return prefersDark ? 'dark' : 'light';
  return choice;
}

/** The saved choice; nothing saved, or anything unexpected, counts as Auto. */
export function readChoice() {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return CHOICES.includes(saved) ? saved : 'auto';
  } catch {
    return 'auto'; // storage blocked by the browser
  }
}

export function saveChoice(choice) {
  try {
    localStorage.setItem(THEME_KEY, choice);
  } catch {
    // storage blocked: the choice still applies until the page reloads
  }
}

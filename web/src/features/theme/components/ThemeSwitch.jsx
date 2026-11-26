import { useTheme } from '../hooks/useTheme';
import { THEME_OPTIONS } from '../lib/options';
import '../styles/theme.css';

/** Light | Dark | Auto as one segmented control (real radio buttons, so the keyboard works as usual). */
export default function ThemeSwitch() {
  const { choice, setChoice } = useTheme();
  return (
    <div className="theme-switch" role="radiogroup" aria-label="Theme">
      {THEME_OPTIONS.map(([value, label, title]) => (
        <label key={value} title={title}>
          <input type="radio" name="theme" value={value} checked={choice === value} onChange={() => setChoice(value)} />
          {label}
        </label>
      ))}
    </div>
  );
}

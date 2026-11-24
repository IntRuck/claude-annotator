import { ENGINES, engineInfo } from '../lib/engines';
import { statusText } from '../lib/status';
import '../styles/jobs.css';

/** Top-bar AI controls, like today: engine, its options, extra instructions, Label all unlabeled, Stop, status. */
export default function EngineBar({ settings, summary, notice, busy, onChange, onRunAll, onStop }) {
  const info = engineInfo(settings.engine);
  const waiting = summary?.queued ?? 0;

  return (
    <div className="engine-bar" title="Which AI labels the images">
      <span className="lbl">AI</span>
      <select aria-label="AI engine" value={settings.engine}
              onChange={(e) => onChange({ engine: e.target.value, model: engineInfo(e.target.value).defaultModel })}>
        {ENGINES.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
      </select>
      <input aria-label={info.modelLabel} className="model" list={`${info.value}-models`} value={settings.model}
             onChange={(e) => onChange({ model: e.target.value })} />
      <datalist id={`${info.value}-models`}>
        {info.models.map((m) => <option key={m} value={m} />)}
      </datalist>
      <input aria-label="Extra instructions for the AI" className="extra" placeholder="Extra instructions"
             value={settings.extra} onChange={(e) => onChange({ extra: e.target.value })} />
      <button type="button" className="primary" disabled={busy} onClick={onRunAll}
              title="Label every image that has no labels yet (and retry the ones that failed)">
        Label all unlabeled
      </button>
      <button type="button" disabled={waiting === 0} onClick={onStop} title="Stop after the current image">■ Stop</button>
      <span className="ai-status" aria-live="polite">{notice || statusText(summary)}</span>
    </div>
  );
}

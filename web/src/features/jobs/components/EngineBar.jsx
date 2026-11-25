import { useNow } from '../hooks/useNow';
import { ENGINES, REFINE_NEEDS_VLM, engineInfo } from '../lib/engines';
import { statusText } from '../lib/status';
import { isWorkerOnline } from '../lib/workerStatus';
import '../styles/jobs.css';

const START_WORKER = 'Start it next to the API: cd backend && .venv/Scripts/python -m annotator.worker. '
  + 'Queued images wait until it runs.';

/** Its own clock tick, so only this badge re-renders every few seconds. */
function WorkerOffline({ status }) {
  const now = useNow(5000);
  if (isWorkerOnline(status, now) !== false) return null;
  return <span className="engine-note bad" title={START_WORKER}>Worker offline</span>;
}

/** A fixed list (Claude, Grounding DINO), or a box you can type in with suggestions: the models the worker found
 * (Gemini: what the key can use, Ollama: what's pulled), else the usual ones. */
function ModelPicker({ info, value, reported, onChange }) {
  if (info.choices) {
    return (
      <select aria-label={info.modelLabel} value={value} onChange={(e) => onChange(e.target.value)}>
        {info.choices.map(([model, text]) => <option key={model} value={model}>{text}</option>)}
      </select>
    );
  }
  const models = reported?.length ? reported : info.models;
  return (
    <>
      <input aria-label={info.modelLabel} className="model" list={`${info.value}-models`} value={value}
             onChange={(e) => onChange(e.target.value)} />
      <datalist id={`${info.value}-models`}>
        {models.map((m) => <option key={m} value={m} />)}
      </datalist>
    </>
  );
}

/** Top-bar AI controls, like today: engine, its options (model, grid, confidence, extra instructions), Label all
 * unlabeled, Refine all, Stop, status. `engineStatus` is what the worker reported (models, warnings, heartbeat). */
export default function EngineBar({
  settings, summary, notice, busy, engineStatus, onChange, onRunAll, onRefineAll, onStop,
}) {
  const info = engineInfo(settings.engine);
  const reported = engineStatus?.engines?.[settings.engine];
  const waiting = summary?.queued ?? 0;

  return (
    <div className="engine-bar" title="Which AI labels the images">
      <span className="lbl">AI</span>
      <select aria-label="AI engine" value={settings.engine} onChange={(e) => onChange({ engine: e.target.value })}>
        {ENGINES.map((e) => <option key={e.value} value={e.value}>{e.label}</option>)}
      </select>
      <ModelPicker info={info} value={settings.model} reported={reported?.models}
                   onChange={(model) => onChange({ model })} />
      {info.grid && (
        <label className="chk" title="Draw a 0-1000 grid on the image the AI sees">
          <input type="checkbox" checked={Boolean(settings.grid)} onChange={(e) => onChange({ grid: e.target.checked })} />
          grid
        </label>
      )}
      {info.threshold !== undefined && (
        <label className="chk" title="Minimum confidence to keep a box">
          conf
          <input type="number" aria-label="Minimum confidence" className="conf" min="0.05" max="0.95" step="0.05"
                 value={settings.threshold ?? info.threshold}
                 onChange={(e) => onChange({ threshold: e.target.value === '' ? null : Number(e.target.value) })} />
        </label>
      )}
      {info.takesExtra && (
        <input aria-label="Extra instructions for the AI" className="extra" placeholder="Extra instructions"
               value={settings.extra} onChange={(e) => onChange({ extra: e.target.value })} />
      )}
      {reported?.note && (
        <span className={`engine-note${reported.ready ? '' : ' bad'}`} title={reported.note}>{reported.note}</span>
      )}
      <button type="button" className="primary" disabled={busy} onClick={onRunAll}
              title="Label every image that has no labels yet (and retry the ones that failed)">
        Label all unlabeled
      </button>
      <button type="button" disabled={busy || !info.supportsRefine} onClick={onRefineAll}
              title={info.supportsRefine ? "Let the AI review and fix every auto-labeled image you haven't approved"
                : REFINE_NEEDS_VLM}>
        Refine all
      </button>
      <button type="button" disabled={waiting === 0} onClick={onStop} title="Stop after the current image">■ Stop</button>
      <span className="ai-status" aria-live="polite">{notice || statusText(summary)}</span>
      <WorkerOffline status={engineStatus} />
    </div>
  );
}

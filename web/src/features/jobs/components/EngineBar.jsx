import { useNow } from '../hooks/useNow';
import { ENGINES, engineInfo } from '../lib/engines';
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

/** Top-bar AI controls, like today: engine, its options, extra instructions, Label all unlabeled, Refine all,
 * Stop, status. `engineStatus` is what the worker reported (models, warnings, heartbeat). */
export default function EngineBar({
  settings, summary, notice, busy, engineStatus, onChange, onRunAll, onRefineAll, onStop,
}) {
  const info = engineInfo(settings.engine);
  const reported = engineStatus?.engines?.[settings.engine];
  const models = reported?.models?.length ? reported.models : info.models;
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
        {models.map((m) => <option key={m} value={m} />)}
      </datalist>
      <input aria-label="Extra instructions for the AI" className="extra" placeholder="Extra instructions"
             value={settings.extra} onChange={(e) => onChange({ extra: e.target.value })} />
      {reported?.note && (
        <span className={`engine-note${reported.ready ? '' : ' bad'}`} title={reported.note}>{reported.note}</span>
      )}
      <button type="button" className="primary" disabled={busy} onClick={onRunAll}
              title="Label every image that has no labels yet (and retry the ones that failed)">
        Label all unlabeled
      </button>
      <button type="button" disabled={busy || !info.supportsRefine} onClick={onRefineAll}
              title="Let the AI review and fix every auto-labeled image you haven't approved">
        Refine all
      </button>
      <button type="button" disabled={waiting === 0} onClick={onStop} title="Stop after the current image">■ Stop</button>
      <span className="ai-status" aria-live="polite">{notice || statusText(summary)}</span>
      <WorkerOffline status={engineStatus} />
    </div>
  );
}

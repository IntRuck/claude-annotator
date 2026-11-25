import { useState } from 'react';
import { ErrorBanner, LoadingState, Modal } from '@/components/ui';
import { classColor } from '@/features/classes';
import { useHealth } from '../hooks/useHealth';
import { clampLow, heatColour, imbalanceTone, issueTone, statusLine } from '../lib/healthView';
import '../styles/health.css';

function Card({ value, label, tone = '' }) {
  return (
    <div className="health-card">
      <div className={`v ${tone}`}>{value}</div>
      <div className="l">{label}</div>
    </div>
  );
}

function Bar({ share, colour }) {
  return <div className="health-bar" style={{ width: `${100 * share}%`, background: colour }} />;
}

function Heatmap({ rows }) {
  const max = Math.max(1, ...rows.flat());
  return (
    <div className="heatmap" role="img" aria-label="Where box centres sit"
         style={{ gridTemplateColumns: `repeat(${rows.length}, 1fr)` }}>
      {rows.flatMap((row, y) => row.map((count, x) => (
        <span key={`${y}-${x}`} className="heat-cell" style={count ? { background: heatColour(count, max) } : undefined}
              title={count ? `${count} box centre${count === 1 ? '' : 's'}` : undefined} />
      )))}
    </div>
  );
}

function Report({ report, onPickImages }) {
  const s = report.summary;
  const maxBoxes = Math.max(1, ...report.classes.map((c) => c.boxes));
  const maxSize = Math.max(1, ...report.sizes.map((b) => b.count));
  return (
    <div className="health">
      <div className="health-cards">
        <Card value={s.images} label={`images (${s.labeled} labeled)`} />
        <Card value={s.boxes} label={`boxes · ${s.avgBoxesPerImage} per image`} />
        <Card value={`${s.classesWithData}/${s.classes}`} label="classes with data" />
        <Card value={`${s.imbalanceRatio || '-'}×`} label="imbalance (most / fewest boxes)"
              tone={imbalanceTone(s.imbalanceRatio)} />
      </div>
      <p className="health-status">{`Status: ${statusLine(s.status)}`}</p>

      <div className="health-columns">
        <div>
          <h3>Classes (click one to see its images)</h3>
          <table className="health-table">
            <thead>
              <tr><th>ID</th><th>Class</th><th>Boxes</th><th className="bar-col" /><th>Images</th><th>Avg size</th><th /></tr>
            </thead>
            <tbody>
              {report.classes.map((c) => (
                <tr key={c.index}>
                  <td>{c.index}</td>
                  <td>
                    <span className="dot" style={{ background: classColor(c.index) }} />
                    <button type="button" className="link" onClick={() => onPickImages(`Class: ${c.name}`, c.imageIds)}>
                      {c.name}
                    </button>
                  </td>
                  <td>{c.boxes}</td>
                  <td className="bar-col"><Bar share={c.boxes / maxBoxes} colour={classColor(c.index)} /></td>
                  <td>{c.images}</td>
                  <td>{`${c.avgAreaPct}%`}</td>
                  <td className={c.boxes ? 'warn' : 'bad'}>{c.warn}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Issues (click one to review)</h3>
          <table className="health-table">
            <tbody>
              {report.issues.map((issue) => (
                <tr key={issue.key}>
                  <td>
                    {issue.count
                      ? <button type="button" className="link" onClick={() => onPickImages(issue.label, issue.imageIds)}>{issue.label}</button>
                      : issue.label}
                  </td>
                  <td className={`num ${issueTone(issue)}`}>{issue.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <h3>Box sizes (% of image area)</h3>
          <table className="health-table">
            <tbody>
              {report.sizes.map((b) => (
                <tr key={b.key}>
                  <td>{b.label}</td>
                  <td className="bar-col"><Bar share={b.count / maxSize} /></td>
                  <td className="num">{b.count}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Where boxes sit (box centres)</h3>
          <Heatmap rows={report.heatmap} />
          <p className="health-note">
            Dark = many boxes. A strong hotspot means the model may struggle with objects elsewhere in the frame.
          </p>
        </div>
      </div>
    </div>
  );
}

/** Dataset health check (today's Health check dialog). Clicking a class or an issue hands its images to
 * `onPickImages(label, imageIds)`, which shows them as a filter. */
export default function HealthDialog({ projectId, onClose, onPickImages }) {
  const [lowText, setLowText] = useState('100');
  const health = useHealth(projectId, clampLow(lowText));
  const actions = (
    <>
      <label className="health-low">
        Warn below
        <input type="number" min="1" aria-label="Warn below (boxes)" value={lowText}
               onChange={(e) => setLowText(e.target.value)} />
        boxes
      </label>
      <button type="button" onClick={() => health.refetch()} disabled={health.isFetching}>Refresh</button>
    </>
  );

  return (
    <Modal title="Dataset health" onClose={onClose} actions={actions} wide>
      <ErrorBanner error={health.error} />
      {health.isPending && <LoadingState />}
      {health.data && <Report report={health.data} onPickImages={onPickImages} />}
    </Modal>
  );
}

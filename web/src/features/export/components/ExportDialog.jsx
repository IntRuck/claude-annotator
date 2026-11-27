import { useState } from 'react';
import { ErrorBanner, Modal } from '@/components/ui';
import { exportUrl } from '../api/exportApi';
import { useExportSummary } from '../hooks/useExportSummary';
import '../styles/export.css';

const DOWNLOADS = [
  { format: 'yolo', label: 'Download YOLO zip', primary: true,
    title: 'Zip with images/train, images/val, labels and data.yaml' },
  { format: 'coco', label: 'Download COCO JSON', title: 'One COCO JSON file, for tools that use the COCO format' },
];

const SHAPES = [['boxes', 'Boxes'], ['outlines', 'Outlines']];

/** "1 image", "2 images". */
const count = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function summaryLine(s, shape) {
  if (!s) return 'Counting…';
  const outlines = shape === 'outlines';
  if (s.images === 0) return outlines ? 'No fully outlined images match these options.' : 'No labelled images match these options.';
  const what = outlines ? count(s.boxes, 'outline') : count(s.boxes, 'box', 'boxes');
  const line = `${count(s.images, 'image')} (${s.train} train / ${s.val} val) · ${what}`;
  return outlines && s.leftOut > 0 ? `${line} · ${s.leftOut} left out (not fully outlined)` : line;
}

/** Export labels (today's dialog, plus Boxes / Outlines). The browser downloads the file straight from the API. */
export default function ExportDialog({ projectId, onClose }) {
  const [options, setOptions] = useState({ onlyReviewed: false, skipFlagged: true, shape: 'boxes' });
  const summary = useExportSummary(projectId, options);
  const toggle = (key) => setOptions((o) => ({ ...o, [key]: !o[key] }));
  const ready = summary.data?.images > 0;

  return (
    <Modal title="Export labels" onClose={onClose}>
      <div className="export-dialog">
        <div role="radiogroup" aria-label="What to export" className="export-shape">
          {SHAPES.map(([value, label]) => (
            <label key={value} className="export-option">
              <input type="radio" name="export-shape" value={value} checked={options.shape === value}
                     onChange={() => setOptions((o) => ({ ...o, shape: value }))} />
              {label}
            </label>
          ))}
        </div>
        <label className="export-option">
          <input type="checkbox" checked={options.onlyReviewed} onChange={() => toggle('onlyReviewed')} />
          Approved images only <span className="muted">(only images you checked and approved)</span>
        </label>
        <label className="export-option">
          <input type="checkbox" checked={options.skipFlagged} onChange={() => toggle('skipFlagged')} />
          Leave out 🚩 flagged images <span className="muted">(probably bad labels)</span>
        </label>
        <ErrorBanner error={summary.error} />
        {!summary.error && <p className="export-summary">{summaryLine(summary.data, options.shape)}</p>}
        <div className="export-actions">
          {DOWNLOADS.map((d) => (ready
            ? <a key={d.format} className={`button${d.primary ? ' primary' : ''}`} href={exportUrl(projectId, d.format, options)}
                 title={d.title} download>{d.label}</a>
            : <button key={d.format} type="button" className={d.primary ? 'primary' : ''} disabled>{d.label}</button>))}
        </div>
        <p className="export-tips">
          <b>YOLO</b> is what you want for YOLO training (one .txt per image + data.yaml, 10% held out for
          validation). <b>COCO</b> is a single JSON file used by some other tools (e.g. DETR, Detectron, MMDetection).
          {' '}<b>Outlines</b> gives YOLO segmentation files and COCO with outlines, for outline (segmentation) models.
        </p>
      </div>
    </Modal>
  );
}

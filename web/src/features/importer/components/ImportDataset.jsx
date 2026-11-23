import { ErrorBanner, Modal } from '@/components/ui';
import { useImportDataset } from '../hooks/useImportDataset';
import { summaryLines } from '../lib/summary';
import '../styles/importer.css';

// Lets the browser send a whole folder (with sub-folders) through one file input.
const FOLDER_PICKER = { webkitdirectory: '', directory: '' };

export default function ImportDataset({ projectId, onClose }) {
  const run = useImportDataset(projectId);

  const choose = (e) => {
    const files = [...e.target.files];
    e.target.value = '';
    if (files.length) run.mutate(files);
  };

  return (
    <Modal title="Import a dataset" onClose={onClose}>
      <p className="import-tips">
        Pick a dataset folder: images, YOLO label files (<code>.txt</code>, matched to images by name), and optionally
        a class list (<code>classes.txt</code> or <code>data.yaml</code>). A folder from today&apos;s app also brings
        its statuses and flags (<code>_annot_state.json</code>).
      </p>
      <label className="import-picker">
        {run.isPending ? 'Importing…' : 'Choose dataset folder'}
        <input type="file" multiple aria-label="Choose dataset folder" onChange={choose} disabled={run.isPending}
               {...FOLDER_PICKER} />
      </label>
      <ErrorBanner error={run.error} />
      {run.data && (
        <div className="import-result">
          {summaryLines(run.data).map((line) => <p key={line}>{line}</p>)}
          {run.data.skipped.map((s) => <p key={s.fileName} className="muted">{s.fileName}: {s.reason}</p>)}
        </div>
      )}
    </Modal>
  );
}

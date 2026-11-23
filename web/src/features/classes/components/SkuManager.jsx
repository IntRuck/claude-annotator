import { useState } from 'react';
import { ErrorBanner, LoadingState, Modal } from '@/components/ui';
import { useAddClass, useClasses, useUpdateClass } from '../hooks/useClasses';
import { classColor } from '../lib/classColor';
import '../styles/classes.css';

const FIELDS = [
  { key: 'name', label: 'Name' },
  { key: 'detectorPrompt', label: 'Detector prompt' },
  { key: 'description', label: 'Description', multiline: true },
];

/** One SKU row. Each field saves on its own when you leave it, like today's SKU manager. */
function SkuRow({ sku, onSave }) {
  const [values, setValues] = useState({ name: sku.name, detectorPrompt: sku.detectorPrompt, description: sku.description });

  const leave = (key) => {
    const value = values[key];
    if (value === sku[key]) return;
    if (key === 'name' && !value.trim()) {
      setValues((v) => ({ ...v, name: sku.name }));
      return;
    }
    onSave(sku.index, { [key]: value });
  };

  return (
    <tr aria-label={`SKU ${sku.index}`}>
      <td><span className="dot" style={{ background: classColor(sku.index) }} /> {sku.index}</td>
      {FIELDS.map(({ key, label, multiline }) => {
        const Input = multiline ? 'textarea' : 'input';
        return (
          <td key={key}>
            <Input aria-label={label} value={values[key]}
                   placeholder={key === 'detectorPrompt' ? sku.name.replaceAll('_', ' ') : key === 'description' ? 'what it looks like' : ''}
                   onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
                   onBlur={() => leave(key)} />
          </td>
        );
      })}
    </tr>
  );
}

const EMPTY = { name: '', detectorPrompt: '', description: '' };

export default function SkuManager({ projectId, onClose, intro = false }) {
  const classes = useClasses(projectId);
  const add = useAddClass(projectId);
  const update = useUpdateClass(projectId);
  const [draft, setDraft] = useState(EMPTY);

  const submitNew = (e) => {
    e.preventDefault();
    if (!draft.name.trim()) return;
    add.mutate(draft, { onSuccess: () => setDraft(EMPTY) });
  };

  return (
    <Modal title="SKUs to detect" onClose={onClose} wide>
      {intro && (
        <p className="sku-intro"><b>What should be detected?</b> Add each SKU below. A short description of how it looks helps the AI a lot.</p>
      )}
      <p className="sku-tips">
        <b>Name</b> goes into your YOLO labels (no spaces, e.g. <code>sardine_155g</code>). The ID is the YOLO class ID, so rows never move; new SKUs go at the end.<br />
        <b>Detector prompt</b> is a short plain phrase for Grounding DINO / YOLO-World (e.g. <i>red tin can</i>).<br />
        <b>Description</b> is for Gemini / Claude / Ollama: shape, colours, brand text, size, and how it differs from look-alikes. Changes save when you leave a field.
      </p>
      <ErrorBanner error={update.error || add.error || classes.error} />
      {classes.isPending ? <LoadingState /> : (
        <form onSubmit={submitNew}>
          <table className="sku-table">
            <thead><tr><th>ID</th><th>Name</th><th>Detector prompt</th><th>Description</th></tr></thead>
            <tbody>
              {(classes.data ?? []).map((sku) => (
                <SkuRow key={`${sku.index}:${sku.name}:${sku.detectorPrompt}:${sku.description}`} sku={sku}
                        onSave={(index, changes) => update.mutate({ index, changes })} />
              ))}
              <tr className="sku-new">
                <td>+</td>
                <td><input aria-label="New SKU name" placeholder="new_sku_name" value={draft.name}
                           onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></td>
                <td><input aria-label="New SKU detector prompt" placeholder="short phrase (optional)" value={draft.detectorPrompt}
                           onChange={(e) => setDraft({ ...draft, detectorPrompt: e.target.value })} /></td>
                <td>
                  <textarea aria-label="New SKU description" placeholder="what it looks like (optional)" value={draft.description}
                            onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
                  <div className="sku-add"><button type="submit" className="primary" disabled={add.isPending}>Add SKU</button></div>
                </td>
              </tr>
            </tbody>
          </table>
        </form>
      )}
    </Modal>
  );
}

import { useState } from 'react';
import { ErrorBanner, Modal } from '@/components/ui';
import { useDeleteProject } from '../hooks/useProjects';

const count = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** Deleting can't be undone, so it says what goes and waits for the project name to be typed. */
export default function DeleteProjectDialog({ project, onClose, onDeleted = onClose }) {
  const remove = useDeleteProject();
  const [typed, setTyped] = useState('');
  const matches = typed === project.name;

  const what = project.imageCount > 0
    ? `its ${count(project.imageCount, 'photo')}, their labels and ${count(project.classCount, 'SKU')}`
    : `its ${count(project.classCount, 'SKU')}`;

  return (
    <Modal title={`Delete ${project.name}?`} onClose={onClose}>
      <form className="project-form" onSubmit={(e) => {
        e.preventDefault();
        if (matches) remove.mutate(project.id, { onSuccess: onDeleted });
      }}>
        <p>This deletes the project with {what}. It can’t be undone.</p>
        <label>
          <span>Type the project name to confirm</span>
          <input value={typed} placeholder={project.name} autoComplete="off" autoFocus
                 onChange={(e) => setTyped(e.target.value)} />
        </label>
        <ErrorBanner error={remove.error} />
        <div className="project-form-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="danger" disabled={!matches || remove.isPending}>Delete project</button>
        </div>
      </form>
    </Modal>
  );
}

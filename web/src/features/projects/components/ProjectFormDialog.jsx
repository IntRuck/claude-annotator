import { useState } from 'react';
import { ErrorBanner, Modal } from '@/components/ui';
import { useCreateProject, useUpdateProject } from '../hooks/useProjects';

export const MAX_DESCRIPTION = 200; // same limit as the backend

/** New project (no `project`) or edit an existing one's name and description. Closes once saved. */
export default function ProjectFormDialog({ project = null, onClose }) {
  const create = useCreateProject();
  const update = useUpdateProject();
  const [name, setName] = useState(project?.name ?? '');
  const [description, setDescription] = useState(project?.description ?? '');
  const saving = project ? update : create;

  const submit = (e) => {
    e.preventDefault();
    if (project) {
      update.mutate({ projectId: project.id, name, description }, { onSuccess: onClose });
    } else {
      create.mutate({ name, description }, { onSuccess: onClose });
    }
  };

  return (
    <Modal title={project ? 'Edit project' : 'New project'} onClose={onClose}>
      <form className="project-form" onSubmit={submit}>
        <label>
          <span>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </label>
        <label>
          <span>Description <span className="muted">(optional)</span></span>
          <textarea rows={2} maxLength={MAX_DESCRIPTION} value={description} placeholder="e.g. Shelf photos from store 3"
                    onChange={(e) => setDescription(e.target.value)} />
          <span className="project-form-count muted" aria-hidden="true">{description.length}/{MAX_DESCRIPTION}</span>
        </label>
        <ErrorBanner error={saving.error} />
        <div className="project-form-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="primary" disabled={saving.isPending}>
            {project ? 'Save changes' : 'Create project'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

import { useState } from 'react';
import { EmptyState, ErrorBanner, LoadingState } from '@/components/ui';
import { useProjectSummaries } from '../hooks/useProjects';
import { arrangeProjects, SORTS } from '../lib/listing';
import DeleteProjectDialog from './DeleteProjectDialog';
import ProjectFormDialog from './ProjectFormDialog';
import ProjectRow from './ProjectRow';
import '../styles/projects.css';

/** The projects page: every project as a row with its progress, plus search, sort, new, edit and delete. */
export default function ProjectsHome() {
  const summaries = useProjectSummaries();
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('changed');
  const [dialog, setDialog] = useState(null); // { kind: 'new' | 'edit' | 'delete', project? }
  const all = summaries.data ?? [];
  const shown = arrangeProjects(all, { query, sort });
  const close = () => setDialog(null);

  return (
    <section className="projects">
      <div className="projects-head">
        <h2>Projects</h2>
        <button type="button" className="primary" onClick={() => setDialog({ kind: 'new' })}>New project</button>
      </div>

      {all.length > 0 && (
        <div className="projects-tools">
          <input type="search" aria-label="Search projects" placeholder="Search projects" value={query}
                 onChange={(e) => setQuery(e.target.value)} />
          <label>
            Sort
            <select aria-label="Sort projects" value={sort} onChange={(e) => setSort(e.target.value)}>
              {SORTS.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
            </select>
          </label>
        </div>
      )}

      {summaries.isPending && <LoadingState />}
      <ErrorBanner error={summaries.error} />
      {summaries.isSuccess && all.length === 0 && (
        <EmptyState>No projects yet. Create one to start labelling.</EmptyState>
      )}
      {all.length > 0 && shown.length === 0 && <EmptyState>No projects match “{query.trim()}”.</EmptyState>}

      {shown.length > 0 && (
        <ul className="project-rows">
          {shown.map((p) => (
            <ProjectRow key={p.id} project={p} onEdit={(project) => setDialog({ kind: 'edit', project })}
                        onDelete={(project) => setDialog({ kind: 'delete', project })} />
          ))}
        </ul>
      )}

      {dialog?.kind === 'new' && <ProjectFormDialog onClose={close} />}
      {dialog?.kind === 'edit' && <ProjectFormDialog project={dialog.project} onClose={close} />}
      {dialog?.kind === 'delete' && <DeleteProjectDialog project={dialog.project} onClose={close} />}
    </section>
  );
}

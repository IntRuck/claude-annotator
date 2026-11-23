import { useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorBanner, LoadingState } from '@/components/ui';
import { useCreateProject, useProjects } from '../hooks/useProjects';
import '../styles/projects.css';

export default function ProjectList() {
  const projects = useProjects();
  const create = useCreateProject();
  const [name, setName] = useState('');

  const submit = (e) => {
    e.preventDefault();
    create.mutate(name, { onSuccess: () => setName('') });
  };

  return (
    <section className="projects">
      <form className="projects-new" onSubmit={submit}>
        <input aria-label="New project name" placeholder="New project name" value={name}
               onChange={(e) => setName(e.target.value)} />
        <button type="submit" className="primary" disabled={create.isPending}>Create project</button>
      </form>
      <ErrorBanner error={create.error} />

      {projects.isPending && <LoadingState />}
      <ErrorBanner error={projects.error} />
      {projects.data?.length === 0 && <EmptyState>No projects yet. Create one to start labelling.</EmptyState>}
      {projects.data?.length > 0 && (
        <ul className="projects-list">
          {projects.data.map((p) => (
            <li key={p.id}>
              <Link to={`/projects/${p.id}`}>
                <span className="projects-name">{p.name}</span>
                <span className="muted"> · created {new Date(p.createdAt).toLocaleDateString()}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

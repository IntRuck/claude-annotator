import { Menu } from '@/components/ui';
import { useProjects } from '../hooks/useProjects';

/** The project name in the workspace top bar; opens a list of the other projects. `onGo(path)` navigates (the
 * workspace saves unsaved edits first). A long name is cut with "…", so hovering shows it in full. */
export default function ProjectSwitcher({ project, onGo }) {
  const projects = useProjects();
  const others = (projects.data ?? []).filter((p) => p.id !== project?.id);
  const items = [
    ...others.map((p) => ({ label: p.name, onSelect: () => onGo(`/projects/${p.id}`) })),
    ...(others.length ? [{ separator: true }] : []),
    { label: 'All projects', onSelect: () => onGo('/') },
  ];
  return (
    <Menu label={project?.name ?? 'Project'} className="switcher"
          title={project ? [project.name, project.description].filter(Boolean).join('\n') : 'Switch project'}
          items={items}>
      <span className="switcher-name">{project?.name ?? ''}</span>
      <span className="switcher-caret" aria-hidden="true">▾</span>
    </Menu>
  );
}

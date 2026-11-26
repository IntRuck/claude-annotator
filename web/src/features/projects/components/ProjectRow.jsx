import { Link, useNavigate } from 'react-router-dom';
import { Menu } from '@/components/ui';
import { thumbUrl } from '@/features/images';
import { fullDate, timeAgo } from '../lib/relativeTime';

const count = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** Labelled-but-not-approved after approved, then the rest; the words say the same for screen readers. */
function Progress({ project }) {
  const pct = (n) => Math.round((n / project.imageCount) * 100);
  return (
    <div className="project-progress">
      <div className="project-bar" aria-hidden="true">
        <span className="approved" style={{ width: `${pct(project.reviewed)}%` }} />
        <span className="labelled" style={{ width: `${pct(project.labelled - project.reviewed)}%` }} />
      </div>
      <span>{`${pct(project.labelled)}% labelled, ${pct(project.reviewed)}% approved`}</span>
    </div>
  );
}

/** One project on the projects page. The whole row opens it; ⋯ has the other actions. */
export default function ProjectRow({ project, onEdit, onDelete }) {
  const navigate = useNavigate();
  const changed = new Date(project.lastChangedAt) - new Date(project.createdAt) > 1000;
  const when = project.lastChangedAt;

  return (
    <li className="project-row">
      <div className="project-cover">
        {project.coverImageId !== null && <img src={thumbUrl(project.coverImageId)} alt="" loading="lazy" />}
      </div>

      <div className="project-main">
        <Link to={`/projects/${project.id}`} className="project-name">{project.name}</Link>
        {project.description && <p className="project-desc">{project.description}</p>}
        {project.imageCount > 0 ? <Progress project={project} /> : <p className="project-none">No photos yet</p>}
        <p className="project-meta">
          {project.toApprove > 0 && <span>{project.toApprove} to approve</span>}
          {project.flagged > 0 && <span className="warn">{project.flagged} flagged</span>}
          {project.errors > 0 && <span className="bad">{count(project.errors, 'error')}</span>}
          <span className="muted" title={fullDate(when)}>{changed ? 'Changed' : 'Created'} {timeAgo(when)}</span>
        </p>
      </div>

      <p className="project-totals">
        <span>{count(project.imageCount, 'image')}</span>
        <span>{count(project.classCount, 'SKU')}</span>
      </p>

      <Menu label={`Actions for ${project.name}`} align="end" className="project-actions" items={[
        { label: 'Open', onSelect: () => navigate(`/projects/${project.id}`) },
        { label: 'Edit details', onSelect: () => onEdit(project) },
        { separator: true },
        { label: 'Delete…', onSelect: () => onDelete(project), danger: true },
      ]}>⋯</Menu>
    </li>
  );
}

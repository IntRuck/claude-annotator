import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ErrorBanner, LoadingState } from '@/components/ui';
import { useProject } from '@/features/projects';
import { ClassList, SkuManager, useClasses } from '@/features/classes';
import './pages.css';

/** One project's workspace. Later slices add the image strip, editor and AI controls. */
export default function WorkspacePage() {
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const classes = useClasses(projectId);
  const [skuOpen, setSkuOpen] = useState(false);
  const [currentClass, setCurrentClass] = useState(0);

  const noClassesYet = classes.isSuccess && classes.data.length === 0;
  const showSkus = skuOpen || noClassesYet;

  return (
    <div className="workspace">
      <header className="workspace-bar">
        <Link to="/" className="brand">Claude Annotator</Link>
        <h1>{project.data?.name ?? ''}</h1>
        <button type="button" onClick={() => setSkuOpen(true)}>SKUs</button>
      </header>
      <ErrorBanner error={project.error || classes.error} />
      <aside className="workspace-left">
        {classes.isPending ? <LoadingState /> : (
          <ClassList classes={classes.data ?? []} currentIndex={currentClass}
                     onPick={setCurrentClass} onOpenSkus={() => setSkuOpen(true)} />
        )}
      </aside>
      {showSkus && <SkuManager projectId={projectId} intro={noClassesYet} onClose={() => setSkuOpen(false)} />}
    </div>
  );
}

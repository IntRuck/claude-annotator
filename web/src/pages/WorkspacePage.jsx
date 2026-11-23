import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorBanner, LoadingState } from '@/components/ui';
import { useProject } from '@/features/projects';
import { ClassList, SkuManager, useClasses } from '@/features/classes';
import { ImageStrip, UploadImages, fileUrl, useImages } from '@/features/images';
import { ImportDataset } from '@/features/importer';
import './pages.css';

/** One project's workspace. The box editor replaces the plain image view in slice 5. */
export default function WorkspacePage() {
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const classes = useClasses(projectId);
  const [filter, setFilter] = useState('all');
  const images = useImages(projectId, filter);
  const [skuOpen, setSkuOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [introDismissed, setIntroDismissed] = useState(false);
  const [currentClass, setCurrentClass] = useState(0);
  const [chosenImageId, setChosenImageId] = useState(null);

  const items = images.data?.items ?? [];
  // Keep the chosen image while it's in the filtered list; otherwise open the first one (like today).
  const current = items.find((i) => i.id === chosenImageId) ?? items[0] ?? null;

  // A project with no classes opens the SKU manager once (like today), unless you're importing a dataset.
  const noClassesYet = classes.isSuccess && classes.data.length === 0;
  const showIntro = noClassesYet && !introDismissed && !importOpen;
  const showSkus = skuOpen || showIntro;
  const closeSkus = () => {
    setSkuOpen(false);
    setIntroDismissed(true);
  };

  return (
    <div className="workspace">
      <header className="workspace-bar">
        <Link to="/" className="brand">Claude Annotator</Link>
        <h1>{project.data?.name ?? ''}</h1>
        <button type="button" onClick={() => setImportOpen(true)}>Import dataset</button>
        <button type="button" onClick={() => setSkuOpen(true)}>SKUs</button>
      </header>
      <aside className="workspace-left">
        <ErrorBanner error={project.error || classes.error} />
        {classes.isPending ? <LoadingState /> : (
          <ClassList classes={classes.data ?? []} currentIndex={currentClass}
                     onPick={setCurrentClass} onOpenSkus={() => setSkuOpen(true)} />
        )}
      </aside>
      <section className="workspace-stage">
        {current
          ? <img className="stage-image" src={fileUrl(current.id)} alt={current.fileName} />
          : <EmptyState>{images.isPending ? 'Loading…' : 'Upload images to start'}</EmptyState>}
      </section>
      <aside className="workspace-right">
        <UploadImages projectId={projectId} />
        <ErrorBanner error={images.error} />
        <ImageStrip items={items} counts={images.data?.counts} filter={filter} currentId={current?.id ?? null}
                    onSelect={setChosenImageId} onFilterChange={setFilter} />
      </aside>
      {importOpen && <ImportDataset projectId={projectId} onClose={() => setImportOpen(false)} />}
      {showSkus && <SkuManager projectId={projectId} intro={noClassesYet} onClose={closeSkus} />}
    </div>
  );
}

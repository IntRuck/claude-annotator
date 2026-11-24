import { useCallback, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { EmptyState, ErrorBanner, LoadingState } from '@/components/ui';
import { useProject } from '@/features/projects';
import { ClassList, SkuManager, useClasses } from '@/features/classes';
import { ImageStrip, UploadImages, fileUrl, stepFrom, useImages, useSetFlag } from '@/features/images';
import { ImportDataset } from '@/features/importer';
import { BoxPanel, Editor, ReviewPanel, useEditor } from '@/features/editor';
import './pages.css';

/** One project's workspace: classes and boxes (left), editor (middle), review and images (right), like today. */
export default function WorkspacePage() {
  const projectId = Number(useParams().projectId);
  const project = useProject(projectId);
  const classes = useClasses(projectId);
  const [filter, setFilter] = useState('all');
  const images = useImages(projectId, filter);
  const flag = useSetFlag(projectId);
  const [skuOpen, setSkuOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [introDismissed, setIntroDismissed] = useState(false);
  const [currentClass, setCurrentClass] = useState(0);
  const [chosenImageId, setChosenImageId] = useState(null);
  const [tab, setTab] = useState('classes');
  const [hidden, setHidden] = useState(() => new Set());
  const [solo, setSolo] = useState(false);

  const items = images.data?.items ?? [];
  // Keep the chosen image while it's in the filtered list; otherwise open the first one (like today).
  const current = items.find((i) => i.id === chosenImageId) ?? items[0] ?? null;
  const editor = useEditor(current);
  const classList = classes.data ?? [];

  // A project with no classes opens the SKU manager once (like today), unless you're importing a dataset.
  const noClassesYet = classes.isSuccess && classList.length === 0;
  const showIntro = noClassesYet && !introDismissed && !importOpen;
  const dialogOpen = skuOpen || importOpen || showIntro;

  /** Unsaved changes are saved as "edited" before moving on (a conflict keeps you on the image). */
  const goTo = useCallback(async (id) => {
    if (id === null || id === current?.id) return;
    try {
      await editor.saveIfDirty();
    } catch {
      return;
    }
    setHidden(new Set());
    setSolo(false);
    setChosenImageId(id);
  }, [current, editor]);

  const openDialog = async (open) => {
    await editor.saveIfDirty().catch(() => {});
    open(true);
  };

  const approve = async () => {
    if (!current) return;
    const at = items.findIndex((i) => i.id === current.id);
    const next = items[at + 1]?.id ?? null;
    try {
      await editor.save('reviewed');
    } catch {
      return;
    }
    if (next !== null) setChosenImageId(next);
  };

  const setImageFlag = (flagged, reason, note) => flag.mutate({ imageId: current.id, flagged, reason, note });

  const pickClass = useCallback((index) => {
    setCurrentClass(index);
    editor.dispatch({ type: 'setClass', cls: index });
  }, [editor]);

  const counts = {};
  editor.state.boxes.forEach((b) => { counts[b.cls] = (counts[b.cls] ?? 0) + 1; });

  return (
    <div className="workspace">
      <header className="workspace-bar">
        <Link to="/" className="brand">Claude Annotator</Link>
        <h1>{project.data?.name ?? ''}</h1>
        <button type="button" onClick={() => openDialog(setImportOpen)}>Import dataset</button>
        <button type="button" onClick={() => openDialog(setSkuOpen)}>SKUs</button>
      </header>

      <aside className="workspace-left">
        <ErrorBanner error={project.error || classes.error} />
        <div className="tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'classes'} onClick={() => setTab('classes')}>Classes</button>
          <button type="button" role="tab" aria-selected={tab === 'boxes'} onClick={() => setTab('boxes')}>
            Boxes <span className="badge">{editor.state.boxes.length}</span>
          </button>
        </div>
        {tab === 'classes' && (classes.isPending ? <LoadingState /> : (
          <ClassList classes={classList} currentIndex={currentClass} counts={counts}
                     onPick={pickClass} onOpenSkus={() => openDialog(setSkuOpen)} />
        ))}
        {tab === 'boxes' && (
          <BoxPanel boxes={editor.state.boxes} classes={classList} selected={editor.state.selected} hidden={hidden}
                    onSelect={(i) => editor.dispatch({ type: 'select', index: i })}
                    onChangeClass={(i, cls) => { editor.dispatch({ type: 'select', index: i }); editor.dispatch({ type: 'setClass', cls }); }}
                    onDelete={(i) => { editor.dispatch({ type: 'select', index: i }); editor.dispatch({ type: 'remove' }); setHidden(new Set()); }}
                    onToggleHidden={(i) => setHidden((h) => { const n = new Set(h); if (n.has(i)) n.delete(i); else n.add(i); return n; })} />
        )}
        {current?.note && <p className="image-note">{current.note}</p>}
      </aside>

      <section className="workspace-stage">
        {current
          ? (
            <Editor key={current.id} editor={editor} image={current} imageUrl={fileUrl(current.id)} classes={classList}
                    currentClass={currentClass} hidden={hidden} solo={solo} setSolo={setSolo} dialogOpen={dialogOpen}
                    onPickClass={pickClass} onStep={(d) => goTo(stepFrom(items, current.id, d))} onApprove={approve}
                    onToggleFlag={() => setImageFlag(!current.flagged, '', '')} onNeedClasses={() => openDialog(setSkuOpen)} />
          )
          : <EmptyState>{images.isPending ? 'Loading…' : 'Upload images to start'}</EmptyState>}
      </section>

      <aside className="workspace-right">
        <UploadImages projectId={projectId} />
        {current && (
          <ReviewPanel key={current.id} image={current} dirty={editor.state.dirty} onApprove={approve} onFlag={setImageFlag} />
        )}
        <ErrorBanner error={images.error || flag.error} />
        <ImageStrip items={items} counts={images.data?.counts} filter={filter} currentId={current?.id ?? null}
                    onSelect={goTo} onFilterChange={async (f) => { await editor.saveIfDirty().catch(() => {}); setFilter(f); }} />
      </aside>

      {importOpen && <ImportDataset projectId={projectId} onClose={() => setImportOpen(false)} />}
      {(skuOpen || showIntro) && (
        <SkuManager projectId={projectId} intro={noClassesYet}
                    onClose={() => { setSkuOpen(false); setIntroDismissed(true); }} />
      )}
    </div>
  );
}

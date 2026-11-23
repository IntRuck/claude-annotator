import { ErrorBanner } from '@/components/ui';
import { useUploadImages } from '../hooks/useImages';
import '../styles/images.css';

const ACCEPT = '.jpg,.jpeg,.png,.bmp,.webp,image/jpeg,image/png,image/bmp,image/webp';

export default function UploadImages({ projectId }) {
  const upload = useUploadImages(projectId);

  const choose = (e) => {
    const files = [...e.target.files];
    e.target.value = '';
    if (files.length) upload.mutate(files);
  };

  const result = upload.data;
  return (
    <div className="upload">
      <label className="upload-button">
        {upload.isPending ? 'Uploading…' : 'Upload images'}
        <input type="file" multiple accept={ACCEPT} aria-label="Upload images" onChange={choose} disabled={upload.isPending} />
      </label>
      <ErrorBanner error={upload.error} />
      {result && (
        <div className="upload-result">
          <div>Added {result.added.length} · skipped {result.skipped.length}</div>
          {result.skipped.map((s) => <div key={s.fileName} className="muted">{s.fileName}: {s.reason}</div>)}
        </div>
      )}
    </div>
  );
}

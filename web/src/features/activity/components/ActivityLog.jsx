import '../styles/activity.css';

const time = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });

/** Activity log (folded away like today): what the AI did, queued or stopped, newest first. A line about an
 * image opens that image. */
export default function ActivityLog({ entries, onSelectImage }) {
  return (
    <details className="activity-log">
      <summary>Activity log</summary>
      {entries.length === 0 ? <p className="empty">Nothing yet.</p> : (
        <ol>
          {entries.map((e) => (
            <li key={e.id} className={e.level}>
              <time dateTime={e.createdAt}>{time(e.createdAt)}</time>
              {e.imageId
                ? <button type="button" className="link" onClick={() => onSelectImage(e.imageId)}>{e.message}</button>
                : <span>{e.message}</span>}
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

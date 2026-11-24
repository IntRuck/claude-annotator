import '../styles/jobs.css';

/** An engine hit its usage limit: its images wait in the queue until Resume (today's run just stopped). */
export default function PausedBanner({ paused, busy, onResume }) {
  if (!paused?.length) return null;
  return (
    <div className="paused-banner" role="status">
      <span>
        {paused.map((p) => `⏸ ${p.label} paused: ${p.reason}`).join(' · ')}
      </span>
      <button type="button" disabled={busy} onClick={onResume} title="Carry on with the waiting images">Resume</button>
    </div>
  );
}

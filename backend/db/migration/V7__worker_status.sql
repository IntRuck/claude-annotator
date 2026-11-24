-- Worker heartbeats and engine pauses.
-- The worker writes its row every 15 s with what each engine can do right now (key set? which models?), so the
-- page can show "worker offline" and per-engine warnings. A usage limit pauses that engine: its jobs stay queued
-- until someone presses Resume (today's run simply stopped).

create table worker_status (
    worker_id    text primary key,                 -- host:pid
    started_at   timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    engines      jsonb       not null default '{}' -- {"gemini": {"ready": true, "note": "", "models": [...]}}
);

create table engine_pauses (
    engine    text primary key,
    reason    text        not null,
    paused_at timestamptz not null default now()
);

alter table worker_status enable row level security;
alter table engine_pauses enable row level security;

-- Live updates (V4 channel). Both have no project, so the payload's projectId is null and the API sends the
-- engine status to every open tab. The worker also wakes on these (a Resume).
create trigger worker_status_notify_change
    after insert or update or delete on worker_status
    for each row execute function notify_change('worker', 'worker_id');

create trigger engine_pauses_notify_change
    after insert or update or delete on engine_pauses
    for each row execute function notify_change('worker', 'engine');

-- AI work queue and the activity log.
-- A job is one image for one engine. The worker claims the oldest queued job with FOR UPDATE SKIP LOCKED,
-- so jobs survive restarts (today's queue lived in memory). Export jobs come in a later version.

create table jobs (
    id          bigint generated always as identity primary key,
    project_id  bigint      not null references projects (id) on delete cascade,
    image_id    bigint      references images (id) on delete cascade,
    kind        text        not null check (kind in ('annotate', 'refine')),
    engine      text        not null,
    options     jsonb       not null default '{}',
    status      text        not null default 'queued'
                            check (status in ('queued', 'running', 'done', 'failed', 'cancelled')),
    error       text        not null default '',
    created_at  timestamptz not null default now(),
    started_at  timestamptz,
    finished_at timestamptz
);

-- The queue, oldest first.
create index jobs_queued on jobs (id) where status = 'queued';
create index jobs_project_status on jobs (project_id, status);
-- At most one unfinished labelling job per image, so pressing "Label all" twice doesn't queue it twice.
create unique index jobs_one_open_per_image on jobs (image_id) where status in ('queued', 'running');

alter table jobs enable row level security;

create table activity_log (
    id         bigint generated always as identity primary key,
    project_id bigint      not null references projects (id) on delete cascade,
    job_id     bigint      references jobs (id) on delete set null,
    image_id   bigint      references images (id) on delete set null,
    level      text        not null default 'info' check (level in ('info', 'warning', 'error')),
    message    text        not null,
    created_at timestamptz not null default now()
);

create index activity_project_recent on activity_log (project_id, id desc);

alter table activity_log enable row level security;

-- Live updates (same channel as V4). Activity: one payload per entry.
create trigger activity_notify_change
    after insert or update or delete on activity_log
    for each row execute function notify_change('activity', 'id');

-- Jobs: one payload per statement and project ({type, op, projectId}, no id), so queueing 500 images is one
-- message. The API answers it with the project's job summary; the worker wakes on it.
create function notify_jobs_change() returns trigger
    language plpgsql as
$$
declare
    pid bigint;
begin
    for pid in select distinct project_id from changed_jobs loop
        perform pg_notify('annotator_changes', jsonb_build_object(
            'type', 'jobs', 'op', lower(tg_op), 'projectId', pid)::text);
    end loop;
    return null;
end;
$$;

create trigger jobs_notify_insert
    after insert on jobs referencing new table as changed_jobs
    for each statement execute function notify_jobs_change();

create trigger jobs_notify_update
    after update on jobs referencing new table as changed_jobs
    for each statement execute function notify_jobs_change();

create trigger jobs_notify_delete
    after delete on jobs referencing old table as changed_jobs
    for each statement execute function notify_jobs_change();

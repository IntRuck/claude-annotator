-- Projects (datasets) and their classes (SKUs).
-- class_index is the YOLO class ID: new classes go at the end and an index never changes,
-- so renaming a class keeps existing labels valid.

create table projects (
    id         bigint generated always as identity primary key,
    name       text        not null check (length(btrim(name)) > 0),
    created_at timestamptz not null default now()
);

create table classes (
    project_id      bigint  not null references projects (id) on delete cascade,
    class_index     integer not null check (class_index >= 0),
    name            text    not null check (name ~ '^[^[:space:]]+$'),
    detector_prompt text    not null default '',
    description     text    not null default '',
    primary key (project_id, class_index)
);

-- One name per project, ignoring capitals.
create unique index classes_project_name_ci on classes (project_id, lower(name));

-- Only the backend touches data: RLS on, no policies for anon/authenticated.
alter table projects enable row level security;
alter table classes enable row level security;

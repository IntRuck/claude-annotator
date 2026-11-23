-- Photos in a project. Originals and 240 px thumbnails live in the private `images` Storage bucket
-- (created by the API at startup); these rows hold their paths.
-- `flagged` ("check this later") is separate from `status`, so an approved image can still be flagged.

create table images (
    id           bigint generated always as identity primary key,
    project_id   bigint      not null references projects (id) on delete cascade,
    file_name    text        not null check (length(file_name) > 0),
    stem         text        not null,
    storage_path text        not null,
    thumb_path   text        not null,
    width        integer     not null check (width > 0),
    height       integer     not null check (height > 0),
    status       text        not null default 'unlabeled'
                             check (status in ('unlabeled', 'auto', 'edited', 'reviewed', 'error')),
    note         text        not null default '',
    flagged      boolean     not null default false,
    flag_reason  text        not null default '',
    flag_note    text        not null default '',
    box_count    integer     not null default 0 check (box_count >= 0),
    created_at   timestamptz not null default now(),
    updated_at   timestamptz not null default now(),
    unique (project_id, file_name)
);

create index images_project_status on images (project_id, status);

alter table images enable row level security;

-- Projects page: a short description under each project's name, and updated_at, moved on when the name or
-- description changes. "Last changed" on the projects page is the later of this and the newest image change.

alter table projects
    add column description text        not null default '',
    add column updated_at  timestamptz not null default now();

-- Projects made before this migration: unchanged since they were created.
update projects set updated_at = created_at;

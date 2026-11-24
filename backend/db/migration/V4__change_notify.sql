-- Live updates. Every committed change to images or classes sends a small NOTIFY on `annotator_changes`:
--   {"type": "images" | "classes", "op": "insert" | "update" | "delete", "id": <row id>, "projectId": <id>}
-- The API's listener reads the row and pushes the full DTO to the browser tabs of that project over SSE.
-- NOTIFY is only delivered on commit, and Postgres folds identical payloads within one transaction, so
-- saving 50 boxes (50 box_count updates on one image) sends one image update.
-- Later slices add their tables (jobs, activity, worker) to the same channel.

create function notify_change() returns trigger
    language plpgsql as
$$
declare
    changed jsonb;
begin
    if tg_op = 'UPDATE' and old is not distinct from new then
        return null;
    end if;
    changed := to_jsonb(case when tg_op = 'DELETE' then old else new end);
    perform pg_notify('annotator_changes', jsonb_build_object(
        'type', tg_argv[0],
        'op', lower(tg_op),
        'id', changed -> tg_argv[1],
        'projectId', changed -> 'project_id')::text);
    return null;
end;
$$;

-- Arguments: the message type, then the column that identifies the row within its project.
create trigger images_notify_change
    after insert or update or delete on images
    for each row execute function notify_change('images', 'id');

create trigger classes_notify_change
    after insert or update or delete on classes
    for each row execute function notify_change('classes', 'class_index');
